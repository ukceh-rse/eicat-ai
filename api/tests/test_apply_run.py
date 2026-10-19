from datetime import datetime, timezone

from eicat_ai.models import (
    ActorKind,
    Category,
    EvidenceSpan,
    Impact,
    ImpactOrigin,
    ImpactState,
    Mechanism,
    ReviewedImpact,
    VerifiedChoice,
)
from eicat_ai.review import apply_run, as_found

NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)
P = "paper-1"


def ai(mechanism=Mechanism.PREDATION, category=Category.MODERATE, evidence="Rats ate eggs."):
    return Impact(
        alien_species="Rattus rattus", mechanism=mechanism, category=category,
        evidence=evidence, justification="j", impacted_species=["Petrel"],
    )


def existing(mechanism=Mechanism.PREDATION, origin=ImpactOrigin.AI, verified=False, state=ImpactState.ACTIVE):
    impact = ai(mechanism)
    return ReviewedImpact(
        paper_id=P, origin=origin, run_id="run-0", ai=impact if origin == ImpactOrigin.AI else None,
        current=impact, verified=verified or origin == ImpactOrigin.HUMAN, state=state,
    )


def extracted(*impacts, paper=P):
    return {paper: [(i, [EvidenceSpan(start=0, end=4, text=i.evidence[:4])]) for i in impacts]}


def run(impacts, new, choice=None, run_id="run-1"):
    return apply_run(impacts, new, run_id, choice, NOW)


def active(impacts):
    return [i for i in impacts if i.state == ImpactState.ACTIVE]


def by_state(impacts, state):
    return [i for i in impacts if i.state == state]


def test_unverified_ai_impact_is_superseded_and_replaced():
    old = existing()
    impacts, events = run([old], extracted(ai(category=Category.MAJOR)))
    assert next(i for i in impacts if i.id == old.id).state == ImpactState.SUPERSEDED
    [new] = active(impacts)
    assert (new.origin, new.run_id, new.verified, new.current.category) == (ImpactOrigin.AI, "run-1", False, Category.MAJOR)
    # the current evidence is the paper text the spans cover; the AI's wording stays on `ai`
    assert new.current == new.ai.model_copy(update={"evidence": "Rats"}) and new.evidence[0].text == "Rats"
    superseded = next(e for e in events if e.action == "superseded")
    assert (superseded.actor, superseded.impact_id, superseded.run_id) == (ActorKind.SYSTEM, old.id, "run-1")
    assert superseded.changes[0].model_dump() == {"field": "state", "old": "active", "new": "superseded"}
    created = next(e for e in events if e.action == "created")
    assert (created.actor, created.impact_id) == (ActorKind.AI, new.id)


def test_input_is_not_mutated():
    old = existing()
    run([old], extracted(ai()))
    assert old.state == ImpactState.ACTIVE


def test_keep_verified():
    old = existing(verified=True)
    impacts, _ = run([old], extracted(ai(Mechanism.COMPETITION)), VerifiedChoice.KEEP)
    kept = next(i for i in impacts if i.id == old.id)
    assert (kept.state, kept.verified) == (ImpactState.ACTIVE, True)


def test_discard_verified():
    old = existing(verified=True)
    impacts, _ = run([old], extracted(ai(Mechanism.COMPETITION)), VerifiedChoice.DISCARD)
    assert next(i for i in impacts if i.id == old.id).state == ImpactState.SUPERSEDED


def test_discard_keeps_human_created_and_removed():
    human = existing(Mechanism.COMPETITION, origin=ImpactOrigin.HUMAN)
    removed = existing(Mechanism.HYBRIDISATION, state=ImpactState.REMOVED)
    impacts, events = run([human, removed], {}, VerifiedChoice.DISCARD)
    assert next(i for i in impacts if i.id == human.id).state == ImpactState.ACTIVE
    assert next(i for i in impacts if i.id == removed.id).state == ImpactState.REMOVED
    assert events == []


def test_superseded_impacts_stay_superseded():
    old = existing(state=ImpactState.SUPERSEDED)
    impacts, _ = run([old], extracted(ai()))
    assert next(i for i in impacts if i.id == old.id).state == ImpactState.SUPERSEDED
    assert len(active(impacts)) == 1


def test_unheld_key_becomes_active_unverified():
    holder = existing(verified=True)
    impacts, _ = run([holder], extracted(ai(Mechanism.COMPETITION)), VerifiedChoice.KEEP)
    [new] = [i for i in active(impacts) if i.id != holder.id]
    assert (new.current.mechanism, new.verified) == (Mechanism.COMPETITION, False)


def test_suppressed_by_verified():
    holder = existing(verified=True)
    impacts, events = run([holder], extracted(ai()), VerifiedChoice.KEEP)
    assert [i.id for i in active(impacts)] == [holder.id]
    [record] = by_state(impacts, ImpactState.SUPPRESSED)
    assert record.held_by == holder.id
    assert [(s.run_id, s.ai.category) for s in record.sightings] == [("run-1", Category.MODERATE)]
    assert record.sightings[0].evidence[0].text == "Rats"
    assert [e.action for e in events if e.impact_id == record.id] == ["created", "suppressed"]
    assert next(e for e in events if e.action == "suppressed").actor == ActorKind.SYSTEM


def test_suppressed_by_human_created():
    holder = existing(origin=ImpactOrigin.HUMAN)
    impacts, _ = run([holder], extracted(ai()), VerifiedChoice.DISCARD)
    [record] = by_state(impacts, ImpactState.SUPPRESSED)
    assert record.held_by == holder.id
    assert [i.id for i in active(impacts)] == [holder.id]


def test_suppressed_by_removed():
    holder = existing(state=ImpactState.REMOVED)
    impacts, _ = run([holder], extracted(ai()))
    assert active(impacts) == []
    [record] = by_state(impacts, ImpactState.SUPPRESSED)
    assert record.held_by == holder.id


def test_active_holder_preferred_over_removed():
    removed = existing(state=ImpactState.REMOVED)
    verified = existing(verified=True)
    impacts, _ = run([removed, verified], extracted(ai()), VerifiedChoice.KEEP)
    [record] = by_state(impacts, ImpactState.SUPPRESSED)
    assert record.held_by == verified.id


def test_key_comes_from_current_mechanism():
    edited = existing(verified=True)
    edited.current = edited.current.model_copy(update={"mechanism": Mechanism.COMPETITION})
    impacts, _ = run([edited], extracted(ai(Mechanism.PREDATION), ai(Mechanism.COMPETITION)), VerifiedChoice.KEEP)
    assert {i.current.mechanism for i in active(impacts)} == {Mechanism.COMPETITION, Mechanism.PREDATION}
    [record] = by_state(impacts, ImpactState.SUPPRESSED)
    assert record.current.mechanism == Mechanism.COMPETITION


def test_key_is_per_paper():
    holder = existing(verified=True)
    impacts, _ = run([holder], extracted(ai(), paper="paper-2"), VerifiedChoice.KEEP)
    assert by_state(impacts, ImpactState.SUPPRESSED) == []
    assert {i.paper_id for i in active(impacts)} == {P, "paper-2"}


def test_one_suppressed_record_accumulates_sightings():
    holder = existing(verified=True)
    impacts, _ = run([holder], extracted(ai(category=Category.MODERATE)), VerifiedChoice.KEEP, "run-1")
    impacts, events = run(impacts, extracted(ai(category=Category.MAJOR)), VerifiedChoice.KEEP, "run-2")
    [record] = by_state(impacts, ImpactState.SUPPRESSED)
    assert [(s.run_id, s.ai.category) for s in record.sightings] == [("run-1", Category.MODERATE), ("run-2", Category.MAJOR)]
    # the record mirrors its latest sighting
    assert (record.run_id, record.ai.category, record.current.category) == ("run-2", Category.MAJOR, Category.MAJOR)
    [sighted] = [e for e in events if e.impact_id == record.id]
    assert (sighted.action, sighted.actor, sighted.changes) == ("sighted", ActorKind.AI, [])


def test_sighting_follows_a_new_holder():
    holder = existing(verified=True)
    impacts, _ = run([holder], extracted(ai()), VerifiedChoice.KEEP, "run-1")
    for i in impacts:
        if i.id == holder.id:
            i.state = ImpactState.REMOVED
    human = existing(origin=ImpactOrigin.HUMAN)
    impacts, events = run(impacts + [human], extracted(ai()), VerifiedChoice.KEEP, "run-2")
    [record] = by_state(impacts, ImpactState.SUPPRESSED)
    assert record.held_by == human.id
    [sighted] = [e for e in events if e.impact_id == record.id]
    assert sighted.changes[0].model_dump() == {"field": "held_by", "old": holder.id, "new": human.id}


def test_as_found_takes_paper_text_of_anchored_spans():
    quote = ai(evidence="Rats were said to eat eggs.")
    spans = [EvidenceSpan(start=0, end=4, text="Rats", approximate=True), EvidenceSpan(start=9, end=13, text="eggs")]
    assert as_found(quote, spans).evidence == "Rats\n\neggs"
    assert quote.evidence == "Rats were said to eat eggs."
    assert as_found(quote, []).evidence == quote.evidence


def test_run_created_impacts_have_unedited_evidence():
    impacts, _ = run([], extracted(ai()))
    assert [i.evidence_edited for i in impacts] == [False]


def test_as_found_keeps_ai_text_only_for_unanchored_spans():
    quote = ai(evidence="Rats ate eggs. Eggs vanished. Moons are cheese.")
    spans = [
        EvidenceSpan(start=0, end=4, text="Rats"),
        EvidenceSpan(start=9, end=13, text="eggs", approximate=True),
        EvidenceSpan(text="Moons are cheese."),
    ]
    assert as_found(quote, spans).evidence == "Rats\n\neggs\n\nMoons are cheese."
