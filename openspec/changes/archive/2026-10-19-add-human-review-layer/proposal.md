# Proposal

## Why

EICAT assessments need expert judgement, but today the pipeline's extracted impacts are read-only in the UI and a re-run overwrites `Analysis.results` wholesale. Experts can neither correct the AI nor keep their corrections, and there is no record of what the AI said versus what a human decided.

## What Changes

- Add a **human review layer** over AI-extracted impacts. Each impact gets a stable id, keeps a frozen snapshot of the AI's original output, and carries a separate editable `current` value, so AI provenance is always traceable.
- Reviewers can **edit every field** of an impact. Evidence is edited only by reselecting text in the paper viewer and is stored as character-offset spans into the paper markdown.
- Reviewers can **add impacts** by highlighting text in the paper, and **remove impacts** (soft delete, restorable).
- Add a **verified** checkbox on AI impacts. Editing an impact verifies it automatically; unticking is allowed. Verified and human-created impacts form the human layer.
- **Re-run behaviour changes**: unverified AI impacts are superseded; verified impacts are kept unless the user explicitly discards them. The run endpoint refuses (409) to run over verified impacts without an explicit choice, and the UI shows a confirmation summary.
- **Suppression**: a new AI impact whose `(paper, mechanism)` key is held by a verified, human-created or removed impact is not shown as active. It is stored as a suppressed record with a full per-run snapshot of each sighting, and can be viewed and restored.
- AI evidence passages are **anchored** to the paper text on ingest; passages that cannot be located are flagged for the reviewer.
- Every review and run action is written to an **audit trail** recording when, what changed (field, old, new), an optional reason, and the actor kind (`human`, `ai`, `system`), with a reserved `user_id` for future user accounts.
- `Analysis.results` keeps its current shape and meaning (raw AI output of the latest run) so `eval/gisd_eval.py` is unaffected.

## Capabilities

### New Capabilities
- `impact-review`: The human review layer on an analysis's impacts — impact identity and provenance, verification, editing, adding, removing and restoring, and how reviewed impacts are presented.
- `evidence-anchoring`: Representing impact evidence as spans of the paper text, locating AI evidence in the paper, and selecting evidence by highlighting text.
- `analysis-reruns`: What happens to existing impacts when an analysis is run again — superseding, keeping or discarding verified impacts, and suppression of AI impacts whose key is held by an expert decision.
- `review-audit-trail`: The append-only log of review and run actions, and how it is queried and displayed.

### Modified Capabilities
<!-- None: no specs exist yet in openspec/specs/. -->

## Impact

- **API** (`api/src/eicat_ai/`): new models in `models.py` (`ReviewedImpact`, `EvidenceSpan`, `Sighting`, `AnalysisRun`, `AuditEvent` document); `Analysis` gains `runs` and `impacts`; `routers/analyses.py` gains review endpoints and new run semantics; `main.py` registers the audit collection and adds `PATCH` to CORS methods. New anchoring helper.
- **UI** (`ui/src/`): `ImpactsPanel` becomes an editable review table; `PaperViewerDialog` gains highlight-to-select and span highlighting; new edit, re-run confirmation and history components; `types/index.ts`, `api/client.ts` and `analysesStore.ts` extended. `types/index.ts` also gains the missing `reversibility` field.
- **Data**: existing analyses have `results` but no `impacts`; they are migrated by an idempotent startup step that builds impacts from `results`.
- **Eval**: no change; `results` contract preserved.
- **Out of scope**: user accounts/authentication, species-level overall EICAT verdict, paper re-conversion (span offsets assume immutable markdown), a "runs disagree with experts" report.
