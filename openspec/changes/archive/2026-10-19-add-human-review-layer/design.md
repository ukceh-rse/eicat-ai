# Design

## Context

See proposal.md for motivation and specs/ for required behaviour.

Current state that shapes the approach:

- `Analysis` (Beanie document, collection `analyses`) stores `results: Dict[str, List[Impact]]` keyed by paper id. `_run_analysis` (`api/src/eicat_ai/routers/analyses.py`) runs as a FastAPI background task and replaces `results` wholesale, then calls `analysis.save()`, which rewrites the whole document.
- `merge_by_mechanism` (`converters.py`) guarantees at most one AI impact per mechanism per paper, and joins merged evidence passages with `"\n\n"`. The prompt asks for verbatim evidence but nothing enforces it.
- Papers are stored as markdown (`PaperDoc.markdown`), produced once at upload by GROBID → TEI → HTML → markdown, and rendered in the UI by `react-markdown` + `remark-gfm` in `PaperViewerDialog`.
- `eval/gisd_eval.py:144` reads `analysis["results"][paper_id]` through the API.
- No authentication exists. CORS allows `GET, POST, PUT, DELETE` only.
- The API has pytest as a dev dependency but no tests; the UI has no test framework.

## Goals / Non-Goals

**Goals:**
- Keep the re-run/suppression rules in one pure, unit-testable function.
- Keep the `Impact` model unchanged so the agent, `merge_by_mechanism`, CSV export and eval keep working.
- No lost updates between a background run and concurrent review edits.

**Non-Goals:**
- Real-time collaboration between simultaneous reviewers (last valid write wins, guarded by revision checks).
- Fuzzy matching beyond whitespace and case for anchoring.
- A UI test framework.

## Decisions

### D1. Impacts embedded in `Analysis`; audit events in their own collection

`Analysis` gains `runs: List[AnalysisRun]` and `impacts: List[ReviewedImpact]`. `AuditEvent` is a separate Beanie document (collection `audit_events`), indexed on `(analysis_id, at)` and `impact_id`.

- Embedding impacts keeps every review action and a run's whole merge one atomic document write. Volume is small: tens of papers × ≤12 mechanisms, plus superseded history.
- Audit events in their own collection survive analysis deletion (spec requirement), can be queried across analyses later, and never inflate the document the UI fetches.
- Alternative considered: impacts as their own collection. Rejected because a run's supersede + insert + suppress would need multi-document transactions, which the current single-node Mongo setup doesn't provide.

### D2. Model shape

```
EvidenceSpan   { start: int | None, end: int | None, text: str }   # None offsets = unanchored
Sighting       { run_id, at, ai: Impact, evidence: List[EvidenceSpan] }
AnalysisRun    { id, started_at, completed_at, model, usage, verified_choice: keep|discard|None, status }
ReviewedImpact {
  id: str (uuid4), paper_id, origin: ai|human, run_id | None,
  ai: Impact | None,                # frozen
  current: Impact,
  evidence: List[EvidenceSpan],
  verified: bool,                   # human-created impacts stored as True
  state: active|removed|superseded|suppressed,
  held_by: str | None,              # suppressed only
  sightings: List[Sighting],        # suppressed only
}
AuditEvent { at, analysis_id, impact_id?, run_id?, actor: {kind, user_id: None},
             action, changes: [{field, old, new}], note? }
```

`current` reuses `Impact`, so its `evidence: str` is kept as the span texts joined with `"\n\n"` and recomputed whenever spans change. The spans are the source of truth.

For suppressed records, `ai`/`current` mirror the latest sighting, so restoring is just a state change plus `verified = True`.

### D3. Re-run merge is a pure function

```
apply_run(impacts, new_by_paper, run_id, verified_choice, now)
    -> (impacts', events)
```

1. Supersede every active AI impact that is unverified, or is verified when `verified_choice == discard`.
2. Compute held keys `(paper_id, current.mechanism)` from impacts that are (active ∧ (verified ∨ human)) ∨ removed.
3. For each new AI impact: if its key is held, append a `Sighting` to the existing suppressed record for that key (creating it with `held_by` if absent); otherwise insert it as active, unverified.
4. Emit audit events for every state change.

The function performs no I/O. Tests cover every scenario in `specs/analysis-reruns`.

### D4. Merge at run completion, not start

The background task extracts first and applies `apply_run` only once every paper has succeeded. Then it reloads the latest `Analysis` and saves. A failed run therefore leaves impacts untouched, and `results` is replaced in the same write.

- Alternative considered: superseding at run start. Rejected because a failed run would hide the reviewer's active list with nothing to replace it.

### D5. Concurrency: review is locked while running; revision checks guard the rest

- Review endpoints return 409 while `status == running`, and the UI disables editing during a run.
- Enable Beanie `use_revision = True` on `Analysis`, so a save over a stale revision raises instead of silently overwriting. Review endpoints surface that as 409, and the UI refetches.

### D6. API surface

| Method | Path | Body |
|---|---|---|
| POST | `/analyses/{id}/impacts` | `{paper_id, fields, evidence: [span], note?}` — human-created |
| PATCH | `/analyses/{id}/impacts/{iid}` | `{fields?, evidence?, verified?, note?}` |
| POST | `/analyses/{id}/impacts/{iid}/remove` | `{note?}` |
| POST | `/analyses/{id}/impacts/{iid}/restore` | `{note?}` — removed → active, or suppressed → active+verified |
| POST | `/analyses/{id}/run?verified=keep\|discard` | 409 `{verified, unverified}` when verified exist and param missing |
| GET | `/analyses/{id}/audit?impact_id=` | events oldest first |

- `PATCH` with `fields` or `evidence` forces `verified = True`. When that flips the flag, a separate `verified` event is written.
- Spans submitted by humans are validated server-side: offsets must be present and `markdown[start:end] == text`.
- Remove and restore use POST action routes rather than DELETE, so they can take a note and so a DELETE never appears to destroy data.
- `PATCH` is added to the CORS `allow_methods`.
- `AnalysisResponse` gains `runs` and `impacts`, and keeps `results`.

### D7. Anchoring on the server

`anchor(markdown, evidence) -> List[EvidenceSpan]`:

1. Try the whole evidence string first; if it isn't found, split on `"\n\n"`.
2. For each passage, try `markdown.find(passage)`.
3. Otherwise, use a normalised search over a whitespace-collapsed, casefolded copy of the markdown, with an index map back to the original offsets.
4. If both fail, return an unanchored span.

Anchoring runs inside the background task, so the paper markdown is already loaded.

### D8. Selection and highlighting in the UI via a rehype plugin

A small rehype plugin passed to `ReactMarkdown` wraps each hast text node in `<span data-s data-e>`, using the node's source `position.start/end.offset`.

- **Selection:** `window.getSelection()` → the nearest `[data-s]` ancestor of the anchor and focus nodes. Source offset = node start + offset within the node. When the rendered text of a node differs in length from its source slice (escapes, entities), fall back to searching the markdown for the selected string near that node's start offset.
- **Highlighting:** the same plugin splits text nodes at span boundaries and wraps the covered parts in `<mark>`. The viewer scrolls the first mark into view.
- Span `text` is the raw markdown slice, so it may contain markdown syntax (`**`, `|`). That's accepted; the display renders it.
- Alternatives considered:
  - Storing offsets into rendered text. Rejected because those offsets depend on the renderer, and the server cannot validate them.
  - Storing only the quote. Rejected because a quote can appear more than once and cannot be validated.

Spike findings (task 1.1; 60 converted papers from the eval stack, 26,945 non-blank text nodes; plugin in `ui/src/components/sourceOffsets.ts`):

- 94.4% of text nodes render exactly as their source slice. Table cells were all exact.
- 4.9% differ only because rendering drops source characters: backslash escapes (`12\]`), entity syntax, the indentation of continuation lines, and code-span backticks (where a newline also renders as a space). A greedy alignment of each rendered character to the next matching source character (any whitespace matching any whitespace) maps all but 3 of these per character, so no search is needed.
- Cases needing the search fallback: 3 nodes where alignment fails (a setext heading built from a page-metadata block), and 209 text nodes (0.8%) with no source position, which remark-rehype creates for autolinked URLs and for the brackets of unresolved link references (`[`, `]`). The fallback searches for the selected text from 200 characters before the nearest positioned ancestor.
- A selection that ends on an element boundary (triple-click ends at offset 0 of the next paragraph) must resolve to the nearest mapped, non-whitespace text node, skipping the unpositioned `"\n"` nodes between blocks.
- Whitespace-only text inside `table`/`thead`/`tbody`/`tr` is left unwrapped, since a `<span>` there is invalid DOM.
- In headless Chrome, on two papers with tables (afrianto_2020_b, adams_1999), whole and partial paragraphs, table cells, cross-paragraph ranges, a triple-click and a mouse drag all produced offsets whose `markdown.slice(start, end)` begins and ends where the selection does (link syntax such as `[(Smith, 2012)](#b19 "…")` is included in the slice, as noted above).

`PaperViewerDialog` gains three modes: `view`, `highlight(impact)` and `select(onConfirm)`. The add-impact and edit-evidence flows open it in `select` mode.

### D9. Legacy analyses migrated at startup

An idempotent startup step converts each analysis that has non-empty `results` and no `runs`. It creates one synthetic run (`model = "legacy"`), turns each result into an active, unverified AI impact, anchors its evidence, and writes `ai`-actor `created` events.

- Alternative considered: lazy migration on read. Rejected because a GET would then write, and the list endpoint would migrate everything anyway.

## Risks / Trade-offs

- **Offset mapping breaks in some markdown** (tables, escaped characters, inline HTML) → Fall back to string search near the node (D8). The server validates every span, so a bad mapping is rejected instead of being saved wrong. Spike this first (tasks group 1).
- **Many AI passages fail to anchor** → The unanchored warning keeps this visible rather than fatal. The startup migration logs an anchoring hit rate, which tells you whether the normalised matcher needs extending.
- **Paper markdown changes after anchoring** → Re-conversion isn't possible today. If it's ever added, spans must be re-anchored; this is recorded as out of scope in the proposal.
- **Mechanism-only key misses same-mechanism impacts on different native taxa** → `merge_by_mechanism` already collapses these into one impact, so the AI never produces two impacts with the same key. A human can still create one deliberately.
- **Suppression hides AI disagreement** (e.g. the AI now says MR where the expert verified MO) → Accepted (option C). The sightings keep every snapshot, so the disagreement can be reported later.
- **Analysis document growth** from superseded impacts across many re-runs → Bounded in practice: one set per run, and suppressed records are deduplicated per key. If it ever matters, superseded impacts can be moved out later without changing the API.
- **No auth, so anyone with UI access is recorded as "human"** → Accepted. `actor.user_id` is reserved for later.

## Migration Plan

1. Deploy the API. The startup migration converts existing analyses (idempotent, logs counts and anchoring hit rate).
2. Deploy the UI.
3. Rollback: the old API ignores the new fields, and `results` is untouched, so the previous version keeps working. Review data stays in the document and in `audit_events`.
