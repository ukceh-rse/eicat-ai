"""API-level tests for the review layer, against an in-memory Mongo (mongomock-motor)."""

import asyncio

import pytest
from beanie import PydanticObjectId, init_beanie
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from eicat_ai.main import app
from eicat_ai import run_queue
from eicat_ai.migration import INTERRUPTED, migrate_legacy_analyses, reanchor_evidence, recover_runs
from eicat_ai.models import (
    Actor,
    ActorKind,
    Analysis,
    AnalysisRun,
    AnalysisStatus,
    AuditEvent,
    Category,
    EvidenceSpan,
    FieldChange,
    Impact,
    ImpactOrigin,
    ImpactState,
    Mechanism,
    PaperDoc,
    PaperStatus,
    ReviewedImpact,
    RunStatus,
    Sighting,
    SpeciesNames,
    VerifiedChoice,
)

MARKDOWN = "Introduction.\n\nRats ate the eggs of petrels on the island.\n\nDiscussion."
EVIDENCE = "Rats ate the eggs of petrels on the island."

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    await init_beanie(database=AsyncMongoMockClient()["test"], document_models=[PaperDoc, Analysis, AuditEvent])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def ai(mechanism=Mechanism.PREDATION):
    return Impact(
        alien_species="Rattus rattus", mechanism=mechanism, category=Category.MODERATE,
        evidence=EVIDENCE, justification="j", impacted_species=["Petrel"],
    )


async def paper(tag=None) -> PaperDoc:
    doc = PaperDoc(filename="p.pdf", content_type="application/pdf", size=1, pdf_data=b"", status=PaperStatus.READY,
                   markdown=MARKDOWN if tag is None else f"{MARKDOWN}\n\n{tag}")
    await doc.insert()
    return doc


async def analysis_with(*impacts_for, status=AnalysisStatus.COMPLETED) -> tuple[Analysis, str]:
    """An analysis on one paper, holding one AI impact per (verified, state) pair given."""
    doc = await paper()
    pid = str(doc.id)
    impacts = [
        ReviewedImpact(paper_id=pid, origin=ImpactOrigin.AI, run_id="r0", ai=ai(), current=ai(), verified=v, state=s)
        for v, s in impacts_for
    ]
    analysis = Analysis(species=SpeciesNames(scientific_name="Rattus rattus"), paper_ids=[doc.id], impacts=impacts,
                        status=status)
    await analysis.insert()
    return analysis, pid


class FakeExtraction:
    """Extraction keyed by the tag on a paper's last line: records calls, can hold a paper until released, or fail."""

    def __init__(self):
        self.calls: list[str] = []
        self.gates: dict[str, asyncio.Event] = {}
        self.fail: set[str] = set()
        self.active = self.max_active = 0

    def hold(self, tag):
        self.gates[tag] = asyncio.Event()
        return self.gates[tag]

    async def __call__(self, agent, paper, species):
        tag = paper.content.rsplit("\n", 1)[-1]
        self.calls.append(tag)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            if tag in self.gates:
                await self.gates[tag].wait()
            if tag in self.fail:
                raise RuntimeError(f"extraction of {tag} failed")
            return [ai(Mechanism.COMPETITION)], {"input_tokens": 3}
        finally:
            self.active -= 1


@pytest.fixture
def fake_extraction(monkeypatch):
    fake = FakeExtraction()
    monkeypatch.setattr(run_queue, "data_extraction_agent", lambda model: None)
    monkeypatch.setattr(run_queue, "extract_impacts", fake)
    return fake


async def analysis_of(*tags, impacts=()) -> tuple[Analysis, list[str]]:
    """An analysis on one paper per tag; `impacts` are (tag, verified) pairs, each an active AI impact."""
    docs = [await paper(tag) for tag in tags]
    pids = [str(d.id) for d in docs]
    by_tag = dict(zip(tags, pids))
    analysis = Analysis(
        species=SpeciesNames(scientific_name="Rattus rattus"), paper_ids=[d.id for d in docs],
        impacts=[
            ReviewedImpact(paper_id=by_tag[t], origin=ImpactOrigin.AI, run_id="r0", ai=ai(), current=ai(), verified=v)
            for t, v in impacts
        ],
    )
    await analysis.insert()
    return analysis, pids


async def until(predicate):
    for _ in range(200):
        if await predicate():
            return
        await asyncio.sleep(0.005)
    raise AssertionError("condition not reached")


async def paper_state(analysis_id, pid):
    return (await Analysis.get(analysis_id)).run_states()[pid].state


async def run_of(analysis_id, pid):
    [run] = [r for r in (await Analysis.get(analysis_id)).runs if r.paper_id == pid]
    return run


# --- run -------------------------------------------------------------------


async def test_run_without_choice_over_verified_impacts_is_refused(client):
    analysis, _ = await analysis_with((True, ImpactState.ACTIVE), (False, ImpactState.ACTIVE))
    r = await client.post(f"/analyses/{analysis.id}/run")
    assert r.status_code == 409
    assert (r.json()["verified"], r.json()["unverified"]) == (1, 1)
    stored = await Analysis.get(analysis.id)
    assert stored.runs == [] and stored.status == AnalysisStatus.COMPLETED


async def test_run_without_verified_impacts_needs_no_choice(client, fake_extraction):
    analysis, pid = await analysis_with((False, ImpactState.ACTIVE))
    r = await client.post(f"/analyses/{analysis.id}/run")
    assert r.status_code == 200
    assert r.json()["status"] == "running" and r.json()["paper_runs"][pid]["state"] == "queued"
    await run_queue.idle()
    stored = await Analysis.get(analysis.id)
    assert stored.status == AnalysisStatus.COMPLETED
    assert [(run.paper_id, run.status, run.usage) for run in stored.runs] == [(pid, RunStatus.COMPLETED, {"input_tokens": 3})]
    assert [i.current.mechanism for i in stored.impacts if i.state == ImpactState.ACTIVE] == [Mechanism.COMPETITION]
    assert stored.results[pid][0].mechanism == Mechanism.COMPETITION
    actions = [e.action for e in await AuditEvent.find(AuditEvent.analysis_id == analysis.id).to_list()]
    assert actions[:2] == ["run_queued", "run_started"] and actions[-1] == "run_completed"


async def test_run_with_keep_keeps_verified(client, fake_extraction):
    analysis, _ = await analysis_with((True, ImpactState.ACTIVE))
    r = await client.post(f"/analyses/{analysis.id}/run", params={"verified": "keep"})
    assert r.status_code == 200
    await run_queue.idle()
    stored = await Analysis.get(analysis.id)
    kept = next(i for i in stored.impacts if i.id == analysis.impacts[0].id)
    assert kept.state == ImpactState.ACTIVE and kept.verified


async def test_failure_while_saving_run_marks_it_failed(client, fake_extraction, monkeypatch):
    def broken(*args):
        raise RuntimeError("boom")

    monkeypatch.setattr(run_queue, "apply_run", broken)
    analysis, pid = await analysis_with((False, ImpactState.ACTIVE))
    await client.post(f"/analyses/{analysis.id}/run")
    await run_queue.idle()
    stored = await Analysis.get(analysis.id)
    assert stored.status == AnalysisStatus.FAILED and stored.error == "Saving the run failed: boom"
    assert stored.runs[0].status == RunStatus.FAILED
    assert stored.impacts == analysis.impacts
    events = await AuditEvent.find(AuditEvent.analysis_id == analysis.id).to_list()
    assert events[-1].action == "run_failed"
    # review is not left locked
    r = await client.post(f"/analyses/{analysis.id}/impacts/{analysis.impacts[0].id}/remove", json={})
    assert r.status_code == 200


async def test_run_all_processes_papers_one_at_a_time_in_order(client, fake_extraction):
    analysis, pids = await analysis_of("A", "B", "C")
    await client.post(f"/analyses/{analysis.id}/run")
    await run_queue.idle()
    assert fake_extraction.calls == ["A", "B", "C"] and fake_extraction.max_active == 1
    runs = (await Analysis.get(analysis.id)).runs
    assert [r.paper_id for r in runs] == pids
    assert all(later.started_at >= earlier.completed_at for earlier, later in zip(runs, runs[1:]))


async def test_wake_during_the_last_claim_is_not_lost(client, fake_extraction, monkeypatch):
    analysis, [pid] = await analysis_of("A")
    claim = run_queue._claim
    woken = False

    async def claim_then_queue(analysis_id):
        nonlocal woken
        claimed = await claim(analysis_id)
        if claimed is None and not woken:
            # a run is queued after the drain found the queue empty, before it stops
            woken = True
            stored = await Analysis.get(analysis_id)
            stored.runs.append(AnalysisRun(paper_id=pid, model="m"))
            await stored.save()
            run_queue.wake(analysis_id)
        return claimed

    monkeypatch.setattr(run_queue, "_claim", claim_then_queue)
    run_queue.wake(analysis.id)
    await run_queue.idle()
    assert [r.status for r in (await Analysis.get(analysis.id)).runs] == [RunStatus.COMPLETED]


async def test_running_one_paper_keeps_the_others_results_and_impacts(client, fake_extraction):
    analysis, [a, b] = await analysis_of("A", "B", impacts=[("A", False), ("B", False)])
    await client.post(f"/analyses/{analysis.id}/run", params={"paper_id": b})
    await run_queue.idle()
    await client.post(f"/analyses/{analysis.id}/run", params={"paper_id": a})
    await run_queue.idle()
    stored = await Analysis.get(analysis.id)
    assert set(stored.results) == {a, b}
    assert fake_extraction.calls == ["B", "A"]

    analysis, [a, b] = await analysis_of("A", "B", impacts=[("A", False), ("B", False)])
    await client.post(f"/analyses/{analysis.id}/run", params={"paper_id": a})
    await run_queue.idle()
    stored = await Analysis.get(analysis.id)
    b_impact = next(i for i in stored.impacts if i.paper_id == b)
    assert b_impact == analysis.impacts[1]
    assert set(stored.results) == {a}


async def test_failed_paper_does_not_stop_the_queue(client, fake_extraction):
    analysis, [a, b, c] = await analysis_of("A", "B", "C", impacts=[("B", False)])
    fake_extraction.fail.add("B")
    await client.post(f"/analyses/{analysis.id}/run")
    await run_queue.idle()
    stored = await Analysis.get(analysis.id)
    states = stored.run_states()
    assert [states[p].state for p in (a, b, c)] == ["completed", "failed", "completed"]
    assert states[b].error == "extraction of B failed"
    assert [i for i in stored.impacts if i.paper_id == b] == analysis.impacts
    assert stored.status == AnalysisStatus.FAILED and stored.error == "extraction of B failed"


async def test_counts_cover_only_the_papers_to_queue(client, fake_extraction):
    analysis, [a, b] = await analysis_of("A", "B", impacts=[("A", False), ("B", True)])
    # paper A has no verified impacts: no choice needed although B has some
    r = await client.post(f"/analyses/{analysis.id}/run", params={"paper_id": a})
    assert r.status_code == 200
    await run_queue.idle()
    # both papers: B's verified impact needs a choice, counted over both papers' active AI impacts
    r = await client.post(f"/analyses/{analysis.id}/run")
    assert r.status_code == 409 and (r.json()["verified"], r.json()["unverified"]) == (1, 1)


async def test_already_queued_paper_is_not_counted_or_queued_again(client, fake_extraction):
    analysis, [a, b] = await analysis_of("A", "B", impacts=[("A", True)])
    gate = fake_extraction.hold("B")
    # B runs, and A waits behind it with its stored choice
    await client.post(f"/analyses/{analysis.id}/run", params={"paper_id": b})
    await until(lambda: _running(analysis.id, b))
    r = await client.post(f"/analyses/{analysis.id}/run", params={"paper_id": a, "verified": "keep"})
    assert r.json()["paper_runs"][a]["state"] == "queued"
    # Run all now: A is queued and B running, so nothing is queued and no choice is needed
    r = await client.post(f"/analyses/{analysis.id}/run")
    assert r.status_code == 200
    gate.set()
    await run_queue.idle()
    runs = (await Analysis.get(analysis.id)).runs
    assert sorted(r.paper_id for r in runs) == sorted([a, b])
    assert next(r for r in runs if r.paper_id == a).verified_choice == VerifiedChoice.KEEP


async def _running(analysis_id, pid):
    return await paper_state(analysis_id, pid) == "running"


async def test_paper_run_while_another_runs_waits_its_turn(client, fake_extraction):
    analysis, [a, b] = await analysis_of("A", "B")
    gate = fake_extraction.hold("A")
    await client.post(f"/analyses/{analysis.id}/run", params={"paper_id": a})
    await until(lambda: _running(analysis.id, a))
    r = await client.post(f"/analyses/{analysis.id}/run", params={"paper_id": b})
    assert r.json()["paper_runs"][b]["state"] == "queued"
    gate.set()
    await run_queue.idle()
    run_a, run_b = await run_of(analysis.id, a), await run_of(analysis.id, b)
    assert run_b.started_at >= run_a.completed_at


async def test_unknown_paper_is_rejected(client):
    analysis, _ = await analysis_of("A")
    r = await client.post(f"/analyses/{analysis.id}/run", params={"paper_id": str(PydanticObjectId())})
    assert r.status_code == 400


async def test_cancel_queued_run(client, fake_extraction):
    analysis, [a, b, c] = await analysis_of("A", "B", "C", impacts=[("B", False)])
    gate = fake_extraction.hold("A")
    await client.post(f"/analyses/{analysis.id}/run")
    await until(lambda: _running(analysis.id, a))
    run_b = await run_of(analysis.id, b)
    r = await client.post(f"/analyses/{analysis.id}/runs/{run_b.id}/cancel")
    assert r.status_code == 200 and r.json()["paper_runs"][b]["state"] == "not_run"
    # cancelling unlocks: B's impacts can be reviewed again while A runs
    r = await client.patch(f"/analyses/{analysis.id}/impacts/{analysis.impacts[0].id}", json={"verified": True})
    assert r.status_code == 200
    run_a = await run_of(analysis.id, a)
    assert (await client.post(f"/analyses/{analysis.id}/runs/{run_a.id}/cancel")).status_code == 409
    gate.set()
    await run_queue.idle()
    assert fake_extraction.calls == ["A", "C"]
    stored = await Analysis.get(analysis.id)
    run_b = await run_of(analysis.id, b)
    assert (run_b.status, run_b.started_at) == (RunStatus.CANCELLED, None)
    assert [i.state for i in stored.impacts if i.paper_id == b] == [ImpactState.ACTIVE]
    assert (await run_of(analysis.id, c)).status == RunStatus.COMPLETED


async def test_removing_a_running_paper_cancels_its_run(client, fake_extraction):
    analysis, [a, b] = await analysis_of("A", "B", impacts=[("A", False)])
    fake_extraction.hold("A")  # never released: removal must stop it
    await client.post(f"/analyses/{analysis.id}/run")
    await until(lambda: _running(analysis.id, a))
    r = await client.delete(f"/analyses/{analysis.id}/papers/{a}")
    assert r.status_code == 200
    await run_queue.idle()
    stored = await Analysis.get(analysis.id)
    assert (await run_of(analysis.id, a)).status == RunStatus.CANCELLED
    assert [i for i in stored.impacts if i.paper_id == a] == analysis.impacts and a not in stored.results
    assert (await run_of(analysis.id, b)).status == RunStatus.COMPLETED
    actions = [e.action for e in await AuditEvent.find(AuditEvent.analysis_id == analysis.id).to_list()]
    assert "run_cancelled" in actions


# --- review lock -----------------------------------------------------------


async def test_review_of_a_queued_paper_is_refused(client, fake_extraction):
    analysis, [a, b] = await analysis_of("A", "B", impacts=[("B", False)])
    gate = fake_extraction.hold("A")
    await client.post(f"/analyses/{analysis.id}/run")
    await until(lambda: _running(analysis.id, a))
    base = f"/analyses/{analysis.id}/impacts"
    iid = analysis.impacts[0].id
    start = MARKDOWN.index(EVIDENCE)
    for r in [
        await client.patch(f"{base}/{iid}", json={"verified": True}),
        await client.post(f"{base}/{iid}/remove", json={}),
        await client.post(f"{base}/{iid}/restore", json={}),
        await client.post(base, json={
            "paper_id": b, "fields": {"mechanism": "Predation", "category": "MO"},
            "evidence": [{"start": start, "end": start + len(EVIDENCE), "text": EVIDENCE}],
        }),
    ]:
        assert r.status_code == 409
    assert (await Analysis.get(analysis.id)).impacts == analysis.impacts
    gate.set()
    await run_queue.idle()


async def test_other_papers_stay_reviewable_during_a_run(client, fake_extraction):
    analysis, [a, b] = await analysis_of("A", "B", impacts=[("B", False)])
    gate = fake_extraction.hold("A")
    await client.post(f"/analyses/{analysis.id}/run", params={"paper_id": a})
    await until(lambda: _running(analysis.id, a))
    r = await client.patch(f"/analyses/{analysis.id}/impacts/{analysis.impacts[0].id}", json={"verified": True})
    assert r.status_code == 200
    gate.set()
    await run_queue.idle()


# --- restart ---------------------------------------------------------------


async def test_restart_fails_the_interrupted_run_and_processes_the_queue(client, fake_extraction):
    analysis, [a, b] = await analysis_of("A", "B", impacts=[("A", False)])
    analysis.runs = [
        AnalysisRun(paper_id=a, model="m", status=RunStatus.RUNNING),
        AnalysisRun(paper_id=b, model="m"),
    ]
    await analysis.save()
    await recover_runs()
    await run_queue.idle()
    stored = await Analysis.get(analysis.id)
    states = stored.run_states()
    assert (states[a].state, states[a].error) == ("failed", INTERRUPTED)
    assert states[b].state == "completed"
    assert [i for i in stored.impacts if i.paper_id == a] == analysis.impacts


async def test_shutdown_leaves_the_running_run_running_and_the_queue_queued(client, fake_extraction):
    analysis, [a, b] = await analysis_of("A", "B")
    fake_extraction.hold("A")
    await client.post(f"/analyses/{analysis.id}/run")
    await until(lambda: _running(analysis.id, a))
    await run_queue.shutdown()
    assert fake_extraction.calls == ["A"]
    assert [(await run_of(analysis.id, p)).status for p in (a, b)] == [RunStatus.RUNNING, RunStatus.QUEUED]


async def test_restart_fixes_a_stale_running_status(client):
    analysis, _ = await analysis_with(status=AnalysisStatus.RUNNING)
    await recover_runs()
    assert (await Analysis.get(analysis.id)).status == AnalysisStatus.PENDING


# --- review ----------------------------------------------------------------


async def test_span_not_matching_paper_is_rejected(client):
    analysis, _ = await analysis_with((False, ImpactState.ACTIVE))
    iid = analysis.impacts[0].id
    r = await client.patch(
        f"/analyses/{analysis.id}/impacts/{iid}", json={"evidence": [{"start": 0, "end": 4, "text": "Rats"}]}
    )
    assert r.status_code == 422
    stored = await Analysis.get(analysis.id)
    assert stored.impacts[0] == analysis.impacts[0]


async def test_reviewer_spans_are_not_approximate(client):
    analysis, _ = await analysis_with((False, ImpactState.ACTIVE))
    start = MARKDOWN.index(EVIDENCE)
    span = {"start": start, "end": start + len(EVIDENCE), "text": EVIDENCE, "approximate": True}
    r = await client.patch(f"/analyses/{analysis.id}/impacts/{analysis.impacts[0].id}", json={"evidence": [span]})
    assert r.status_code == 200
    stored = await Analysis.get(analysis.id)
    assert [s.approximate for s in stored.impacts[0].evidence] == [False]


async def test_invalid_category_is_rejected(client):
    analysis, _ = await analysis_with((False, ImpactState.ACTIVE))
    r = await client.patch(
        f"/analyses/{analysis.id}/impacts/{analysis.impacts[0].id}", json={"fields": {"category": "XX"}}
    )
    assert r.status_code == 422


async def test_add_impact_from_selected_text(client):
    analysis, pid = await analysis_with()
    start = MARKDOWN.index(EVIDENCE)
    r = await client.post(f"/analyses/{analysis.id}/impacts", json={
        "paper_id": pid,
        "fields": {"alien_species": "Rattus rattus", "mechanism": "Predation", "category": "MO",
                   "justification": "j", "impacted_species": ["Petrel"]},
        "evidence": [{"start": start, "end": start + len(EVIDENCE), "text": EVIDENCE}],
    })
    assert r.status_code == 201
    [impact] = r.json()["impacts"]
    assert (impact["origin"], impact["verified"], impact["ai"]) == ("human", True, None)


# --- audit -----------------------------------------------------------------


async def test_impact_history_is_filtered_and_oldest_first(client):
    analysis, _ = await analysis_with((False, ImpactState.ACTIVE), (False, ImpactState.ACTIVE))
    first, second = (i.id for i in analysis.impacts)
    base = f"/analyses/{analysis.id}/impacts"
    await client.patch(f"{base}/{first}", json={"fields": {"category": "MR", "reversibility": "unknown"}})
    await client.post(f"{base}/{second}/remove", json={"note": "not caused by the alien species"})
    await client.post(f"{base}/{first}/remove", json={})

    events = (await client.get(f"/analyses/{analysis.id}/audit", params={"impact_id": first})).json()
    assert [e["action"] for e in events] == ["updated", "verified", "removed"]
    assert all(e["impact_id"] == first for e in events)
    assert [e["at"] for e in events] == sorted(e["at"] for e in events)
    removal = (await client.get(f"/analyses/{analysis.id}/audit", params={"impact_id": second})).json()[0]
    assert (removal["note"], removal["actor"]) == ("not caused by the alien species", {"kind": "human", "user_id": None})


async def test_audit_events_survive_analysis_deletion(client):
    analysis, _ = await analysis_with((False, ImpactState.ACTIVE))
    await client.post(f"/analyses/{analysis.id}/impacts/{analysis.impacts[0].id}/remove", json={})
    assert (await client.delete(f"/analyses/{analysis.id}")).status_code == 204
    events = (await client.get(f"/analyses/{analysis.id}/audit")).json()
    assert [e["action"] for e in events] == ["removed"]


# --- papers ----------------------------------------------------------------


async def test_impacts_of_removed_paper_return_when_it_is_added_back(client):
    analysis, pid = await analysis_with((True, ImpactState.ACTIVE), (False, ImpactState.REMOVED))
    r = await client.delete(f"/analyses/{analysis.id}/papers/{pid}")
    assert r.json()["impacts"] == []
    r = await client.post(f"/analyses/{analysis.id}/papers/{pid}")
    assert [(i["verified"], i["state"]) for i in r.json()["impacts"]] == [(True, "active"), (False, "removed")]


async def test_impacts_of_removed_paper_cannot_be_reviewed(client):
    analysis, pid = await analysis_with((False, ImpactState.ACTIVE))
    await client.delete(f"/analyses/{analysis.id}/papers/{pid}")
    r = await client.post(f"/analyses/{analysis.id}/impacts/{analysis.impacts[0].id}/remove", json={})
    assert r.status_code == 404


# --- migration -------------------------------------------------------------


async def test_migration_is_idempotent_and_leaves_results(client):
    doc = await paper()
    pid = str(doc.id)
    analysis = Analysis(species=SpeciesNames(scientific_name="Rattus rattus"), paper_ids=[doc.id],
                        status=AnalysisStatus.COMPLETED, results={pid: [ai()]})
    await analysis.insert()
    results = analysis.model_dump()["results"]

    await migrate_legacy_analyses()
    await migrate_legacy_analyses()

    stored = await Analysis.get(analysis.id)
    assert [r.model for r in stored.runs] == ["legacy"]
    [impact] = stored.impacts
    assert (impact.origin, impact.verified, impact.state) == (ImpactOrigin.AI, False, ImpactState.ACTIVE)
    assert impact.evidence[0].start == MARKDOWN.index(EVIDENCE)
    assert stored.model_dump()["results"] == results
    assert await AuditEvent.find(AuditEvent.analysis_id == analysis.id).count() == 1


async def test_reanchor_evidence_anchors_stored_unanchored_spans(client):
    analysis, pid = await analysis_with((False, ImpactState.ACTIVE), (False, ImpactState.SUPPRESSED))
    unanchored = [EvidenceSpan(text=EVIDENCE)]
    active, suppressed = analysis.impacts
    active.evidence = unanchored
    suppressed.evidence = unanchored
    suppressed.sightings = [Sighting(run_id="r0", at=analysis.created_at, ai=ai(), evidence=unanchored)]
    reviewer = [EvidenceSpan(start=0, end=5, text="Intro")]
    human = ReviewedImpact(paper_id=pid, origin=ImpactOrigin.HUMAN, current=ai(), evidence=reviewer, verified=True)
    analysis.impacts.append(human)
    await analysis.save()

    await reanchor_evidence()
    await reanchor_evidence()

    stored = await Analysis.get(analysis.id)
    start = MARKDOWN.index(EVIDENCE)
    anchored = [EvidenceSpan(start=start, end=start + len(EVIDENCE), text=EVIDENCE)]
    active, suppressed, human = stored.impacts
    assert active.evidence == anchored and active.current.evidence == EVIDENCE
    assert suppressed.evidence == anchored and suppressed.sightings[0].evidence == anchored
    assert human.evidence == reviewer


async def test_reanchor_evidence_takes_paper_text_unless_a_reviewer_changed_it(client):
    analysis, _ = await analysis_with((False, ImpactState.ACTIVE), (False, ImpactState.ACTIVE))
    start = MARKDOWN.index("Rats ate")
    span = [EvidenceSpan(start=start, end=start + 8, text="Rats ate")]
    untouched, edited = analysis.impacts
    untouched.evidence = edited.evidence = span
    edited.current.evidence = "reviewer text"
    await analysis.save()
    await AuditEvent(
        analysis_id=analysis.id, impact_id=edited.id, actor=Actor(kind=ActorKind.HUMAN), action="updated",
        changes=[FieldChange(field="evidence", old=[], new=[s.model_dump() for s in span])],
    ).insert()

    await reanchor_evidence()

    untouched, edited = (await Analysis.get(analysis.id)).impacts
    assert (untouched.current.evidence, untouched.ai.evidence) == ("Rats ate", EVIDENCE)
    assert not untouched.evidence_edited
    assert (edited.current.evidence, edited.evidence_edited) == ("reviewer text", True)


async def test_reanchor_evidence_runs_once(client):
    await reanchor_evidence()
    analysis, _ = await analysis_with((False, ImpactState.ACTIVE))
    analysis.impacts[0].evidence = [EvidenceSpan(text=EVIDENCE)]
    await analysis.save()

    await reanchor_evidence()

    [impact] = (await Analysis.get(analysis.id)).impacts
    assert impact.evidence == [EvidenceSpan(text=EVIDENCE)]


async def test_reanchor_evidence_keeps_spans_that_stay_unanchored(client):
    analysis, _ = await analysis_with((False, ImpactState.ACTIVE))
    [impact] = analysis.impacts
    impact.ai.evidence = f"{EVIDENCE} Zebras juggle flaming torches quietly at dawn."
    impact.current.evidence = impact.ai.evidence
    impact.evidence = [EvidenceSpan(text=impact.ai.evidence)]
    await analysis.save()

    await reanchor_evidence()
    first = await Analysis.get(analysis.id)
    await reanchor_evidence()
    second = await Analysis.get(analysis.id)

    [impact] = first.impacts
    assert [s.start is not None for s in impact.evidence] == [True, False]
    assert impact.current.evidence == f"{EVIDENCE}\n\nZebras juggle flaming torches quietly at dawn."
    assert second.impacts == first.impacts
