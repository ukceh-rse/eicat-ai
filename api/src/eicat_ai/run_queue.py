"""Per-analysis run queue (design D2): each analysis's queued runs are processed one at a time, in the order queued,
by a drain task that lives while the analysis has queued runs. Analyses drain independently of each other."""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from beanie import PydanticObjectId
from beanie.exceptions import RevisionIdWasChanged
from loguru import logger

from eicat_ai.agents import data_extraction_agent
from eicat_ai.anchoring import Locator
from eicat_ai.converters import extract_impacts
from eicat_ai.models import (
    ActorKind,
    Analysis,
    AnalysisRun,
    AuditEvent,
    EvidenceSpan,
    Impact,
    Paper,
    PaperDoc,
    RunStatus,
    SpeciesNames,
)
from eicat_ai.review import Event, apply_run
from eicat_ai.settings import settings

SAVE_ATTEMPTS = 3

_drains: Dict[PydanticObjectId, asyncio.Task] = {}
_woken: Set[PydanticObjectId] = set()
_extracting: Dict[str, asyncio.Task] = {}  # run id -> the task extracting its paper
_stopped: Set[str] = set()  # runs whose extraction stop() cancelled


async def write_events(analysis_id: PydanticObjectId, events: List[Event]) -> None:
    if events:
        await AuditEvent.insert_many([e.to_document(analysis_id) for e in events])


def wake(analysis_id: PydanticObjectId) -> None:
    """Make sure the analysis's queued runs get processed."""
    _woken.add(analysis_id)
    if analysis_id not in _drains:
        _drains[analysis_id] = asyncio.create_task(_drain(analysis_id))


def stop(run_id: str) -> None:
    """Cancel the extraction of a run already saved as cancelled."""
    task = _extracting.get(run_id)
    if task is not None:
        _stopped.add(run_id)
        task.cancel()


async def idle() -> None:
    """Wait until every queue is drained."""
    while _drains:
        await asyncio.gather(*_drains.values(), return_exceptions=True)


async def shutdown() -> None:
    """Stop draining; a run cut off here is still recorded as running and is failed on the next start."""
    # cancelling a drain also cancels the extraction it awaits
    tasks = list(_drains.values())
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


async def _drain(analysis_id: PydanticObjectId) -> None:
    try:
        while True:
            _woken.discard(analysis_id)
            claimed = await _claim(analysis_id)
            if claimed is None:
                # no await between this check and leaving, so a wake() since the claim is never lost
                if analysis_id not in _woken:
                    return
                continue
            await _process(analysis_id, *claimed)
    except Exception:
        logger.exception(f"Draining the run queue of analysis {analysis_id} failed")
    finally:
        _drains.pop(analysis_id, None)


async def _claim(analysis_id: PydanticObjectId) -> Optional[Tuple[AnalysisRun, SpeciesNames]]:
    """Start the oldest queued run of a current paper."""
    for attempt in range(1, SAVE_ATTEMPTS + 1):
        analysis = await Analysis.get(analysis_id)
        if analysis is None:
            return None
        papers = {str(p) for p in analysis.paper_ids}
        run = next((r for r in analysis.runs if r.status == RunStatus.QUEUED and r.paper_id in papers), None)
        if run is None:
            return None
        run.status, run.started_at = RunStatus.RUNNING, datetime.now(timezone.utc)
        analysis.refresh_status()
        try:
            await analysis.save()
        except RevisionIdWasChanged:
            if attempt == SAVE_ATTEMPTS:
                raise
            continue
        await write_events(analysis_id, [Event(
            at=run.started_at, actor=ActorKind.SYSTEM, action="run_started", run_id=run.id,
        )])
        return run, analysis.species


def _anchored(markdown: str, impacts: List[Impact]) -> List[Tuple[Impact, List[EvidenceSpan]]]:
    """Each impact with its evidence anchored in the paper. Anchoring is CPU-bound, so runs call this off the event
    loop to keep the API responsive."""
    locator = Locator(markdown)
    return [(i, locator.anchor(i.evidence)) for i in impacts]


async def _extract(
    paper_id: str, species: SpeciesNames
) -> Tuple[List[Impact], List[Tuple[Impact, List[EvidenceSpan]]], Dict[str, int]]:
    doc = await PaperDoc.get(PydanticObjectId(paper_id))
    if doc is None or doc.markdown is None:
        raise RuntimeError("Paper text not available")
    agent = data_extraction_agent(settings.model)
    impacts, usage = await extract_impacts(agent, Paper(content=doc.markdown), species)
    return impacts, await asyncio.to_thread(_anchored, doc.markdown, impacts), usage


async def _process(analysis_id: PydanticObjectId, run: AnalysisRun, species: SpeciesNames) -> None:
    task = asyncio.create_task(_extract(run.paper_id, species))
    _extracting[run.id] = task
    impacts: List[Impact] = []
    anchored: List[Tuple[Impact, List[EvidenceSpan]]] = []
    usage: Dict[str, int] = {}
    error: Optional[str] = None
    try:
        impacts, anchored, usage = await task
    except asyncio.CancelledError:
        # cancelling the drain cancels the extraction too, so only stop() tells the two apart
        if run.id not in _stopped:
            task.cancel()
            raise
        _stopped.discard(run.id)
        return  # removing the paper cancelled the run, and recorded it
    except Exception as e:
        error = str(e)
    finally:
        _extracting.pop(run.id, None)

    try:
        events = await _complete_run(analysis_id, run.id, impacts, anchored, usage, error)
    except Exception as e:
        # never leave the paper running, which would lock its review
        logger.exception(f"Saving run {run.id} of analysis {analysis_id} failed")
        error = f"Saving the run failed: {e}"
        events = []
        analysis = await Analysis.get(analysis_id)
        if analysis is None:
            return
        for r in analysis.runs:
            if r.id == run.id and r.status == RunStatus.RUNNING:
                r.status, r.completed_at, r.error = RunStatus.FAILED, datetime.now(timezone.utc), error
        analysis.refresh_status()
        await analysis.save(ignore_revision=True)
    if events is None:
        return
    action = "run_completed" if error is None else "run_failed"
    events.append(Event(
        at=datetime.now(timezone.utc), actor=ActorKind.SYSTEM, action=action, run_id=run.id, note=error,
    ))
    await write_events(analysis_id, events)


async def _complete_run(
    analysis_id: PydanticObjectId,
    run_id: str,
    impacts: List[Impact],
    anchored: List[Tuple[Impact, List[EvidenceSpan]]],
    usage: Dict[str, int],
    error: Optional[str],
) -> Optional[List[Event]]:
    """Save a finished run of one paper; returns the merge events, or None if the analysis was deleted or the run
    cancelled meanwhile."""
    # merge into the latest document, so review edits of other papers made since the run started are kept
    now = datetime.now(timezone.utc)
    for attempt in range(1, SAVE_ATTEMPTS + 1):
        analysis = await Analysis.get(analysis_id)
        if analysis is None:
            return None
        run = next(r for r in analysis.runs if r.id == run_id)
        if run.status != RunStatus.RUNNING:
            return None
        paper_id = run.paper_id
        run.completed_at, run.usage = now, usage
        for k, v in usage.items():
            analysis.usage[k] = analysis.usage.get(k, 0) + v
        events: List[Event] = []
        if error is None:
            in_paper = [i for i in analysis.impacts if i.paper_id == paper_id]
            merged, events = apply_run(in_paper, {paper_id: anchored}, run_id, run.verified_choice, now)
            analysis.impacts = merged + [i for i in analysis.impacts if i.paper_id != paper_id]
            analysis.results[paper_id] = impacts
            run.status = RunStatus.COMPLETED
        else:
            run.status, run.error = RunStatus.FAILED, error
        analysis.refresh_status()
        try:
            await analysis.save()
            return events
        except RevisionIdWasChanged:
            if attempt == SAVE_ATTEMPTS:
                raise
            logger.warning(f"Analysis {analysis_id} changed while saving run {run_id}, retrying")
