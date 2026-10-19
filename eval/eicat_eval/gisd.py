"""GISD gold-standard data: reading the cleaned export, merging duplicate rows, mechanism names.

The cleaned CSV comes from `utils/filter_clean.py` (run by `gisd_eval.py fetch`). This module is also
the one bridge into `utils/`, a separate uv project whose helpers the evaluation reuses; both helpers
it imports are standard-library only, so they load fine in the eval environment.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from eicat_eval.paths import GISD_CLEAN, UTILS

sys.path.insert(0, str(UTILS))
from gisd import normalise_mechanism  # noqa: E402
from library import load_library  # noqa: E402

__all__ = ["GOLD_IMPACT_KEY", "canonical_mechanism", "gold_impacts", "load_library", "merge_countries", "read_gisd"]

# Columns that identify one GISD impact; rows differing only in other columns are the same impact.
GOLD_IMPACT_KEY = ["Impact mechanism", "EICAT Category", "Evidence for EICAT impact category", "Impacted native species"]

# App mechanism names that `utils/gisd.py` does not already map onto the GISD canonical form.
APP_MECHANISM_ALIASES = {"Bio-fouling": "Bio-fouling or other direct physical disturbance"}


def read_gisd(path: Path = GISD_CLEAN) -> pd.DataFrame:
    """The cleaned GISD export, with `Reference` stripped so it can be matched exactly."""
    gisd = pd.read_csv(path)
    gisd["Reference"] = gisd["Reference"].str.strip()
    return gisd


def merge_countries(rows: pd.DataFrame) -> pd.DataFrame:
    """Merge rows that repeat one impact per country of impact (the app has no country field).

    Rows are grouped on `GOLD_IMPACT_KEY`; their countries are joined into one comma-separated value
    and every other column keeps its first value. Column order and first-seen row order are kept.
    """
    return rows.groupby(GOLD_IMPACT_KEY, dropna=False, sort=False, as_index=False).agg(
        lambda s: ", ".join(dict.fromkeys(s.dropna().astype(str))) if s.name == "Countries of impact" else s.iloc[0]
    )[rows.columns]


def gold_impacts(gold: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """A run's `gold.csv` split per case, in file order; a row's position within its case is its gold index."""
    return {case_id: g.reset_index(drop=True) for case_id, g in gold.groupby("case_id", sort=False)}


def canonical_mechanism(mechanism: str) -> str:
    """The canonical GISD spelling of a mechanism named by GISD or by the app."""
    return normalise_mechanism(APP_MECHANISM_ALIASES.get(mechanism, mechanism))
