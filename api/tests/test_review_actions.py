from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from eicat_ai.models import (
    ActorKind,
    Category,
    EvidenceSpan,
    Impact,
    ImpactOrigin,
    ImpactState,
    Mechanism,
    ReviewedImpact,
)
from eicat_ai.review import ReviewError, create_impact, edit_impact, remove_impact, restore_impact

NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)
SPANS = [EvidenceSpan(start=0, end=4, text="Rats")]


def ai_impact(**kwargs):
    impact = Impact(
        alien_species="Rattus rattus", mechanism=Mechanism.PREDATION, category=Category.MODERATE,
        evidence="Rats ate eggs.", justification="j", impacted_species=["Petrel"],
    )
    return ReviewedImpact(paper_id="p", origin=ImpactOrigin.AI, run_id="r", ai=impact, current=impact, evidence=SPANS, **kwargs)


def changes(event):
    return [(c.field, c.old, c.new) for c in event.changes]


def test_edit_records_old_and_new_and_auto_verifies():
    impact = ai_impact()
    events = edit_impact(impact, {"category": "MR", "reversibility": "reversible"}, None, None, "seen in fig 2", NOW)
    assert [e.action for e in events] == ["updated", "verified"]
    updated, verified = events
    assert changes(updated) == [("category", "MO", "MR"), ("reversibility", None, "reversible")]
    assert (updated.actor, updated.note, updated.impact_id) == (ActorKind.HUMAN, "seen in fig 2", impact.id)
    assert changes(verified) == [("verified", False, True)]
    assert impact.verified and impact.current.category == Category.MAJOR
    # the AI snapshot is untouched
    assert impact.ai.category == Category.MODERATE


def test_edit_of_verified_impact_logs_no_verify_event():
    impact = ai_impact(verified=True)
    events = edit_impact(impact, {"mechanism": "Competition"}, None, None, None, NOW)
    assert [e.action for e in events] == ["updated"]
    assert changes(events[0]) == [("mechanism", "Predation", "Competition")]


def test_edit_cannot_unverify():
    impact = ai_impact()
    events = edit_impact(impact, {"confidence": "High"}, None, False, None, NOW)
    assert impact.verified
    assert [e.action for e in events] == ["updated", "verified"]


def test_evidence_change_records_spans_and_recomputes_text():
    impact = ai_impact()
    new = [EvidenceSpan(start=10, end=14, text="eggs"), EvidenceSpan(start=20, end=24, text="nest")]
    events = edit_impact(impact, {}, new, None, None, NOW)
    [evidence] = events[0].changes
    assert evidence.field == "evidence"
    assert evidence.old == [{"start": 0, "end": 4, "text": "Rats", "approximate": False}]
    assert [s["text"] for s in evidence.new] == ["eggs", "nest"]
    assert impact.current.evidence == "eggs\n\nnest"
    assert impact.verified
    assert impact.evidence_edited


def test_accepting_approximate_spans_is_not_an_evidence_edit():
    impact = ai_impact()
    impact.evidence = [s.model_copy(update={"approximate": True}) for s in SPANS]
    events = edit_impact(impact, {}, [s.model_copy(update={"approximate": False}) for s in SPANS], None, None, NOW)
    assert [s.approximate for s in impact.evidence] == [False] * len(SPANS)
    assert not impact.evidence_edited
    assert [e.action for e in events] == ["updated", "verified"]


def test_field_edit_leaves_evidence_unedited():
    impact = ai_impact()
    edit_impact(impact, {"mechanism": "Competition"}, None, None, None, NOW)
    assert not impact.evidence_edited


def test_unchanged_fields_are_not_an_edit():
    impact = ai_impact()
    assert edit_impact(impact, {"category": "MO"}, None, None, None, NOW) == []
    assert not impact.verified


def test_verify_and_unverify():
    impact = ai_impact()
    [event] = edit_impact(impact, {}, None, True, "checked", NOW)
    assert (event.action, changes(event), event.note) == ("verified", [("verified", False, True)], "checked")
    [event] = edit_impact(impact, {}, None, False, None, NOW)
    assert (event.action, changes(event)) == ("unverified", [("verified", True, False)])
    assert not impact.verified


def test_reversibility_cleared_outside_mr_mv():
    impact = ai_impact()
    edit_impact(impact, {"category": "MV", "reversibility": "irreversible"}, None, None, None, NOW)
    [event] = edit_impact(impact, {"category": "MN"}, None, None, None, NOW)
    assert changes(event) == [("category", "MV", "MN"), ("reversibility", "irreversible", None)]


def test_invalid_category_rejected_and_impact_unchanged():
    impact = ai_impact()
    with pytest.raises(ValidationError):
        edit_impact(impact, {"category": "XX"}, None, None, None, NOW)
    assert impact.current.category == Category.MODERATE and not impact.verified


def test_only_active_impacts_editable():
    with pytest.raises(ReviewError):
        edit_impact(ai_impact(state=ImpactState.REMOVED), {"category": "MR"}, None, None, None, NOW)


def test_human_impact_cannot_be_unverified():
    impact, _ = create_impact("p", {"alien_species": "R", "mechanism": "Predation", "category": "MO", "justification": "", "impacted_species": []}, SPANS, None, NOW)
    with pytest.raises(ReviewError):
        edit_impact(impact, {}, None, False, None, NOW)


def test_create_human_impact():
    impact, [event] = create_impact(
        "p", {"alien_species": "R", "mechanism": "Predation", "category": "MO", "reversibility": "reversible",
              "justification": "", "impacted_species": ["Petrel"]}, SPANS, "missed by AI", NOW,
    )
    assert (impact.origin, impact.ai, impact.verified, impact.state) == (ImpactOrigin.HUMAN, None, True, ImpactState.ACTIVE)
    assert impact.current.evidence == "Rats" and impact.current.reversibility is None
    assert (event.action, event.actor, event.note) == ("created", ActorKind.HUMAN, "missed by AI")


def test_create_requires_fields():
    with pytest.raises(ValidationError):
        create_impact("p", {"mechanism": "Predation"}, SPANS, None, NOW)


def test_remove_and_restore_keep_values():
    impact = ai_impact(verified=True)
    [removed] = remove_impact(impact, "not caused by the alien species", NOW)
    assert impact.state == ImpactState.REMOVED
    assert (removed.action, removed.note, changes(removed)) == ("removed", "not caused by the alien species", [("state", "active", "removed")])
    [restored] = restore_impact(impact, None, NOW)
    assert (impact.state, impact.verified, impact.current.category) == (ImpactState.ACTIVE, True, Category.MODERATE)
    assert changes(restored) == [("state", "removed", "active")]


def test_restore_suppressed_makes_it_verified():
    impact = ai_impact(state=ImpactState.SUPPRESSED, held_by="h")
    [event] = restore_impact(impact, None, NOW)
    assert (impact.state, impact.verified, impact.held_by) == (ImpactState.ACTIVE, True, None)
    assert changes(event) == [("state", "suppressed", "active"), ("held_by", "h", None), ("verified", False, True)]


@pytest.mark.parametrize("state", [ImpactState.ACTIVE, ImpactState.SUPERSEDED])
def test_restore_requires_removed_or_suppressed(state):
    with pytest.raises(ReviewError):
        restore_impact(ai_impact(state=state), None, NOW)


def test_remove_requires_active():
    with pytest.raises(ReviewError):
        remove_impact(ai_impact(state=ImpactState.SUPPRESSED), None, NOW)
