"""Stable local pseudonyms for annotators (A1, A2, ...), so no output ever carries initials.

The mapping is kept in annotators.json, gitignored: it is the only place real initials are
written down, and it grows additively (an annotator's id never changes once assigned), so
ids stay consistent across scripts and across runs even as new annotators are added.
"""

from __future__ import annotations

import json
from pathlib import Path

MAPPING_PATH = Path(__file__).parent / "annotators.json"


def anonymize(stems: set[str], mapping_path: Path = MAPPING_PATH) -> dict[str, str]:
    mapping = json.loads(mapping_path.read_text()) if mapping_path.exists() else {}
    for stem in sorted(stems - mapping.keys()):
        mapping[stem] = f"A{len(mapping) + 1}"
    mapping_path.write_text(json.dumps(mapping, indent=2))
    return {stem: mapping[stem] for stem in stems}


def sort_ids(ids) -> list[str]:
    """Sort anonymous ids numerically (A2 before A10), not lexicographically."""
    return sorted(ids, key=lambda a: int(a[1:]))


def deanonymize(mapping_path: Path = MAPPING_PATH) -> dict[str, str]:
    """Id -> real initials, for the named-output figures only. Never feed this into a report."""
    mapping = json.loads(mapping_path.read_text()) if mapping_path.exists() else {}
    return {anon_id: stem for stem, anon_id in mapping.items()}
