"""API-level tests for the review layer, against an in-memory Mongo (mongomock-motor)."""

import pytest
from beanie import init_beanie
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from eicat_ai.main import app
from eicat_ai.migration import migrate_legacy_analyses
from eicat_ai.models import (
    Analysis,
    AnalysisStatus,
    AuditEvent,
    Category,
    Impact,
    ImpactOrigin,
    ImpactState,
    Mechanism,
    PaperDoc,
    PaperStatus,
    ReviewedImpact,
    RunStatus,
    SpeciesNames,
)
from eicat_ai.routers import analyses as analyses_router

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


async def paper() -> PaperDoc:
    doc = PaperDoc(filename="p.pdf", content_type="application/pdf", size=1, pdf_data=b"", status=PaperStatus.READY,
                   markdown=MARKDOWN)
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


@pytest.fixture
def fake_extraction(monkeypatch):
    async def extract(agent, paper, species):
        return [ai(Mechanism.COMPETITION)], {"input_tokens": 3}

    monkeypatch.setattr(analyses_router, "data_extraction_agent", lambda model: None)
    monkeypatch.setattr(analyses_router, "extract_impacts", extract)


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
    stored = await Analysis.get(analysis.id)  # the background task has run by now
    assert stored.status == AnalysisStatus.COMPLETED
    assert [(run.status, run.usage) for run in stored.runs] == [(RunStatus.COMPLETED, {"input_tokens": 3})]
    assert [i.current.mechanism for i in stored.impacts if i.state == ImpactState.ACTIVE] == [Mechanism.COMPETITION]
    assert stored.results[pid][0].mechanism == Mechanism.COMPETITION
    actions = [e.action for e in await AuditEvent.find(AuditEvent.analysis_id == analysis.id).to_list()]
    assert actions[0] == "run_started" and actions[-1] == "run_completed"


async def test_run_with_keep_keeps_verified(client, fake_extraction):
    analysis, _ = await analysis_with((True, ImpactState.ACTIVE))
    r = await client.post(f"/analyses/{analysis.id}/run", params={"verified": "keep"})
    assert r.status_code == 200
    stored = await Analysis.get(analysis.id)
    kept = next(i for i in stored.impacts if i.id == analysis.impacts[0].id)
    assert kept.state == ImpactState.ACTIVE and kept.verified


async def test_failure_while_saving_run_marks_it_failed(client, fake_extraction, monkeypatch):
    def broken(*args):
        raise RuntimeError("boom")

    monkeypatch.setattr(analyses_router, "apply_run", broken)
    analysis, _ = await analysis_with((False, ImpactState.ACTIVE))
    await client.post(f"/analyses/{analysis.id}/run")
    stored = await Analysis.get(analysis.id)
    assert stored.status == AnalysisStatus.FAILED and stored.error == "Saving the run failed: boom"
    assert stored.runs[0].status == RunStatus.FAILED
    assert stored.impacts == analysis.impacts
    events = await AuditEvent.find(AuditEvent.analysis_id == analysis.id).to_list()
    assert events[-1].action == "run_failed"
    # review is not left locked
    r = await client.post(f"/analyses/{analysis.id}/impacts/{analysis.impacts[0].id}/remove", json={})
    assert r.status_code == 200


# --- review ----------------------------------------------------------------


async def test_review_is_locked_while_running(client):
    analysis, _ = await analysis_with((False, ImpactState.ACTIVE), status=AnalysisStatus.RUNNING)
    r = await client.patch(f"/analyses/{analysis.id}/impacts/{analysis.impacts[0].id}", json={"verified": True})
    assert r.status_code == 409


async def test_span_not_matching_paper_is_rejected(client):
    analysis, _ = await analysis_with((False, ImpactState.ACTIVE))
    iid = analysis.impacts[0].id
    r = await client.patch(
        f"/analyses/{analysis.id}/impacts/{iid}", json={"evidence": [{"start": 0, "end": 4, "text": "Rats"}]}
    )
    assert r.status_code == 422
    stored = await Analysis.get(analysis.id)
    assert stored.impacts[0] == analysis.impacts[0]


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
