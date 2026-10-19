import asyncio
import json
from datetime import datetime, timezone
from typing import Callable, Dict, List, Literal, Optional, Tuple

from beanie import PydanticObjectId
from beanie.exceptions import RevisionIdWasChanged
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel, ValidationError

from eicat_ai.agents import data_extraction_agent
from eicat_ai import review
from eicat_ai.anchoring import Locator, validate_spans
from eicat_ai.converters import extract_impacts
from eicat_ai.models import (
    ActorKind,
    Analysis,
    AnalysisResponse,
    AnalysisRun,
    AnalysisStatus,
    AuditEvent,
    Category,
    EvidenceSpan,
    Impact,
    ImpactOrigin,
    ImpactState,
    Mechanism,
    Paper,
    PaperDoc,
    PaperStatus,
    ReviewedImpact,
    RunStatus,
    SpeciesNames,
    VerifiedChoice,
)
from eicat_ai.review import Event, Extracted, ReviewError, apply_run
from eicat_ai.settings import settings

router = APIRouter(prefix="/analyses", tags=["Analyses"])


async def _write_events(analysis_id: PydanticObjectId, events: List[Event]) -> None:
    if events:
        await AuditEvent.insert_many([e.to_document(analysis_id) for e in events])


SAVE_ATTEMPTS = 3


def _anchored(markdown: str, impacts: List[Impact]) -> List[Tuple[Impact, List[EvidenceSpan]]]:
    """Each impact with its evidence anchored in the paper. Anchoring is CPU-bound, so runs call this off the event
    loop to keep the API responsive."""
    locator = Locator(markdown)
    return [(i, locator.anchor(i.evidence)) for i in impacts]


async def _run_analysis(analysis_id: PydanticObjectId, run_id: str) -> None:
    analysis = await Analysis.get(analysis_id)
    if analysis is None:
        return
    results: Dict[str, List[Impact]] = {}
    extracted: Extracted = {}
    usage: Dict[str, int] = {}
    error: Optional[str] = None
    run_papers = {str(p) for p in analysis.paper_ids}
    try:
        agent = data_extraction_agent(settings.model)
        for paper_id in analysis.paper_ids:
            doc = await PaperDoc.get(paper_id)
            if doc is None or doc.markdown is None:
                continue
            impacts, paper_usage = await extract_impacts(agent, Paper(content=doc.markdown), analysis.species)
            results[str(paper_id)] = impacts
            extracted[str(paper_id)] = await asyncio.to_thread(_anchored, doc.markdown, impacts)
            for k, v in paper_usage.items():
                usage[k] = usage.get(k, 0) + v
    except Exception as e:
        error = str(e)

    try:
        events = await _complete_run(analysis_id, run_id, results, extracted, usage, error, run_papers)
    except Exception as e:
        # never leave the analysis running, which would lock review
        logger.exception(f"Saving run {run_id} of analysis {analysis_id} failed")
        error = f"Saving the run failed: {e}"
        events = []
        analysis = await Analysis.get(analysis_id)
        if analysis is None:
            return
        analysis.status, analysis.error = AnalysisStatus.FAILED, error
        for run in analysis.runs:
            if run.id == run_id:
                run.status, run.completed_at = RunStatus.FAILED, datetime.now(timezone.utc)
        await analysis.save(ignore_revision=True)
    if events is None:
        return
    action = "run_completed" if error is None else "run_failed"
    events.append(Event(
        at=datetime.now(timezone.utc), actor=ActorKind.SYSTEM, action=action, run_id=run_id, note=error,
    ))
    await _write_events(analysis_id, events)


async def _complete_run(
    analysis_id: PydanticObjectId,
    run_id: str,
    results: Dict[str, List[Impact]],
    extracted: Extracted,
    usage: Dict[str, int],
    error: Optional[str],
    run_papers: set[str],
) -> Optional[List[Event]]:
    """Save a finished run; returns the merge events, or None if the analysis was deleted meanwhile."""
    # merge only once every paper has succeeded, into the latest document, so a failed run leaves impacts untouched
    # and review edits made since the run started are kept
    now = datetime.now(timezone.utc)
    for attempt in range(1, SAVE_ATTEMPTS + 1):
        analysis = await Analysis.get(analysis_id)
        if analysis is None:
            return None
        run = next(r for r in analysis.runs if r.id == run_id)
        run.completed_at, run.usage = now, usage
        for k, v in usage.items():
            analysis.usage[k] = analysis.usage.get(k, 0) + v
        events: List[Event] = []
        if error is None:
            # impacts of papers removed from the analysis since are left as they were
            in_run = [i for i in analysis.impacts if i.paper_id in run_papers]
            merged, events = apply_run(in_run, extracted, run_id, run.verified_choice, now)
            analysis.impacts = merged + [i for i in analysis.impacts if i.paper_id not in run_papers]
            analysis.results = results
            analysis.status, run.status = AnalysisStatus.COMPLETED, RunStatus.COMPLETED
            analysis.completed_at, analysis.error = now, None
        else:
            analysis.status, run.status = AnalysisStatus.FAILED, RunStatus.FAILED
            analysis.error = error
        try:
            await analysis.save()
            return events
        except RevisionIdWasChanged:
            if attempt == SAVE_ATTEMPTS:
                raise
            logger.warning(f"Analysis {analysis_id} changed while saving run {run_id}, retrying")


@router.post("/", response_model=AnalysisResponse, status_code=201)
async def create_analysis(species: SpeciesNames) -> AnalysisResponse:
    analysis = Analysis(species=species)
    await analysis.insert()
    return AnalysisResponse.from_doc(analysis)


@router.get("/", response_model=List[AnalysisResponse])
async def list_analyses() -> List[AnalysisResponse]:
    docs = await Analysis.find_all().to_list()
    return [AnalysisResponse.from_doc(d) for d in docs]


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(analysis_id: PydanticObjectId) -> AnalysisResponse:
    analysis = await Analysis.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return AnalysisResponse.from_doc(analysis)


@router.post("/{analysis_id}/papers/{paper_id}", response_model=AnalysisResponse)
async def add_paper(analysis_id: PydanticObjectId, paper_id: PydanticObjectId) -> AnalysisResponse:
    analysis = await Analysis.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    doc = await PaperDoc.get(paper_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    if doc.status != PaperStatus.READY:
        raise HTTPException(status_code=400, detail="Paper conversion not complete")
    if paper_id not in analysis.paper_ids:
        analysis.paper_ids.append(paper_id)
        await analysis.save()
    return AnalysisResponse.from_doc(analysis)


@router.delete("/{analysis_id}/papers/{paper_id}", response_model=AnalysisResponse)
async def remove_paper(analysis_id: PydanticObjectId, paper_id: PydanticObjectId) -> AnalysisResponse:
    analysis = await Analysis.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    analysis.paper_ids = [pid for pid in analysis.paper_ids if pid != paper_id]
    await analysis.save()
    return AnalysisResponse.from_doc(analysis)


def _ai_counts(analysis: Analysis) -> Tuple[int, int]:
    active = [i for i in analysis.visible_impacts() if i.state == ImpactState.ACTIVE and i.origin == ImpactOrigin.AI]
    verified = sum(1 for i in active if i.verified)
    return verified, len(active) - verified


@router.post("/{analysis_id}/run", response_model=AnalysisResponse)
async def run_analysis(
    analysis_id: PydanticObjectId,
    background_tasks: BackgroundTasks,
    verified: Optional[VerifiedChoice] = Query(
        default=None, description="Keep or discard verified AI impacts; required when any exist"
    ),
):
    analysis = await Analysis.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.status == AnalysisStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Analysis is already running")
    if not analysis.paper_ids:
        raise HTTPException(status_code=400, detail="No papers added to this analysis")
    n_verified, n_unverified = _ai_counts(analysis)
    if n_verified and verified is None:
        return JSONResponse(status_code=409, content={
            "detail": "The analysis has verified impacts; choose verified=keep or verified=discard",
            "verified": n_verified,
            "unverified": n_unverified,
        })
    run = AnalysisRun(model=settings.model, verified_choice=verified)
    analysis.runs.append(run)
    analysis.status = AnalysisStatus.RUNNING
    await analysis.save()
    await _write_events(analysis_id, [Event(
        at=run.started_at, actor=ActorKind.SYSTEM, action="run_started", run_id=run.id,
        note=f"verified={verified.value}" if verified else None,
    )])
    background_tasks.add_task(_run_analysis, analysis_id, run.id)
    return AnalysisResponse.from_doc(analysis)


@router.delete("/{analysis_id}", status_code=204)
async def delete_analysis(analysis_id: PydanticObjectId) -> None:
    analysis = await Analysis.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    # audit events are kept: they outlive the analysis
    await analysis.delete()


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------


class ImpactFields(BaseModel):
    """Editable impact fields. Evidence is set only through spans selected in the paper."""

    model_config = {"extra": "forbid"}

    alien_species: Optional[str] = None
    mechanism: Optional[Mechanism] = None
    category: Optional[Category] = None
    reversibility: Optional[Literal["reversible", "irreversible", "unknown"]] = None
    confidence: Optional[Literal["Low", "Medium", "High"]] = None
    justification: Optional[str] = None
    impacted_species: Optional[List[str]] = None


class ImpactCreate(BaseModel):
    paper_id: str
    fields: ImpactFields
    evidence: List[EvidenceSpan]
    note: Optional[str] = None


class ImpactPatch(BaseModel):
    fields: Optional[ImpactFields] = None
    evidence: Optional[List[EvidenceSpan]] = None
    verified: Optional[bool] = None
    note: Optional[str] = None


class ReviewNote(BaseModel):
    note: Optional[str] = None


async def _reviewable(analysis_id: PydanticObjectId) -> Analysis:
    analysis = await Analysis.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.status == AnalysisStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Impacts cannot be reviewed while the analysis is running")
    return analysis


def _impact(analysis: Analysis, impact_id: str) -> ReviewedImpact:
    # impacts of papers removed from the analysis are hidden, and not reviewable until the paper is added back
    impact = next((i for i in analysis.visible_impacts() if i.id == impact_id), None)
    if impact is None:
        raise HTTPException(status_code=404, detail="Impact not found")
    return impact


async def _validated_spans(paper_id: str, spans: List[EvidenceSpan]) -> List[EvidenceSpan]:
    doc = await PaperDoc.get(PydanticObjectId(paper_id))
    if doc is None or doc.markdown is None:
        raise HTTPException(status_code=422, detail="Paper text not available")
    try:
        validate_spans(doc.markdown, spans)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    # a reviewer chose these passages, so none stands in for evidence the AI misquoted
    return [s.model_copy(update={"approximate": False}) for s in spans]


async def _review(analysis: Analysis, action: Callable[[], List[Event]]) -> AnalysisResponse:
    """Apply a review action, save (a concurrent change raises RevisionIdWasChanged, returned as 409) and log it."""
    try:
        events = action()
    except ReviewError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=json.loads(e.json(include_url=False)))
    await analysis.save()
    await _write_events(analysis.id, events)
    return AnalysisResponse.from_doc(analysis)


@router.post("/{analysis_id}/impacts", response_model=AnalysisResponse, status_code=201)
async def create_impact(analysis_id: PydanticObjectId, body: ImpactCreate) -> AnalysisResponse:
    analysis = await _reviewable(analysis_id)
    if body.paper_id not in {str(p) for p in analysis.paper_ids}:
        raise HTTPException(status_code=422, detail="Paper is not part of this analysis")
    spans = await _validated_spans(body.paper_id, body.evidence)

    def action() -> List[Event]:
        impact, events = review.create_impact(
            body.paper_id, body.fields.model_dump(exclude_unset=True), spans, body.note, datetime.now(timezone.utc)
        )
        analysis.impacts.append(impact)
        return events

    return await _review(analysis, action)


@router.patch("/{analysis_id}/impacts/{impact_id}", response_model=AnalysisResponse)
async def edit_impact(analysis_id: PydanticObjectId, impact_id: str, body: ImpactPatch) -> AnalysisResponse:
    analysis = await _reviewable(analysis_id)
    impact = _impact(analysis, impact_id)
    spans = None if body.evidence is None else await _validated_spans(impact.paper_id, body.evidence)
    fields = body.fields.model_dump(exclude_unset=True) if body.fields else {}
    return await _review(analysis, lambda: review.edit_impact(
        impact, fields, spans, body.verified, body.note, datetime.now(timezone.utc)
    ))


@router.post("/{analysis_id}/impacts/{impact_id}/remove", response_model=AnalysisResponse)
async def remove_impact(analysis_id: PydanticObjectId, impact_id: str, body: ReviewNote = ReviewNote()) -> AnalysisResponse:
    analysis = await _reviewable(analysis_id)
    impact = _impact(analysis, impact_id)
    return await _review(analysis, lambda: review.remove_impact(impact, body.note, datetime.now(timezone.utc)))


@router.post("/{analysis_id}/impacts/{impact_id}/restore", response_model=AnalysisResponse)
async def restore_impact(analysis_id: PydanticObjectId, impact_id: str, body: ReviewNote = ReviewNote()) -> AnalysisResponse:
    analysis = await _reviewable(analysis_id)
    impact = _impact(analysis, impact_id)
    return await _review(analysis, lambda: review.restore_impact(impact, body.note, datetime.now(timezone.utc)))


@router.get("/{analysis_id}/audit", response_model=List[AuditEvent])
async def get_audit(analysis_id: PydanticObjectId, impact_id: Optional[str] = None) -> List[AuditEvent]:
    """Audit events oldest first, optionally for one impact. Available after the analysis is deleted."""
    query = AuditEvent.find(AuditEvent.analysis_id == analysis_id)
    if impact_id is not None:
        query = query.find(AuditEvent.impact_id == impact_id)
    return await query.sort(+AuditEvent.at, +AuditEvent.id).to_list()
