# Proposal

## Why

An analysis can only be run as a whole: adding one paper or retrying one that failed re-runs every paper, costs tokens for all of them and locks the whole analysis from review until every paper is done. A run in progress is held only in memory, so an API restart leaves the analysis marked running for good.

## What Changes

- Extraction runs **one paper per run**. A reviewer can run or re-run any single paper from its section of the analysis page; "Run all" queues every paper of the analysis.
- Runs wait in a **persisted queue** and are processed **one at a time** across the analysis, in the order queued. A queued run can be cancelled. A failed paper keeps its error and the queue moves on.
- The **keep/discard choice** for verified impacts is made when papers are queued, with counts for those papers only, and is stored with each queued run.
- A paper is **locked from review from queued until its run finishes**; the analysis's other papers stay reviewable.
- Each paper shows its **run state** (not run, queued, running, completed, failed) and when it was last run. The analysis status is derived from its papers' runs.
- `results[paper_id]` holds the AI's raw impacts from **that paper's latest completed run**; other papers' results are untouched. **BREAKING (API)**: `results` is no longer replaced as a whole by each run.
- After an API restart, queued runs stay queued and are processed; a run that was in progress is marked failed. Removing a paper from an analysis cancels its queued or running run.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `analysis-reruns`: runs cover one paper; a persisted one-at-a-time queue; keep/discard choice and supersession scoped to the papers run; `results` replaced per paper; per-paper run state, cancellation, failure and restart behaviour.
- `impact-review`: review locked per paper while it is queued or running; run and re-run actions on each paper's section.

## Impact

- **API** (`api/src/eicat_ai/`): `AnalysisRun` gains a paper id and queued/cancelled states; `routers/analyses.py` run endpoint accepts the papers to run and returns verified/unverified counts for the papers to be queued on 409, a cancel endpoint is added, and background tasks are replaced by a run queue module that drains each analysis's queued runs and is started and recovered with the app (`main.py`); `Analysis.status` is derived from runs; startup recovery of interrupted runs in `migration.py`.
- **UI** (`ui/src/`): run state, Run/Re-run and Cancel in each paper's section header; "Run all" in the page header; `RerunDialog` counts for the papers being queued; per-paper read-only state and polling while any run is queued or running.
- **Eval**: `eval/gisd_eval.py` reads `results[paper_id]`; it keeps working, but a paper's entry reflects its latest completed run rather than one shared run.
- **Builds on**: `review-table-and-evidence-page` (archived), whose per-paper sections hold the run actions.
- **Out of scope**: running several papers of an analysis in parallel; a queue shared across analyses (each analysis has its own); per-run model choice.
