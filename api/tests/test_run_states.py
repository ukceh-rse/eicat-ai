from datetime import datetime, timedelta, timezone

from beanie import PydanticObjectId

from eicat_ai.models import Analysis, AnalysisRun, AnalysisStatus, RunStatus, SpeciesNames

T0 = datetime(2026, 10, 19, tzinfo=timezone.utc)
A, B, C = (str(PydanticObjectId()) for _ in range(3))


def run(paper, status, minutes=0, error=None):
    at = T0 + timedelta(minutes=minutes)
    done = status in (RunStatus.COMPLETED, RunStatus.FAILED)
    return AnalysisRun(paper_id=paper, status=status, model="m", queued_at=at, started_at=at,
                       completed_at=at if done else None, error=error)


def analysis(*runs, papers=(A, B, C), results=None):
    # constructed without Beanie initialised: the model is used as plain pydantic
    a = Analysis.model_construct(
        species=SpeciesNames(scientific_name="Rattus rattus"), paper_ids=[PydanticObjectId(p) for p in papers],
        runs=list(runs), results=results or {}, impacts=[], status=AnalysisStatus.PENDING, error=None,
        completed_at=None,
    )
    a.refresh_status()
    return a


def states(a):
    return {p: s.state for p, s in a.run_states().items()}


def test_mixed_paper_states():
    a = analysis(run(A, RunStatus.COMPLETED), run(B, RunStatus.RUNNING, 1))
    assert states(a) == {A: "completed", B: "running", C: "not_run"}
    assert a.status == AnalysisStatus.RUNNING


def test_failed_paper():
    a = analysis(run(A, RunStatus.COMPLETED), run(B, RunStatus.FAILED, 1, error="boom"))
    assert a.status == AnalysisStatus.FAILED and a.error == "boom"
    assert a.run_states()[B].error == "boom"


def test_cancelled_run_falls_back_to_earlier_run():
    a = analysis(run(A, RunStatus.COMPLETED), run(A, RunStatus.CANCELLED, 1))
    s = a.run_states()[A]
    assert (s.state, s.last_completed_at) == ("completed", T0)
    assert a.status == AnalysisStatus.COMPLETED and a.completed_at == T0


def test_nothing_completed_is_pending():
    a = analysis(run(A, RunStatus.CANCELLED))
    assert set(states(a).values()) == {"not_run"}
    assert a.status == AnalysisStatus.PENDING


def test_removed_failed_paper_does_not_fail_the_analysis():
    a = analysis(run(A, RunStatus.COMPLETED), run(B, RunStatus.FAILED, 1, error="boom"), papers=(A,))
    assert a.status == AnalysisStatus.COMPLETED and a.error is None


def test_legacy_run_covers_papers_with_results():
    legacy = AnalysisRun(status=RunStatus.COMPLETED, model="legacy", started_at=T0, completed_at=T0)
    a = analysis(legacy, results={A: []})
    assert states(a) == {A: "completed", B: "not_run", C: "not_run"}


def test_failed_run_is_not_locked_and_queued_is():
    a = analysis(run(A, RunStatus.FAILED, error="x"), run(B, RunStatus.QUEUED))
    assert not a.run_states()[A].locked and a.run_states()[B].locked
