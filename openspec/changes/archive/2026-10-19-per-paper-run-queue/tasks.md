# Tasks

## 1. Run model and derived state

- [x] 1.1 Extend `RunStatus` with `queued` and `cancelled`, and `AnalysisRun` with `paper_id`, `queued_at`, optional `started_at` and `error` (`api/src/eicat_ai/models.py`, design D1). Verify existing analyses with legacy runs still load in `tests/test_routes.py`.
- [x] 1.2 Add `run_states(analysis)` and `Analysis.refresh_status()` (D3): a paper's state comes from its latest run that wasn't cancelled; legacy runs without `paper_id` cover papers with a `results` entry; the analysis is running, then failed, then completed, otherwise pending, over current papers; `error` and `completed_at` are derived too. Add `paper_runs` to `AnalysisResponse`. Verify with unit tests for each spec scenario under "Each paper shows its run state" (mixed states, failed paper, cancelled run, nothing completed, removed failed paper, legacy run).

## 2. Run queue worker

- [x] 2.1 Create `api/src/eicat_ai/run_queue.py` with `wake(analysis_id)`, a per-analysis drain task (claim the oldest queued run of a current paper with a revision-checked save, extract in a child task, complete), the pending mark that keeps a late `wake` from being lost, and `idle()` for tests (D2). Verify with a test that queues three runs and checks they run one after another in queue order, and a test that a `wake` during the drain's last claim still gets its run processed.
- [x] 2.2 Narrow `_complete_run` to one paper (D4): merge only that paper's impacts through `apply_run`, set only `results[paper_id]`, add usage, check the run is still running and its paper still in the analysis before merging, call `refresh_status()`, and record a failure on that run only. Keep the force-save fallback. Verify with tests: running A keeps B's `results` and impacts ("Running one paper keeps the others' results", "Other papers untouched"); a failed middle paper leaves its impacts unchanged and the third run starts; the existing `test_failure_while_saving_run_marks_it_failed` passes, adapted to a paper run.
- [x] 2.3 Remove `_run_analysis` and the `BackgroundTasks` use from `routers/analyses.py`, and update existing run tests to await `run_queue.idle()`. Verify `uv run pytest` (in `api/`) passes.

## 3. Run, cancel and remove endpoints

- [x] 3.1 Rework `POST /analyses/{id}/run` (D5): optional repeated `paper_id` (default every current paper), skip papers already queued or running, 409 check and counts over the papers left, 400 for unknown papers or none, one queued run per paper storing the verified choice, `run_queued` audit events, then `wake`. Verify with tests for every scenario of "Re-run over verified impacts requires an explicit choice" (including "Already queued paper not counted") and "Paper runs are queued and processed one at a time" ("Paper already queued", "Run a paper while another runs").
- [x] 3.2 Add `POST /analyses/{id}/runs/{run_id}/cancel` for queued runs (409 otherwise) writing `run_cancelled`. Verify with a test that the cancelled run never starts, the paper's impacts are unchanged, the next run starts in its turn, and the paper is reviewable again ("Cancelling unlocks").
- [x] 3.3 Make `DELETE /analyses/{id}/papers/{paper_id}` cancel the paper's queued run, or save its running run as cancelled and cancel the extraction task through `run_queue` (D6), and call `refresh_status()` on paper add and remove. Verify with a test that removes a paper while its (blocked) fake extraction runs: the run is cancelled, impacts unchanged, no late merge, and the next queued run starts.
- [x] 3.4 Update the "Re-running an analysis" section and the review 409 note in `api/README.md` to cover per-paper runs, Run all as the bare POST, cancel, and the per-paper lock. Verify the documented `curl` commands against a running API.

## 4. Per-paper review lock

- [x] 4.1 Change `_reviewable` to check the impact's paper (or the new impact's `paper_id`) against `run_states` and refuse 409 only for a queued or running paper (D8). Verify by replacing `test_review_is_locked_while_running` with tests for "Review a queued paper" (rejected, impact unchanged) and "Review another paper during a run" (saved), covering edit, add, remove and restore.

## 5. Startup recovery

- [x] 5.1 Add `migration.recover_runs()` and call it in `lifespan` after `reanchor_evidence()`. It fails running runs as "Interrupted by an API restart", refreshes every analysis's status, and wakes analyses with queued runs. Cancel drain tasks on shutdown (D7). Verify with a test for "Restart during a run" (A failed as interrupted with impacts unchanged, B runs) and a test that an analysis stored as `running` with no running run becomes `completed` or `pending`.

## 6. UI

- [x] 6.1 Update `ui/src/types/index.ts` (`AnalysisRun` fields and states, `paper_runs` on `AnalysisResponse`) and `ui/src/api/client.ts` / `store/analysesStore.ts` (`run(id, { paperIds, verified })`, `cancelRun(id, runId)`). Verify `npm run build` (in `ui/`) passes.
- [x] 6.2 In `AnalysisDetailPage`, replace "Run Analysis" with "Run all", add `requestRun(paperIds)` that opens `RerunDialog` with counts over the papers to be queued (or calls the API when they have no impacts), keep polling while the status is running, and drop the page-wide "Review is paused" alert. Reword `RerunDialog` for one paper or all papers. Verify in the running app: Run all on an analysis with 5 verified and 9 unverified AI impacts shows those totals, and discard asks a second time.
- [x] 6.3 In `ImpactsPanel`'s section header, show the paper's run state chip and last completed time, and offer Cancel for a queued paper and otherwise Re-run if it has completed a run and Run if not. Make each section read-only from its own `paper_runs` state, while keeping "Remove from analysis" enabled. Verify in the running app: a queued paper shows Cancel and read-only impacts while another paper stays editable, and its section moves through queued → running → completed without a reload.
- [x] 6.4 Make `EvidencePage` and `NewImpactPage` read-only from the impact's paper state instead of the analysis status. Verify in the running app that opening an impact of a running paper shows it read-only with the run message, and an impact of another paper is editable.
- [x] 6.5 Verify `npm run lint` and `npm run build` pass.

## 7. Integration

- [x] 7.2 Restart the API while one paper of a two-paper analysis is running, and verify in the UI that the paper shows failed with "Interrupted by an API restart" and the other paper's run then completes.

## Workflow follow-up

- Run `/opsx:verify`, then `/opsx:archive` to sync the `analysis-reruns` and `impact-review` deltas into the main specs.
