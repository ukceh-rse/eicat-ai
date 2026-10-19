# Proposal

## Why

Reviewing impacts is slow and the evidence shown is not always the paper's text. Editing any field opens a popup, evidence is viewed and reselected in a popup stacked on another popup, and the table's rows are tall with alert banners and chips, leaving the evidence column cramped. AI evidence the anchoring could locate is still shown in the AI's own wording whenever any other passage of the same impact could not be located.

## What Changes

- AI evidence is **anchored more robustly** (letters-and-digits matching, sentence-by-sentence location, approximate anchoring of paraphrases to the closest passage), and every anchored span always shows the paper text it covers, span by span. Only a span sharing no words with the paper keeps the AI's text, and only that span is flagged.
- Impact fields are **edited inline in the review table**: category (with reversibility), mechanism, confidence and impacted species in their cells; alien species, justification and an optional reason in an expandable row detail. Each change saves immediately. **BREAKING (UI)**: the impact edit popup is removed.
- Category selectors list categories **most severe first** (MV, MR, MO, MN, MC, DD) with the code and full name.
- Evidence is viewed and edited on its **own page** with the paper beside a panel of spans; adding an impact uses the same page with the impact's fields in the panel. **BREAKING (UI)**: the paper viewer popups are removed.
- The review table is **compact**: fixed column widths giving the evidence column the remaining width, evidence clamped to three lines, status shown as icons instead of banners, origin and "changed from AI" combined, actions in a menu, dense rows.
- The analysis page **merges the Papers and Results boxes** into one list with a section per paper, including papers not yet run or without impacts, each with its add-impact and remove-paper actions.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `evidence-anchoring`: robust and approximate location of AI evidence; per-span paper text as an AI impact's evidence; evidence viewed and edited on a dedicated page rather than a viewer popup.
- `impact-review`: inline editing in the table; reason entered in the row detail; adding an impact on the evidence page; category ordering and labels; compact table layout; one section per paper combining papers and their impacts.

## Impact

- **API** (`api/src/eicat_ai/`): `anchoring.py` locating and approximate anchoring; `review.py` deriving evidence per span; `migration.py` re-anchoring stored unanchored spans on startup; `EvidenceSpan` gains an `approximate` flag and `ReviewedImpact` an `evidence_edited` flag.
- **UI** (`ui/src/`): `ImpactsPanel` becomes an inline-editable compact table; `ImpactEditDialog` and `PaperViewerDialog` are replaced by routed evidence, new-impact and paper pages (the Papers page opens papers on their own page too); `AnalysisDetailPage` merges the Papers and Results sections; new routes in `App.tsx`; `impactFields.ts` and `CategoryChip.tsx` category labels.
- **Data**: no shape change beyond the `approximate` and `evidence_edited` flags; the idempotent startup migration fills `evidence_edited` from the audit trail and re-anchors existing unanchored spans.
- **Out of scope**: running individual papers and the run queue (change `per-paper-run-queue`); the analysis-level Run button keeps its current behaviour here.
