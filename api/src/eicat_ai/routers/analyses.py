import json
from datetime import datetime, timezone
from typing import Callable, List, Literal, Optional, Set, Tuple

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from eicat_ai import review, run_queue
from eicat_ai.anchoring import validate_spans
from eicat_ai.models import (
    ActorKind,
    Analysis,
    AnalysisResponse,
    AnalysisRun,
    AuditEvent,
    Category,
    EvidenceSpan,
    ImpactOrigin,
    ImpactState,
    Mechanism,
    PaperDoc,
    PaperStatus,
    ReviewedImpact,
    RunStatus,
    SpeciesNames,
    VerifiedChoice,
)
from eicat_ai.review import Event, ReviewError
from eicat_ai.run_queue import write_events
from eicat_ai.settings import settings

router = APIRouter(prefix="/analyses", tags=["Analyses"])


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
        analysis.refresh_status()
        await analysis.save()
    return AnalysisResponse.from_doc(analysis)


@router.delete("/{analysis_id}/papers/{paper_id}", response_model=AnalysisResponse)
async def remove_paper(analysis_id: PydanticObjectId, paper_id: PydanticObjectId) -> AnalysisResponse:
    analysis = await Analysis.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    now = datetime.now(timezone.utc)
    # its queued run is cancelled and its running run stopped; its impacts stay as they are
    stopped = [
        r for r in analysis.runs
        if r.paper_id == str(paper_id) and r.status in (RunStatus.QUEUED, RunStatus.RUNNING)
    ]
    for run in stopped:
        run.status, run.completed_at = RunStatus.CANCELLED, now
    analysis.paper_ids = [pid for pid in analysis.paper_ids if pid != paper_id]
    analysis.refresh_status()
    await analysis.save()
    for run in stopped:
        run_queue.stop(run.id)
    await write_events(analysis_id, [
        Event(at=now, actor=ActorKind.SYSTEM, action="run_cancelled", run_id=r.id, note="paper removed")
        for r in stopped
    ])
    return AnalysisResponse.from_doc(analysis)


def _ai_counts(analysis: Analysis, papers: Set[str]) -> Tuple[int, int]:
    active = [
        i for i in analysis.visible_impacts()
        if i.paper_id in papers and i.state == ImpactState.ACTIVE and i.origin == ImpactOrigin.AI
    ]
    verified = sum(1 for i in active if i.verified)
    return verified, len(active) - verified


@router.post("/{analysis_id}/run", response_model=AnalysisResponse)
async def run_analysis(
    analysis_id: PydanticObjectId,
    paper_id: Optional[List[PydanticObjectId]] = Query(
        default=None, description="Papers to run; every paper of the analysis when omitted"
    ),
    verified: Optional[VerifiedChoice] = Query(
        default=None, description="Keep or discard verified AI impacts; required when the papers to run have any"
    ),
):
    """Queue one run per paper. Papers already queued or running keep their run and are not queued again."""
    analysis = await Analysis.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if not analysis.paper_ids:
        raise HTTPException(status_code=400, detail="No papers added to this analysis")
    requested = list(dict.fromkeys(str(p) for p in (paper_id or analysis.paper_ids)))
    states = analysis.run_states()
    if any(p not in states for p in requested):
        raise HTTPException(status_code=400, detail="Paper is not part of this analysis")
    to_queue = [p for p in requested if not states[p].locked]
    n_verified, n_unverified = _ai_counts(analysis, set(to_queue))
    if n_verified and verified is None:
        return JSONResponse(status_code=409, content={
            "detail": "The papers have verified impacts; choose verified=keep or verified=discard",
            "verified": n_verified,
            "unverified": n_unverified,
        })
    now = datetime.now(timezone.utc)
    runs = [AnalysisRun(paper_id=p, queued_at=now, model=settings.model, verified_choice=verified) for p in to_queue]
    if runs:
        analysis.runs.extend(runs)
        analysis.refresh_status()
        await analysis.save()
        await write_events(analysis_id, [
            Event(
                at=now, actor=ActorKind.SYSTEM, action="run_queued", run_id=r.id,
                note=f"verified={verified.value}" if verified else None,
            )
            for r in runs
        ])
        run_queue.wake(analysis_id)
    return AnalysisResponse.from_doc(analysis)


@router.post("/{analysis_id}/runs/{run_id}/cancel", response_model=AnalysisResponse)
async def cancel_run(analysis_id: PydanticObjectId, run_id: str) -> AnalysisResponse:
    analysis = await Analysis.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    run = next((r for r in analysis.runs if r.id == run_id), None)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != RunStatus.QUEUED:
        raise HTTPException(status_code=409, detail="Only a queued run can be cancelled")
    run.status, run.completed_at = RunStatus.CANCELLED, datetime.now(timezone.utc)
    analysis.refresh_status()
    await analysis.save()  # a run the queue started meanwhile fails the revision check: 409
    await write_events(analysis_id, [Event(
        at=run.completed_at, actor=ActorKind.SYSTEM, action="run_cancelled", run_id=run.id,
    )])
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


async def _analysis(analysis_id: PydanticObjectId) -> Analysis:
    analysis = await Analysis.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


def _check_reviewable(analysis: Analysis, paper_id: str) -> None:
    state = analysis.run_states().get(paper_id)
    if state is not None and state.locked:
        raise HTTPException(status_code=409, detail="Impacts of this paper cannot be reviewed while it is queued or running")


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
    await write_events(analysis.id, events)
    return AnalysisResponse.from_doc(analysis)


@router.post("/{analysis_id}/impacts", response_model=AnalysisResponse, status_code=201)
async def create_impact(analysis_id: PydanticObjectId, body: ImpactCreate) -> AnalysisResponse:
    analysis = await _analysis(analysis_id)
    if body.paper_id not in {str(p) for p in analysis.paper_ids}:
        raise HTTPException(status_code=422, detail="Paper is not part of this analysis")
    _check_reviewable(analysis, body.paper_id)
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
    analysis = await _analysis(analysis_id)
    impact = _impact(analysis, impact_id)
    _check_reviewable(analysis, impact.paper_id)
    spans = None if body.evidence is None else await _validated_spans(impact.paper_id, body.evidence)
    fields = body.fields.model_dump(exclude_unset=True) if body.fields else {}
    return await _review(analysis, lambda: review.edit_impact(
        impact, fields, spans, body.verified, body.note, datetime.now(timezone.utc)
    ))


@router.post("/{analysis_id}/impacts/{impact_id}/remove", response_model=AnalysisResponse)
async def remove_impact(analysis_id: PydanticObjectId, impact_id: str, body: ReviewNote = ReviewNote()) -> AnalysisResponse:
    analysis = await _analysis(analysis_id)
    impact = _impact(analysis, impact_id)
    _check_reviewable(analysis, impact.paper_id)
    return await _review(analysis, lambda: review.remove_impact(impact, body.note, datetime.now(timezone.utc)))


@router.post("/{analysis_id}/impacts/{impact_id}/restore", response_model=AnalysisResponse)
async def restore_impact(analysis_id: PydanticObjectId, impact_id: str, body: ReviewNote = ReviewNote()) -> AnalysisResponse:
    analysis = await _analysis(analysis_id)
    impact = _impact(analysis, impact_id)
    _check_reviewable(analysis, impact.paper_id)
    return await _review(analysis, lambda: review.restore_impact(impact, body.note, datetime.now(timezone.utc)))


@router.get("/{analysis_id}/audit", response_model=List[AuditEvent])
async def get_audit(analysis_id: PydanticObjectId, impact_id: Optional[str] = None) -> List[AuditEvent]:
    """Audit events oldest first, optionally for one impact. Available after the analysis is deleted."""
    query = AuditEvent.find(AuditEvent.analysis_id == analysis_id)
    if impact_id is not None:
        query = query.find(AuditEvent.impact_id == impact_id)
    return await query.sort(+AuditEvent.at, +AuditEvent.id).to_list()
