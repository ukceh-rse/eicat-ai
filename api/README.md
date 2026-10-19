# EICAT AI API

FastAPI service for AI-assisted EICAT assessment generation. Provides document upload, analysis, and species lookup capabilities.

## Features

- **Document Analysis**: Upload PDFs and extract impact data using AI
- **Species Lookup**: Search GBIF database for species information  
- **File Management**: Upload and retrieve research documents

## Quick Start

### Local Development
```bash
uv sync
uv run src/eicat_ai/main.py
```

### Docker
```bash
docker build -t eicat-ai .
docker run -p 8000:8000 eicat-ai
```

API available at http://localhost:8000

## Dependencies

- [uv](https://docs.astral.sh/uv/) - Python package manager
- FastAPI - Web framework
- Pydantic AI - AI agent framework

## Reviewing impacts

Each run's raw AI output stays in `results[paper_id]`, in the same shape as before, and is not changed by review. Reviewers work on `impacts`, where each impact has:

- a stable `id`, its `paper_id`, an `origin` (`ai` or `human`) and the `run_id` that produced it
- `ai`: the frozen AI output (null for human-created impacts) and `current`: the reviewed values
- `evidence`: spans of the paper markdown (`{start, end, text, approximate}`); `approximate` spans are the closest passage to AI evidence the paper doesn't contain word for word. Spans with null offsets are AI sentences sharing no words with the paper. An AI impact's `current.evidence` is its spans' texts in order, so the paper text for each anchored span and the AI's sentence for each unanchored one; the AI's wording is in `ai.evidence`
- `evidence_edited`: true once a reviewer has changed the spans (saving approximate spans as they are only clears their `approximate` flag). Until then, differences between `current.evidence` and `ai.evidence` come from anchoring, not from review
- `verified` (human-created impacts are always verified) and a `state`: `active`, `removed`, `superseded` (replaced by a re-run) or `suppressed` (re-found by a run while an expert decision holds its paper and mechanism; `held_by` names that impact and `sightings` keeps every run's extraction)

Impacts of papers removed from the analysis are hidden, and come back unchanged if the paper is added again.

The examples below assume:

```bash
API=http://localhost:8000
ANALYSIS=<analysis id>
IMPACT=<impact id>
PAPER=<paper id in the analysis>
```

Verify or unverify an AI impact:

```bash
curl -X PATCH $API/analyses/$ANALYSIS/impacts/$IMPACT \
  -H 'Content-Type: application/json' -d '{"verified": true, "note": "checked against table 2"}'
```

Edit fields (`alien_species`, `mechanism`, `category`, `reversibility`, `confidence`, `justification`, `impacted_species`). Any edit verifies the impact. `reversibility` is cleared unless the category is MR or MV:

```bash
curl -X PATCH $API/analyses/$ANALYSIS/impacts/$IMPACT \
  -H 'Content-Type: application/json' \
  -d '{"fields": {"category": "MR", "reversibility": "reversible"}, "note": "local extinction reported"}'
```

Evidence is never free text: `evidence` takes spans selected in the paper, and each span's `text` must equal the paper markdown between its offsets (otherwise 422). Get the markdown from `GET /papers/{id}/content`:

```bash
curl -X PATCH $API/analyses/$ANALYSIS/impacts/$IMPACT \
  -H 'Content-Type: application/json' \
  -d "$(curl -s $API/papers/$PAPER/content | python3 -c '
import json, sys
text = json.load(sys.stdin)["content"]
print(json.dumps({"evidence": [{"start": 100, "end": 160, "text": text[100:160]}]}))')"
```

Add an impact (origin `human`, verified):

```bash
curl -X POST $API/analyses/$ANALYSIS/impacts \
  -H 'Content-Type: application/json' \
  -d "$(curl -s $API/papers/$PAPER/content | python3 -c '
import json, sys
text = json.load(sys.stdin)["content"]
print(json.dumps({
    "paper_id": "'$PAPER'",
    "fields": {"alien_species": "Rattus rattus", "mechanism": "Predation", "category": "MO",
               "justification": "", "impacted_species": ["Pterodroma macroptera"]},
    "evidence": [{"start": 100, "end": 160, "text": text[100:160]}],
    "note": "missed by the AI",
}))')"
```

Remove an impact (kept, and restorable), and restore a removed or suppressed one. A restored suppressed impact becomes active and verified with its latest sighting's values:

```bash
curl -X POST $API/analyses/$ANALYSIS/impacts/$IMPACT/remove \
  -H 'Content-Type: application/json' -d '{"note": "not caused by the alien species"}'
curl -X POST $API/analyses/$ANALYSIS/impacts/$IMPACT/restore
```

Review requests return the updated analysis. They return 409 while the analysis is running, when the action doesn't fit the impact's state (e.g. editing a removed impact), or when another request changed the analysis at the same time (reload and retry). Invalid values return 422.

### Re-running an analysis

A re-run supersedes unverified AI impacts. Human-created and removed impacts are never changed. When verified AI impacts exist, the run must say whether to keep or discard them, otherwise it returns 409 with the counts:

```bash
curl -X POST $API/analyses/$ANALYSIS/run
# 409 {"detail": "...", "verified": 3, "unverified": 7}
curl -X POST "$API/analyses/$ANALYSIS/run?verified=keep"
```

An AI impact whose paper and mechanism are held by an active verified impact, an active human-created impact or a removed impact doesn't become active; it is stored as `suppressed`. Each run is listed in `runs` with its model, usage and choice.

### Audit trail

Every review and run action is logged in the `audit_events` collection with its time (UTC), actor (`{"kind": "human" | "ai" | "system", "user_id": null}`), action, changed fields (`{field, old, new}`) and optional note. Actions: `created`, `updated`, `verified`, `unverified`, `removed`, `restored`, `superseded`, `suppressed`, `sighted`, `run_started`, `run_completed`, `run_failed`. Events can't be changed through the API and are kept when the analysis is deleted.

```bash
curl "$API/analyses/$ANALYSIS/audit"                    # all events, oldest first
curl "$API/analyses/$ANALYSIS/audit?impact_id=$IMPACT"  # one impact's history
```

### Tests

```bash
uv run --project api pytest api/tests
```
