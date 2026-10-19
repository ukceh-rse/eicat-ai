# Tasks

## 1. Spike: selection-to-offset mapping (design D8)

- [x] 1.1 Prototype the rehype text-node offset plugin in `PaperViewerDialog` behind a dev flag and verify, on two real converted papers (one with tables), that selecting a paragraph, a table cell and a cross-paragraph range yields offsets where `markdown.slice(start, end)` equals the selected source; record the cases needing the search fallback in design.md D8

## 2. Domain models and anchoring (API)

- [x] 2.1 Add `EvidenceSpan`, `Sighting`, `AnalysisRun`, `ReviewedImpact` and the `AuditEvent` document to `api/src/eicat_ai/models.py`, add `runs`/`impacts` and `use_revision` to `Analysis`, extend `AnalysisResponse`, and register `AuditEvent` in `main.py`; verify the API starts against an empty Mongo and `GET /analyses/` returns the new fields
- [x] 2.2 Implement `anchor(markdown, evidence)` (exact, then whitespace/case-normalised, whole string before `"\n\n"` split, unanchored fallback) and add `api/tests/test_anchoring.py` covering verbatim, whitespace-only differences, multi-passage, repeated passage and not-found cases; verify `uv run --project api pytest api/tests` passes
- [x] 2.3 Implement span validation for human-submitted spans (offsets present, slice equals text) with unit tests for valid, mismatched and out-of-range spans; verify tests pass

## 3. Re-run merge and suppression (API)

- [x] 3.1 Implement pure `apply_run(impacts, new_by_paper, run_id, verified_choice, now) -> (impacts, events)` per design D3, with `api/tests/test_apply_run.py` covering every scenario in `specs/analysis-reruns` (supersede unverified, keep/discard verified, human-created and removed untouched, key from current mechanism, suppression by verified/human/removed holders, one suppressed record per key with appended sightings); verify tests pass
- [x] 3.2 Rework `_run_analysis` to record an `AnalysisRun`, anchor evidence, apply `apply_run` only after all papers succeed, reload the latest `Analysis` and save `results` and `impacts` together, and write `run_started`/`run_completed` and merge events to `audit_events`; verify manually that a successful run populates `runs` and `impacts`, and that a forced failure leaves existing impacts unchanged
- [x] 3.3 Add the `verified=keep|discard` query parameter to `POST /analyses/{id}/run`, returning 409 with `{verified, unverified}` counts when verified AI impacts exist and the parameter is missing; verify with curl for the three cases (no verified, missing parameter, explicit choice)
- [x] 3.4 Confirm `eval/gisd_eval.py` still works unchanged by running `uv run --project eval pytest eval/tests` and one `extract` on a single case; verify `results[paper_id]` holds the raw AI impacts

## 4. Review endpoints and audit trail (API)

- [x] 4.1 Add an audit helper that writes `AuditEvent`s (UTC time, actor `{kind, user_id: None}`, field diffs, note), plus unit tests for diff generation including the separate `verified` event on auto-verify; verify tests pass
- [x] 4.2 Implement `POST /analyses/{id}/impacts`, `PATCH /analyses/{id}/impacts/{iid}`, `POST .../remove` and `POST .../restore` per design D6 (auto-verify on edit, `current.evidence` recomputed from spans, suppressed restore uses the latest sighting and sets verified, 409 while running or on a stale revision, 422 on invalid enum values or spans); verify each with curl against a completed analysis, including audit events written
- [x] 4.3 Implement `GET /analyses/{id}/audit?impact_id=` (oldest first), make `DELETE /analyses/{id}` leave audit events in place, and add `PATCH` to CORS `allow_methods`; verify that events can still be fetched after deleting an analysis
- [x] 4.4 Hide impacts of papers no longer in `paper_ids` from `AnalysisResponse.impacts` without deleting them; verify by removing and re-adding a paper with curl
- [x] 4.5 Document the review endpoints, run parameter and audit trail in `api/README.md`, and verify the documented curl examples run as written

## 5. Legacy migration (API)

- [x] 5.1 Implement the idempotent startup migration (design D9: synthetic `legacy` run, active unverified AI impacts, anchored evidence, `created` events, log of counts and anchoring hit rate); verify on a copy of `mongo-data` that existing analyses gain impacts, a second startup changes nothing, and `results` is byte-identical

## 6. UI data layer

- [x] 6.1 Extend `ui/src/types/index.ts` (add `reversibility`, `EvidenceSpan`, `ReviewedImpact`, `Sighting`, `AnalysisRun`, `AuditEvent`), `api/client.ts` (impact create/patch/remove/restore, run with `verified`, audit) and `analysesStore.ts` (actions that replace the analysis from the response, refetch on 409); verify `npm run build` and `npm run lint` pass in `ui/`

## 7. Paper viewer: highlight and select

- [x] 7.1 Turn the spike into the rehype plugin with `view`, `highlight(spans)` and `select(onConfirm)` modes in `PaperViewerDialog`; highlight with `<mark>` and scroll to the first span; verify in the running app that an anchored AI impact's evidence is highlighted in place
- [x] 7.2 In `select` mode, show an action on text selection to add the selection as a span, list the chosen spans with remove buttons, and confirm; verify in the running app that the confirmed spans pass server validation

## 8. Review UI

- [x] 8.1 Rework `ImpactsPanel` into the review table: verified checkbox, origin and "changed from AI" markers (tooltip shows the AI value), unanchored-evidence warning, "n/m verified" in each paper header, and editing disabled while running; verify in the running app against a migrated analysis
- [x] 8.2 Add an impact edit dialog for all fields (enum selects, reversibility required only for MR/MV, impacted species as a chip input, optional reason) with an "Edit evidence" button that opens the viewer in `select` mode; verify in the app that an edit auto-ticks verified and shows as changed from AI
- [x] 8.3 Add "Add impact" from viewer selection (viewer opened from the paper row), creating a human impact through the edit dialog; verify in the app that it appears as verified with origin human
- [x] 8.4 Add remove (with optional reason) and collapsed "Removed (n)" and "Suppressed (n)" sections per paper, with restore actions; each suppressed row shows the impact holding its key and its sightings; verify in the app that restore works from both sections
- [x] 8.5 Add the impact history drawer (time, actor kind, action, field old→new, reason) from each row; verify in the app that it lists AI creation followed by an edit
- [x] 8.6 Add the re-run confirmation dialog (kept/replaced counts from the 409 or local state, second confirm for discard) on the Run button in `AnalysisDetailPage`; verify in the app for both the keep and discard paths
- [x] 8.7 Document the review workflow in `ui/README.md`, and verify that `npm run build` passes

## 9. End-to-end check

- [x] 9.1 Using the docker-compose stack, run an analysis on two papers, verify one impact, edit one, remove one, add one by highlighting, then re-run choosing keep; verify that the unverified impact was replaced, the verified, edited and human impacts survived, re-found mechanisms appear under Suppressed with a sighting, and every action appears in the impact histories
