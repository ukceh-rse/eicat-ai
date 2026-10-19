# Tasks

## 1. Evidence anchoring and derivation (API)

- [x] 1.1 Confirm the anchoring already in the working tree (`Locator`, letters-and-digits and sentence-by-sentence matching, `closest()` approximate anchoring, `EvidenceSpan.approximate`, the reviewer endpoint clearing `approximate`) covers every scenario of "AI evidence is located in the paper", "AI evidence not quoted word for word is anchored approximately" and "Evidence sharing no words with the paper is left unanchored"; add any missing scenario test to `api/tests/test_anchoring.py` / `test_routes.py`, and verify `uv run --project api pytest api/tests/test_anchoring.py api/tests/test_routes.py` passes
- [x] 1.2 Make `review.as_found` set `current.evidence` to `evidence_text(spans)` whenever there are spans (D1), and verify with a `test_apply_run.py` case where two sentences anchor and a third stays unanchored: evidence is the two paper texts then the AI's third sentence
- [x] 1.3 Add `evidence_edited: bool = False` to `ReviewedImpact` and the UI `ReviewedImpact` type; set it in `edit_impact` when the spans change and leave it false where `apply_run` and the legacy migration set values from the AI (D2); verify with `test_review_actions.py` cases for an evidence edit (true), a field-only edit (false) and a run-created impact (false)
- [x] 1.4 Rework `migration.reanchor_evidence` per D3: backfill `evidence_edited` from audit `updated` events with an `evidence` change, re-anchor any impact or sighting with an unanchored span and keep the new spans even if some stay unanchored, and re-derive `current.evidence` for AI impacts with `evidence_edited` false; verify with migration tests that cover a reviewer-edited impact left untouched, a partly re-anchored impact, and a second run changing nothing
- [x] 1.5 Update `api/README.md` to describe approximate spans, per-span evidence and the `evidence_edited` flag, and verify the full API suite passes with `uv run --project api pytest api/tests`

## 2. Shared UI building blocks

- [x] 2.1 Add `CATEGORY_LABELS` to `impactFields.ts` and make `CategoryChip` take its labels from it (D9); verify `npm run build` passes and a chip shows "MC – Minimal Concern"
- [x] 2.2 Change `changedFromAi` so evidence counts as changed only when `evidence_edited` is true, removing the folded-text comparison (D2); verify `npm run build` passes and an untouched approximately anchored impact shows no change marker in the running app
- [x] 2.3 Extract the markdown rendering, highlighting, scroll-to-first-mark and text-selection logic from `PaperViewerDialog` into a `PaperText` component, plus a `PaperLayout` laying a paper beside a side panel (D4); verify `npm run build` and `npm run lint` pass

## 3. Evidence, new-impact and paper pages

- [x] 3.1 Add the `/analyses/:id/impacts/:impactId/evidence` route and `EvidencePage`: paper with the impact's spans highlighted and the first in view, a side panel listing spans with approximate/unanchored status and the AI's wording, adding passages by selection, removing spans, Save (patching `evidence`, with the page's own optional reason as note) and Cancel, both returning to `/analyses/:id?impact=<id>` (D4, D5); read-only while the analysis runs; verify in the running app by opening the page from its address, reselecting evidence, saving, and seeing the API accept it
- [x] 3.2 Add the `/analyses/:id/papers/:paperId/new-impact` route and `NewImpactPage` on the same layout, with the impact's fields (category selector in severity order with labels, reversibility for MR/MV) in the panel, Save disabled until evidence, mechanism and category are set, and a return to the analysis with the new row highlighted; verify in the running app by adding an impact from highlighted text
- [x] 3.3 Add the `/papers/:paperId` route and `PaperPage` for plain reading, and make `PapersPage` navigate there instead of opening `PaperViewerDialog`; verify in the running app that a paper opens on its own page and returns to the Papers list
- [x] 3.4 Delete `PaperViewerDialog` and `ImpactEditDialog` and their imports; verify `grep -rn "PaperViewerDialog\|ImpactEditDialog" ui/src` finds nothing and `npm run build` and `npm run lint` pass

## 4. Inline-editable compact review table

- [x] 4.1 Make category, mechanism, confidence and impacted species editable in their cells, saving one field per change through `patchImpact`, with the reversibility menu for MR/MV that cancels on dismiss, and errors shown while the cell keeps its stored value (D6); verify in the running app: change MN→MO saves and verifies, MN→MR saves only after reversibility is picked, and a rejected value leaves the cell unchanged with an error shown
- [x] 4.2 Add the expandable row detail with alien species and justification saved on blur when changed, the per-row reason sent as `note` with the next change and then cleared, and the AI's original values when they differ (D7); verify in the running app and the impact's history that the reason is recorded with the next change and the field is emptied
- [x] 4.3 Apply the compact layout (D8): fixed `colgroup` widths with evidence taking the rest, evidence clamped to three lines and linking to the evidence page, status icons with tooltips instead of banners, the origin cell showing "AI", "AI, edited" or "Human" with AI values in its tooltip (no separate chip or per-cell dots), actions (remove, restore, history) in a row menu; verify in the running app at a typical laptop width that rows are one line apart from evidence and no banner or "Changed from AI" chip remains
- [x] 4.4 Make the analysis page highlight and scroll to the row named by `?impact=` and then drop the parameter (D5); verify by saving on an evidence page and seeing the row highlighted

## 5. One section per paper

- [x] 5.1 Make `ImpactsPanel` list a section for every paper in `analysis.paper_ids`, showing "Not run yet" or "No impacts found" where relevant, with add-impact (to the new-impact page) and remove-paper actions in the section header, and remove the Papers box and Results heading from `AnalysisDetailPage`, keeping "Add Papers" above the list (D10); verify in the running app that a newly added, unrun paper shows its section and that removing a paper from its section takes it off the page
- [x] 5.2 Update `ui/README.md` for the routed pages, inline editing and merged paper sections, and verify `npm run build` and `npm run lint` pass

## 6. Integration check

- [x] 6.1 Restart the API against a database with impacts from before this change, then check in the UI that previously unanchored evidence now shows paper text per span, reviewer-edited evidence is unchanged, untouched impacts are not marked "AI, edited", and a full review pass (inline edit with reason, evidence reselection, add impact, remove/restore via the menu, history) works end to end
