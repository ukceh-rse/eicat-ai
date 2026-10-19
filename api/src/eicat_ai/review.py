"""Review-layer rules, kept free of I/O so they can be unit tested: re-run merge and suppression (design D3) and the
audit events each change produces."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from beanie import PydanticObjectId
from pydantic import BaseModel, Field

from eicat_ai.anchoring import evidence_text
from eicat_ai.models import (
    Actor,
    ActorKind,
    AuditEvent,
    Category,
    EvidenceSpan,
    FieldChange,
    Impact,
    ImpactOrigin,
    ImpactState,
    ReviewedImpact,
    Sighting,
    VerifiedChoice,
)

# a run's anchored extractions, per paper id
Extracted = Dict[str, List[Tuple[Impact, List[EvidenceSpan]]]]


class Event(BaseModel):
    """An audit event before it is bound to its analysis."""

    at: datetime
    actor: ActorKind
    action: str
    impact_id: Optional[str] = None
    run_id: Optional[str] = None
    changes: List[FieldChange] = Field(default_factory=list)
    note: Optional[str] = None

    def to_document(self, analysis_id: PydanticObjectId) -> AuditEvent:
        return AuditEvent(
            at=self.at,
            analysis_id=analysis_id,
            impact_id=self.impact_id,
            run_id=self.run_id,
            actor=Actor(kind=self.actor),
            action=self.action,
            changes=self.changes,
            note=self.note,
        )


def _state_change(old: ImpactState, new: ImpactState) -> List[FieldChange]:
    return [FieldChange(field="state", old=old.value, new=new.value)]


def holds_key(impact: ReviewedImpact) -> bool:
    """Expert decisions hold their (paper, mechanism) key against new AI impacts."""
    if impact.state == ImpactState.REMOVED:
        return True
    return impact.state == ImpactState.ACTIVE and (impact.verified or impact.origin == ImpactOrigin.HUMAN)


def as_found(ai: Impact, spans: List[EvidenceSpan]) -> Impact:
    """An AI impact as reviewed: its evidence is its spans' texts, so each anchored span shows the paper text it
    covers even where the AI paraphrased, and only an unanchored span keeps the AI's sentence; the AI's own wording
    stays on `ai`."""
    current = ai.model_copy(deep=True)
    if spans:
        current.evidence = evidence_text(spans)
    return current


def apply_run(
    impacts: List[ReviewedImpact],
    new_by_paper: Extracted,
    run_id: str,
    verified_choice: Optional[VerifiedChoice],
    now: datetime,
) -> Tuple[List[ReviewedImpact], List[Event]]:
    impacts = [i.model_copy(deep=True) for i in impacts]
    events: List[Event] = []

    for imp in impacts:
        if imp.state != ImpactState.ACTIVE or imp.origin != ImpactOrigin.AI:
            continue
        if not imp.verified or verified_choice == VerifiedChoice.DISCARD:
            imp.state = ImpactState.SUPERSEDED
            events.append(Event(
                at=now, actor=ActorKind.SYSTEM, action="superseded", impact_id=imp.id, run_id=run_id,
                changes=_state_change(ImpactState.ACTIVE, ImpactState.SUPERSEDED),
            ))

    # an active holder is the one to point at when a removed impact shares its key
    holders = {i.key: i for i in impacts if holds_key(i) and i.state == ImpactState.REMOVED}
    holders.update({i.key: i for i in impacts if holds_key(i) and i.state == ImpactState.ACTIVE})
    suppressed = {i.key: i for i in impacts if i.state == ImpactState.SUPPRESSED}

    for paper_id, extracted in new_by_paper.items():
        for ai, spans in extracted:
            key = (paper_id, ai.mechanism)
            holder = holders.get(key)
            if holder is None:
                imp = ReviewedImpact(
                    paper_id=paper_id, origin=ImpactOrigin.AI, run_id=run_id,
                    ai=ai, current=as_found(ai, spans), evidence=spans,
                )
                impacts.append(imp)
                events.append(Event(at=now, actor=ActorKind.AI, action="created", impact_id=imp.id, run_id=run_id))
                continue
            sighting = Sighting(run_id=run_id, at=now, ai=ai, evidence=spans)
            record = suppressed.get(key)
            if record is None:
                record = ReviewedImpact(
                    paper_id=paper_id, origin=ImpactOrigin.AI, run_id=run_id,
                    ai=ai, current=as_found(ai, spans), evidence=spans,
                    state=ImpactState.SUPPRESSED, held_by=holder.id, sightings=[sighting],
                )
                impacts.append(record)
                suppressed[key] = record
                events.append(Event(at=now, actor=ActorKind.AI, action="created", impact_id=record.id, run_id=run_id))
                events.append(Event(
                    at=now, actor=ActorKind.SYSTEM, action="suppressed", impact_id=record.id, run_id=run_id,
                    changes=[FieldChange(field="held_by", old=None, new=holder.id)],
                ))
                continue
            # the record mirrors its latest sighting, so restoring it needs only a state change
            changes = [FieldChange(field="held_by", old=record.held_by, new=holder.id)] if record.held_by != holder.id else []
            record.sightings.append(sighting)
            record.run_id, record.ai, record.current, record.evidence = run_id, ai, as_found(ai, spans), spans
            record.held_by = holder.id
            events.append(Event(
                at=now, actor=ActorKind.AI, action="sighted", impact_id=record.id, run_id=run_id, changes=changes,
            ))

    return impacts, events


# ---------------------------------------------------------------------------
# Review actions. Each mutates the impact it is given and returns the events to log.
# ---------------------------------------------------------------------------

REVERSIBILITY_CATEGORIES = {Category.MAJOR, Category.MASSIVE}


class ReviewError(ValueError):
    """A review action that the impact's current state does not allow."""


def impact_changes(before: ReviewedImpact, after: ReviewedImpact) -> List[FieldChange]:
    """Changed impact fields with old and new values. Evidence is compared as spans; `current.evidence` is derived."""
    old, new = before.current.model_dump(mode="json"), after.current.model_dump(mode="json")
    changes = [FieldChange(field=k, old=old[k], new=new[k]) for k in old if k != "evidence" and old[k] != new[k]]
    old_spans = [s.model_dump() for s in before.evidence]
    new_spans = [s.model_dump() for s in after.evidence]
    if old_spans != new_spans:
        changes.append(FieldChange(field="evidence", old=old_spans, new=new_spans))
    return changes


def _verify(impact: ReviewedImpact, verified: bool, now: datetime) -> Event:
    old = impact.verified
    impact.verified = verified
    return Event(
        at=now, actor=ActorKind.HUMAN, action="verified" if verified else "unverified", impact_id=impact.id,
        changes=[FieldChange(field="verified", old=old, new=verified)],
    )


def edit_impact(
    impact: ReviewedImpact,
    fields: Dict[str, Any],
    evidence: Optional[List[EvidenceSpan]],
    verified: Optional[bool],
    note: Optional[str],
    now: datetime,
) -> List[Event]:
    """Apply a reviewer's edit. Changing any field or the evidence verifies the impact, logged as its own event so
    the log shows the verification came from the edit. Raises pydantic.ValidationError on invalid values."""
    if impact.state != ImpactState.ACTIVE:
        raise ReviewError(f"Only active impacts can be edited; this impact is {impact.state.value}")
    if verified is False and impact.origin == ImpactOrigin.HUMAN:
        raise ReviewError("Human-created impacts are always verified")
    before = impact.model_copy(deep=True)
    current = Impact.model_validate({**impact.current.model_dump(), **fields})
    if current.category not in REVERSIBILITY_CATEGORIES:
        current.reversibility = None
    if evidence is not None:
        impact.evidence = evidence
        current.evidence = evidence_text(evidence)
    impact.current = current
    events: List[Event] = []
    changes = impact_changes(before, impact)
    # accepting approximate spans as they are clears their flag, but isn't a change of evidence
    if [(s.start, s.end, s.text) for s in before.evidence] != [(s.start, s.end, s.text) for s in impact.evidence]:
        impact.evidence_edited = True
    if changes:
        events.append(Event(
            at=now, actor=ActorKind.HUMAN, action="updated", impact_id=impact.id, changes=changes, note=note,
        ))
        if not impact.verified:
            events.append(_verify(impact, True, now))
    elif verified is not None and verified != impact.verified:
        event = _verify(impact, verified, now)
        event.note = note
        events.append(event)
    return events


def create_impact(
    paper_id: str, fields: Dict[str, Any], evidence: List[EvidenceSpan], note: Optional[str], now: datetime
) -> Tuple[ReviewedImpact, List[Event]]:
    """A reviewer's own impact: origin human, no AI snapshot, verified. Raises pydantic.ValidationError."""
    current = Impact.model_validate({**fields, "evidence": evidence_text(evidence)})
    if current.category not in REVERSIBILITY_CATEGORIES:
        current.reversibility = None
    impact = ReviewedImpact(
        paper_id=paper_id, origin=ImpactOrigin.HUMAN, current=current, evidence=evidence, verified=True,
    )
    return impact, [Event(at=now, actor=ActorKind.HUMAN, action="created", impact_id=impact.id, note=note)]


def remove_impact(impact: ReviewedImpact, note: Optional[str], now: datetime) -> List[Event]:
    if impact.state != ImpactState.ACTIVE:
        raise ReviewError(f"Only active impacts can be removed; this impact is {impact.state.value}")
    impact.state = ImpactState.REMOVED
    return [Event(
        at=now, actor=ActorKind.HUMAN, action="removed", impact_id=impact.id,
        changes=_state_change(ImpactState.ACTIVE, ImpactState.REMOVED), note=note,
    )]


def restore_impact(impact: ReviewedImpact, note: Optional[str], now: datetime) -> List[Event]:
    """Removed impacts return with the values they had. Suppressed impacts already mirror their latest sighting, and
    become verified, since restoring one is an expert decision."""
    old = impact.state
    if old == ImpactState.REMOVED:
        changes = _state_change(old, ImpactState.ACTIVE)
    elif old == ImpactState.SUPPRESSED:
        changes = _state_change(old, ImpactState.ACTIVE) + [FieldChange(field="held_by", old=impact.held_by, new=None)]
        if not impact.verified:
            changes.append(FieldChange(field="verified", old=False, new=True))
        impact.verified, impact.held_by = True, None
    else:
        raise ReviewError(f"Only removed or suppressed impacts can be restored; this impact is {old.value}")
    impact.state = ImpactState.ACTIVE
    return [Event(at=now, actor=ActorKind.HUMAN, action="restored", impact_id=impact.id, changes=changes, note=note)]
