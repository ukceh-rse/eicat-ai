# Design

## Context

See proposal.md (Why). Current state the approach has to work with:

- `POST /analyses/{id}/run` (`routers/analyses.py`) appends one `AnalysisRun` and starts `_run_analysis` with FastAPI `BackgroundTasks`. It extracts every paper in turn and, only once all have succeeded, `_complete_run` merges them through `review.apply_run` in a revision-checked save with three retries, and replaces `results` as a whole.
- `apply_run` already works on any subset of impacts: `_complete_run` passes it only the impacts of the papers in the run. A per-paper run is the same call with one paper.
- Review is locked by `_reviewable`, which refuses every review action while `Analysis.status == RUNNING`. The UI derives `readOnly` from the same status in `AnalysisDetailPage`, `EvidencePage` and `NewImpactPage`.
- `Analysis` uses Beanie revision checks (`use_revision = True`), and `main.py` turns `RevisionIdWasChanged` into a 409.
- The eval harness (`eval/gisd_eval.py`) creates one analysis per case, posts `/run` with no parameters, polls until `status` is `completed` or `failed`, then reads `results[paper_id]`, `error` and `usage`. It runs several analyses at once.
- API tests (`tests/test_routes.py`) rely on `httpx.ASGITransport` finishing background tasks before the response returns.
- The API runs as a single uvicorn process.

## Goals / Non-Goals

**Goals:**
- One place decides a paper's run state and the analysis status, so the API, the review lock and the UI can't disagree.
- The run worker can be driven step by step from tests without real timing.
- The eval harness keeps working unchanged.

**Non-Goals:**
- Several API processes sharing a queue (no cross-process locking or leases).
- Retrying failed runs automatically.
- Progress inside one paper's extraction.

## Decisions

### D1. Runs are stored in `Analysis.runs`; the queue is the queued runs in that list
`AnalysisRun` gains `paper_id: Optional[str]`, `queued_at`, `error` and the states `queued` and `cancelled`. `started_at` becomes optional because a queued run has not started. The queue of an analysis is its `queued` runs in `queued_at` order.

*Alternative:* a separate `run_queue` collection. Rejected: a run would live in two places, and enqueueing, cancelling and completing would need multi-document consistency. Keeping runs in the analysis document lets every state change use the existing revision-checked save.

Runs recorded before this change have no `paper_id`. They count as runs of every paper that has a `results` entry (D3), so existing analyses show their papers as completed without a data migration.

### D2. One drain task per analysis, managed by a new `run_queue` module
`eicat_ai/run_queue.py` keeps a `dict` of analysis id → `asyncio.Task`. `wake(analysis_id)` starts a drain task for the analysis if none is running. Endpoints call it after saving queued runs, and startup calls it for analyses with queued runs (D7). The drain task loops:

1. **Claim:** load the analysis, take the oldest queued run whose paper is still in `paper_ids`, set it `running` with `started_at`, and save with the revision check. On a conflict it reloads and tries again.
2. **Extract:** extract and anchor that one paper in a child task (so it can be cancelled, D6).
3. **Complete:** call `_complete_run`, narrowed to one paper (D4).
4. If no queued run is left, stop.

A `wake` that arrives while the drain is about to stop must not be lost. `wake` marks the analysis pending as well as starting a task. The drain clears that mark before each claim, and removes itself only if no queued run was found and the mark is still clear. That check and the removal happen with no `await` between them, so they can't interleave with a `wake` on the single event loop.

Separate analyses drain at the same time, as the proposal's scope says (one queue per analysis), so the eval harness's parallel analyses still run in parallel.

*Alternative:* one global worker processing runs across all analyses. Rejected: it would serialise the eval harness. *Alternative:* keep `BackgroundTasks` and chain the next run at the end of each one. Rejected: nothing would restart the chain after a restart, and cancellation would have nowhere to hook in.

For tests, `run_queue` exposes `async idle()`, which awaits every drain task. Tests call it after posting a run instead of relying on `BackgroundTasks` finishing inside the request.

### D3. Paper run state and analysis status come from one pure function
`run_states(analysis) -> Dict[paper_id, PaperRunState]` (state, `last_completed_at`, `error`) applies the spec's rule: the latest run that wasn't cancelled, otherwise not run. `Analysis.refresh_status()` derives `status`, `error` and `completed_at` from those states over the current `paper_ids`:
- `error` is the error of the most recently failed paper still in the failed state.
- `completed_at` is the latest completion time.

Every code path that changes `runs` or `paper_ids` calls `refresh_status()` just before it saves. The stored `status` stays, so listing analyses and the eval harness's polling read it as before. `AnalysisResponse` adds `paper_runs` from `run_states`, so the UI doesn't re-derive the rule.

*Alternative:* compute `status` only on read and drop the stored field. Rejected: the stored field would then be stale data in Mongo, and `refresh_status()` is one call per save site.

### D4. Completing a run merges one paper into the latest document
`_complete_run` keeps its reload-and-retry loop and changes as follows:
- `apply_run` gets only that paper's impacts.
- Only `results[paper_id]` is set.
- The run's usage is added to `analysis.usage` (so `usage` remains the total across runs).
- `refresh_status()` is called before saving.

Before merging, it checks on the reloaded document that the run is still `running` and its paper is still in the analysis. If not (the paper was removed meanwhile, D6), it discards the extraction. A failed extraction, or a failure while saving, records only that run as failed with its error. The existing fallback that force-saves a failed state is kept and narrowed to the run, so a paper is never left locked.

### D5. API surface
- `POST /analyses/{id}/run?paper_id=…&paper_id=…&verified=keep|discard`. With no `paper_id`, it means every current paper, so the eval harness's bare `/run` becomes Run all.
  - Papers already queued or running are skipped. The verified/unverified counts and the 409 check cover only the papers left.
  - The 409 body keeps its shape (`detail`, `verified`, `unverified`), so `RerunDialog`'s retry path is unchanged.
  - It returns 400 if a given paper isn't in the analysis, or if there are no papers.
  - It no longer refuses because the analysis is running.
- `POST /analyses/{id}/runs/{run_id}/cancel` cancels a queued run. It returns 409 if the run isn't queued (running runs stop only through paper removal, as the spec says).
- `DELETE /analyses/{id}/papers/{paper_id}` cancels the paper's queued run and stops its running one (D6).
- Audit events: `run_queued` (with the verified choice in its note) is written on enqueue, `run_started` on claim, `run_completed`/`run_failed` as now, and `run_cancelled` on cancel. `run_started` and `run_completed` still exist as the `review-audit-trail` spec requires.

*Alternative:* a JSON body for the run request. Rejected: `verified` is already a query parameter, and query parameters keep the bare POST the eval harness sends valid.

### D6. Stopping a running run cancels its extraction task
The drain task records the child task running the current extraction. Removing a paper saves the run as `cancelled` (or cancels it while queued), then asks `run_queue` to cancel that child task if it belongs to this run. The drain task catches the `CancelledError` from the child, writes `run_cancelled`, and moves on. Because the run is already saved as cancelled, D4's check stops a late completion from merging even if the cancellation lands after extraction finished.

*Alternative:* let the extraction finish and throw its output away. Rejected: it spends tokens and holds up the queue for a paper that has already gone.

### D7. Startup recovery runs after the existing migrations
`migration.recover_runs()`, called in `lifespan` after `reanchor_evidence()`, does two things:
- Marks every `running` run `failed` with the error "Interrupted by an API restart", and calls `refresh_status()`.
- Starts `run_queue.wake` for each analysis with queued runs.

On shutdown, `lifespan` cancels the drain tasks. A run cut off this way is still `running` in Mongo and is failed on the next start, which is what the spec requires. Analyses stuck as `running` from before this change, with no running run, are fixed by the same `refresh_status()` call.

### D8. Per-paper review lock
`_reviewable(analysis_id)` becomes `_reviewable(analysis_id, paper_id)`. It looks up the impact (or the `paper_id` of a new impact) first, then refuses with 409 if `run_states` reports that paper as `queued` or `running`. The UI reads `paper_runs[paperId]` to decide `readOnly` per paper in `ImpactsPanel`, `EvidencePage` and `NewImpactPage`.

Removing a paper stays enabled while the paper is locked, because removal is how a running run is stopped.

Because a paper is locked from the moment it is queued, its verified impacts can't change before its run completes. The keep/discard choice stored at enqueue therefore still matches the counts the reviewer confirmed.

### D9. UI
- **Page header:** "Run all" replaces "Run Analysis". It is disabled when there are no papers or every paper is queued or running.
- **Paper section header:** shows the run state chip and when the paper last completed a run. It offers Run, Re-run or Cancel by the spec's rule.
- **Run and Re-run:** both go through one `requestRun(paperIds)` on the page. It opens `RerunDialog` with counts over those papers' active AI impacts (leaving out papers already queued or running) when they have any impacts, and calls the API directly otherwise. The dialog's wording changes from "Re-run analysis" to name the paper or "all papers".
- **Polling:** the page polls every 5 s while `analysis.status === 'running'` (true while any paper is queued or running, D3). The page-wide "Review is paused" alert goes away. A queued or running section shows the read-only message instead.
- **Types:** `AnalysisRun` gains its new fields and states, and `AnalysisResponse` gains `paper_runs`.

## Risks / Trade-offs

- [The queue lives in one process; a second API process would also drain it] → The API runs as one uvicorn process today. This is listed as a non-goal; a lease on claim would be the fix if that changes.
- [An analysis's `runs` list grows with every paper run] → Runs are small (ids, times, usage, an error string). Fine for the expected scale of tens of papers and a few re-runs each.
- [A long extraction holds the drain of its analysis; other papers of that analysis wait] → This is intended (one at a time per analysis). Other analyses aren't affected.
- [Cancelling the child task mid-request might leave the LLM client in a bad state] → `CancelledError` is the normal asyncio cancellation path for httpx-based clients. The run is already saved as cancelled before the task is cancelled, so the worst case is a lost extraction, never a merge.
- [A revision conflict between a reviewer's save on paper B and the worker's save for paper A] → Both reload and retry or surface 409 as today. The worker retries up to three times, then records the run as failed rather than leaving it running.
- [Legacy runs without `paper_id` are read as covering every paper with a `results` entry] → A paper added after the last legacy run correctly shows as not run, because it has no `results` entry.

## Migration Plan

1. Deploy the API. On startup, `recover_runs()` fails any interrupted runs and fixes stale `running` statuses. No document rewrite is needed for legacy runs (D1).
2. Deploy the UI together with the API: the old UI's "Run Analysis" would still work against the new API (as Run all), but its analysis-wide read-only state would be wrong.
3. Rollback: the old `RunStatus` can't parse `queued` or `cancelled`, so the old code would fail to load analyses holding such runs. Rolling back needs a one-off script that drops cancelled runs and fails queued ones. Rollback is not expected, and no rollback script is written ahead of time.
