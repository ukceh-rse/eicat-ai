"""Reading scored GISD evaluation runs (directories written by `gisd_eval.py`).

A scored run holds `metrics.json` (see `gisd_score.py` for its structure), `cases.csv` (one row per
paper x species case) and the per-impact `pairs.csv` and `impacts.csv`.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from eicat_eval.paths import RUNS


def run_dir(run: str | Path) -> Path:
    """A run given by name resolves under `paths.RUNS`; a path is used as is."""
    return Path(run) if isinstance(run, Path) else RUNS / run


def read_metrics(run: str | Path) -> dict:
    return json.loads((run_dir(run) / "metrics.json").read_text())


def read_cases(run: str | Path) -> pd.DataFrame:
    return pd.read_csv(run_dir(run) / "cases.csv")


def class_accuracy(metrics: dict, field: str, label: str) -> tuple[float, int]:
    """(accuracy, support) of one class on matched pairs: the share of GISD impacts of this class that the app
    gave the same label, and how many there were. Classes GISD never used give (nan, 0).

    `field` is "category" or "mechanism"; `label` a category code or canonical mechanism name.
    """
    row = metrics["labels"][field]["matched"]["per_class"].get(label)
    return (row["recall"], row["support"]) if row and row["support"] else (np.nan, 0)
