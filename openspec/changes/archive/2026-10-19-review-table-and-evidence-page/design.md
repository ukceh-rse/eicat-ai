# Design

## Context

Part of this change is already in the working tree:

- **Anchoring is done** in `api/src/eicat_ai/anchoring.py`. `Locator.anchor` locates evidence as a whole, then passage by passage, then sentence by sentence. It matches exactly, then ignoring whitespace and case, then on letters and digits only. A sentence still not found goes to `closest()`, which picks a window of paper sentences by IDF-weighted overlap and marks the span `approximate` when less than 90% of it aligns. Only a sentence that shares no words with the paper becomes an unanchored span. `EvidenceSpan.approximate` exists in the API model and the UI types. Runs, the legacy migration and the reviewer endpoint (which clears `approximate`) all use `Locator`.
- **Evidence derivation does not yet match the spec.** `review.as_found` uses the paper text only when *every* span is anchored, and otherwise keeps the AI's text whole. `migration.reanchor_evidence` replaces a holder's spans only when re-anchoring places all of them. It treats an impact as "not changed by a reviewer" only when `current.evidence == ai.evidence`.
- **"Changed from AI" does not match the revised spec.** `impactFields.changedFromAi` compares the AI's evidence with the current evidence on letters and digits. So an untouched impact whose evidence was anchored approximately, or with a few OCR differences, or whose quote skipped text with `...`, shows as changed. The API keeps no record of whether a reviewer changed the evidence. The audit trail does record it, as an `updated` event with a `FieldChange(field="evidence")`.
- **The UI is otherwise unchanged.** `ImpactsPanel` shows a table per paper inside accordions, with banners, chips, an edit popup (`ImpactEditDialog`) and a viewer popup (`PaperViewerDialog`). `AnalysisDetailPage` has separate Papers and Results boxes and runs the add-impact flow through both popups. `PapersPage` opens papers in `PaperViewerDialog` too. `App.tsx` has routes for `/papers`, `/analyses` and `/analyses/:id`.
- The UI has no automated tests. It is checked with `npm run build` (`tsc -b`), `npm run lint` and by running the app. The API has pytest suites for anchoring, apply_run, review actions and routes.
- `per-paper-run-queue` touches the same page next (per-paper run state and run actions in each paper's section header). The section header built here is where those actions will go.

## Goals / Non-Goals

**Goals:**
- An AI impact's evidence is derived span by span, and the startup migration brings stored impacts in line once, without touching reviewer evidence.
- "Changed from AI" reflects reviewer actions only.
- Every view of a paper is a routed page: an impact's evidence, a new impact, and plain reading from the Papers page. No paper popups remain.
- The review table is edited in place through the existing `PATCH /impacts/{id}` endpoint. No new edit endpoints.

**Non-Goals:**
- Changes to the anchoring algorithm or its thresholds.
- Per-paper run state, run actions or locking. Review stays locked for the whole analysis while it runs, as now.
- Optimistic UI updates or undo. A cell shows the store's value, which changes only when the API answers.
- UI test infrastructure.

## Decisions

### D1. Evidence is the spans' texts, whatever their status
`as_found(ai, spans)` sets `current.evidence = evidence_text(spans)` whenever there are spans. An unanchored span's `text` is already the AI's sentence, so joining the texts in order gives exactly what the spec requires: paper text for anchored spans and the AI's text for unanchored ones. The AI's wording stays on `ai.evidence`.
*Alternative:* keep the all-or-nothing rule and mark the unanchored part in the UI. Rejected because the spec requires per-span paper text.

### D2. `ReviewedImpact.evidence_edited` records reviewer evidence changes
A new boolean, `evidence_edited` (default `False`), is set to `True` by `edit_impact` when the spans change. It is set to `False` wherever the AI's values replace the current ones: when an impact is created or re-sighted in `apply_run`, and in the legacy migration. Restoring a suppressed impact keeps the latest sighting's evidence, so the flag stays `False`.
- The UI counts evidence as changed from AI only when `evidence_edited` is true. All other fields keep the plain value comparison.
- The startup migration uses the same flag to tell which impacts no reviewer touched.

*Alternatives:*
- Infer the flag in the UI from span flags or folded text. Rejected because an untouched impact whose spans are all exact or OCR-close looks the same as reviewer-chosen spans.
- Read the audit trail per impact. Rejected because it needs a request per row or a join on every analysis read.
- Store the AI's spans on the impact. Rejected because it duplicates `sightings` and costs more for no extra benefit.

This adds a field beyond the `approximate` flag, so the proposal's Data line has been updated to say so.

### D3. Startup migration: backfill the flag, then re-anchor
`reanchor_evidence` runs after `migrate_legacy_analyses` and is idempotent:
1. Set `evidence_edited = True` on every impact that has an audit `updated` event with an `evidence` change. This is one query for the impact ids, run once before the per-analysis loop.
2. For each impact and each sighting with an AI value and any unanchored span, anchor again from `ai.evidence` and keep the new spans, even if some stay unanchored. A reviewer's spans are always anchored, so they are never in scope.
3. For each AI impact with `evidence_edited` false, set `current.evidence = evidence_text(evidence)` if it differs.

The analysis is saved only when something changed, so a second start changes nothing.

### D4. Routes and shared paper rendering
New routes, all inside `Layout`:
- `/analyses/:id/impacts/:impactId/evidence`: the evidence page.
- `/analyses/:id/papers/:paperId/new-impact`: the new-impact page.
- `/papers/:paperId`: plain reading.

The rendering and selection code in `PaperViewerDialog` (markdown with source offsets, highlights, scroll to the first `<mark>`, selection to span, and the "Add passage" popper) moves into a `PaperText` component with the props `paperId`, `highlights` and an optional `onSelect`. A `PaperLayout` component lays the paper out beside a side panel. The evidence page, the new-impact page and the paper page all use these. `PaperViewerDialog` and `ImpactEditDialog` are deleted.

Pages load the analysis from the store, calling `fetch` if it is not loaded yet, so the evidence and new-impact addresses work when opened directly.
*Alternative:* keep the popups and give them a URL. Rejected because the spec and the proposal remove the popups.

### D5. Returning to the table: `?impact=<id>`
After a save or cancel, the evidence and new-impact pages go to `/analyses/:id?impact=<impactId>`. When an impact is created, the new id is found by comparing the impact ids before and after the create response. The analysis page reads the query parameter, opens that paper's section, scrolls the row into view, highlights it briefly, and removes the parameter with `replace`.
*Alternative:* router location state. Rejected because a URL parameter also works after a reload and can be tested by hand.

### D6. Inline editing goes through `patchImpact` with one field per change
Each cell is a compact control whose value comes from the store:
- Category and mechanism use a `Select`.
- Confidence uses a `Select` with an empty option.
- Impacted species uses a multiple free-text `Autocomplete`, saved on change.

A change calls `patchImpact(aid, id, { fields: { [key]: value }, note })`. On an error the store is unchanged, so the control falls back to its previous value, and the error shows in the panel's error alert. This meets "the cell shows its previous value".

When the category is changed to MR or MV, a small reversibility menu opens on the cell. The patch is sent with both fields only after a value is picked. Dismissing the menu cancels the change. All controls are disabled while the analysis is running (`readOnly`).

### D7. Row detail and reason
Each active row has an expand toggle. The detail row spans every column and holds:
- an alien species `TextField` and a justification `TextField`, each saved on blur when its value has changed;
- a reason `TextField` that is not saved by itself;
- the AI's original values when the impact differs from them.

The reason lives in per-row state in `ImpactsPanel` (`Record<impactId, string>`). Any patch from that row, whether a cell or the detail, sends it as `note` and clears it on success. The reason is not sent with verify toggles, since those are not edits.

The evidence page has its own reason field, sent as `note` with the evidence it saves, because the row's reason does not survive leaving the table.
*Alternative:* ask for a reason in a popup on each save. Rejected because it brings back the confirmation step the spec removes.

### D8. Compact table layout
- The table uses `tableLayout: fixed` with a `colgroup` of fixed widths for verified, category, mechanism, impacted species, confidence, origin and actions. The evidence column has no width, so it takes what is left.
- Evidence is clamped with `-webkit-line-clamp: 3` and the whole cell links to the evidence page.
- Status icons sit before the text: a warning icon if any span is unanchored, otherwise an info icon if any is approximate. Each icon's tooltip gives the status and the AI's wording. The evidence page shows each span's own status.
- Evidence is shown as read: link targets and HTML tags are dropped for display (a citation `[[61]](#b60 "…")` reads `[61]`); the stored text is unchanged. The evidence page's span list does the same.
- The origin cell shows "AI", "AI, edited" or "Human". When edited, its tooltip lists the AI's values for the changed fields, which replaces both the "Changed from AI" chip and the per-cell dots.
- Remove, restore and history move into a `MoreVert` menu.
- Rows use `size="small"` with reduced padding.

### D9. Category labels in one place
`impactFields.ts` exports `CATEGORY_LABELS` (for example `MC: 'MC – Minimal Concern'`) next to `CATEGORIES`, which is already in severity order. Every category selector renders those labels in `CATEGORIES` order. `CategoryChip` takes its labels from `CATEGORY_LABELS` and keeps only its colours.

In the table's category cell the chip shows the code alone, with the full name on hover, so it fits a narrow column; every category menu lists code and full name.

### D10. One section per paper
`ImpactsPanel` loops over `analysis.paper_ids` rather than over papers with impacts. It keeps the per-paper accordions, Removed and Suppressed sections, and the "n/m verified" header.
- A paper with no `results` entry and no impacts says "Not run yet".
- A paper that has been run but has no active impacts says "No impacts found".
- The section header holds the add-impact button (which goes to the new-impact page) and the remove-paper button.
- `AnalysisDetailPage` drops its Papers box and its Results heading, and moves "Add Papers" next to the list. The panel always renders, even before any run.

## Risks / Trade-offs

- [The `evidence_edited` backfill depends on the audit trail. An impact edited before audit events existed would be treated as untouched.] → The audit trail shipped with the review layer, and so did every evidence edit, so no such impacts exist.
- [Saving on change makes every pick a write and an audit event. A reviewer cycling through values creates noise in the history.] → This is accepted by the spec. Selects save only when the value really changes.
- [Saving on blur can be lost if the reviewer navigates away mid-edit.] → The text fields also save on Enter for alien species. Justification is multiline and saves on blur, which happens before route changes in React.
- [Moving the viewer code into `PaperText` risks breaking the source-offset selection logic.] → `sourceOffsets.ts` is unchanged. The move is mechanical and is checked by hand on the evidence page: highlight a passage, save, and confirm that the API accepts it.
- [`AnalysisDetailPage` will be edited again by `per-paper-run-queue`.] → Section headers keep their actions in one place so that change adds run controls beside them.

## Migration Plan

`reanchor_evidence` runs at API startup (D3). It is idempotent and only updates documents it changes. Rollback means redeploying the previous version: the extra `approximate` and `evidence_edited` fields are ignored by the older models, and re-anchored spans are still valid spans.
