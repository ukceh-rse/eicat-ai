"""Evaluate the EICAT AI application end-to-end against GISD impact assessments.

Papers are PDFs downloaded by hand into a flat directory (`gisd_data/` by default), each named
as in the reference library page (`references.html`) built by `utils/library.py`.
Every paper is pushed through the real application stack (upload -> GROBID/TEI conversion ->
one analysis per GISD species for that reference) and the extracted impacts are scored
against the GISD rows for the same reference and species.

    uv run --project eval eval/gisd_eval.py fetch                  # latest GISD + reference library
    uv run --project eval eval/gisd_eval.py run                    # start stack, extract, score
    uv run --project eval eval/gisd_eval.py score eval/runs/<run>  # re-score a finished run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from statistics import fmean

import httpx
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "utils"))
from gisd import normalise_mechanism  # noqa: E402
from library import load_library  # noqa: E402

DEFAULT_DATA_DIR = REPO / "gisd_data"
DEFAULT_RUNS_DIR = REPO / "eval" / "runs"
DEFAULT_API_URL = "http://localhost:18000"
COMPOSE = [
    "docker", "compose", "-p", "eicat-gisd-eval",
    "-f", str(REPO / "docker-compose.yml"),
    "-f", str(REPO / "eval" / "compose.gisd-eval.yml"),
]  # fmt: skip

POLL_SECONDS = 5
PAPER_TIMEOUT = 15 * 60
ANALYSIS_TIMEOUT = 60 * 60

CAT_SEVERITY = {"MV": 5, "MR": 4, "MO": 3, "MN": 2, "MC": 1, "DD": 0}
# App mechanism names that utils/gisd.py does not already map onto the GISD canonical form.
APP_MECHANISM_ALIASES = {"Bio-fouling": "Bio-fouling or other direct physical disturbance"}


# ── fetch ─────────────────────────────────────────────────────────────────────


def utils_script(name: str, *args: str) -> None:
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}  # don't leak eval's venv into utils'
    subprocess.run(["uv", "run", "--project", str(REPO / "utils"), str(REPO / "utils" / name), *args], check=True, env=env)


def fetch(data_dir: Path, force: bool) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    raw, clean, library = data_dir / "gisd.xlsx", data_dir / "gisd_clean.csv", data_dir / "references.html"
    utils_script("download.py", "--output", str(raw), *(["--force"] if force else []))
    utils_script("filter_clean.py", "--input", str(raw), "--output", str(clean), "--include-dd")
    utils_script("library.py", "build", "--gisd", str(clean), "--output", str(library))
    print(f"\nOpen {library} (or `uv run utils/library.py serve {library}`) to find and download the papers.")


# ── cases ─────────────────────────────────────────────────────────────────────


def load_cases(data_dir: Path, manifest_path: Path, gisd_path: Path) -> tuple[list[dict], pd.DataFrame]:
    """Pair each PDF with its GISD reference, giving one case per (PDF, species)."""
    refs_by_file: dict[str, list[str]] = {}
    for entry in load_library(manifest_path):
        refs_by_file.setdefault(entry["file"], []).append(entry["reference"])
    gisd = pd.read_csv(gisd_path)
    gisd["Reference"] = gisd["Reference"].str.strip()

    cases, gold = [], []
    for pdf in sorted(p for p in data_dir.iterdir() if p.suffix.lower() == ".pdf"):
        refs = refs_by_file.get(pdf.name, [])
        if len(refs) != 1:
            reason = "not in the library" if not refs else f"matches {len(refs)} references in the library"
            print(f"  ! skipping {pdf.name}: {reason}")
            continue
        rows = gisd[gisd["Reference"] == refs[0]]
        if rows.empty:
            print(f"  ! skipping {pdf.name}: reference has no GISD EICAT rows in {gisd_path.name}")
            continue
        for species, group in rows.groupby("Species"):
            case_id = f"{pdf.stem}__{re.sub(r'\W+', '_', species)}"
            cases.append({"case_id": case_id, "pdf": pdf.name, "reference": refs[0], "species": species})
            gold.append(group.assign(case_id=case_id))
    return cases, pd.concat(gold) if gold else pd.DataFrame()


# ── extraction via the app API ────────────────────────────────────────────────


async def wait_for(client: httpx.AsyncClient, url: str, done: set[str], timeout: float) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        response = await client.get(url)
        response.raise_for_status()
        body = response.json()
        if body["status"] in done:
            return body
        if asyncio.get_running_loop().time() > deadline:
            raise TimeoutError(f"{url} still '{body['status']}' after {timeout}s")
        await asyncio.sleep(POLL_SECONDS)


async def post(client: httpx.AsyncClient, url: str, **kwargs) -> dict:
    response = await client.post(url, **kwargs)
    response.raise_for_status()
    return response.json()


def save_record(extracted_dir: Path, case: dict, status: str, error: str | None, impacts: list) -> None:
    record = {**case, "model": os.environ.get("EICAT_MODEL"), "status": status, "error": error, "impacts": impacts}
    (extracted_dir / f"{case['case_id']}.json").write_text(json.dumps(record, indent=2))
    print(f"  {case['case_id']}: {status}" + (f" ({len(impacts)} impacts)" if status == "completed" else f" - {error}"))


async def extract_pdf(client: httpx.AsyncClient, sem: asyncio.Semaphore, pdf: Path, cases: list[dict], extracted_dir: Path) -> None:
    async with sem:
        try:
            paper = await post(client, "/papers/", files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")})
            paper = await wait_for(client, f"/papers/{paper['id']}", {"ready", "failed"}, PAPER_TIMEOUT)
            if paper["status"] == "failed":
                raise RuntimeError(f"paper conversion failed: {paper['error']}")
        except Exception as e:
            for case in cases:
                save_record(extracted_dir, case, "failed", str(e) or repr(e), [])
            return

        for case in cases:
            try:
                analysis = await post(client, "/analyses/", json={"scientific_name": case["species"], "vernacular_names": []})
                await post(client, f"/analyses/{analysis['id']}/papers/{paper['id']}")
                await post(client, f"/analyses/{analysis['id']}/run")
                analysis = await wait_for(client, f"/analyses/{analysis['id']}", {"completed", "failed"}, ANALYSIS_TIMEOUT)
                impacts = analysis["results"].get(paper["id"], [])
                save_record(extracted_dir, case, analysis["status"], analysis["error"], impacts)
            except Exception as e:
                save_record(extracted_dir, case, "failed", str(e) or repr(e), [])


async def extract_all(cases: list[dict], data_dir: Path, extracted_dir: Path, api_url: str, concurrency: int) -> None:
    by_pdf: dict[str, list[dict]] = {}
    for case in cases:
        by_pdf.setdefault(case["pdf"], []).append(case)
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(base_url=api_url, timeout=120) as client:
        await asyncio.gather(*(extract_pdf(client, sem, data_dir / pdf, cs, extracted_dir) for pdf, cs in by_pdf.items()))


def run(args: argparse.Namespace) -> None:
    out: Path = args.out or DEFAULT_RUNS_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
    extracted_dir = out / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)

    cases, gold = load_cases(args.data_dir, args.manifest or args.data_dir / "references.html", args.gisd or args.data_dir / "gisd_clean.csv")
    if not cases:
        sys.exit(f"No evaluable PDFs found in {args.data_dir}")
    gold.to_csv(out / "gold.csv", index=False)

    # resuming into an existing --out only re-runs cases that have not completed
    done = {p.stem for p in extracted_dir.glob("*.json") if json.loads(p.read_text())["status"] == "completed"}
    todo = [c for c in cases if c["case_id"] not in done]
    print(f"{len(cases)} cases from {len({c['pdf'] for c in cases})} PDFs; {len(todo)} to extract -> {out}")

    try:
        if todo:
            if subprocess.run([*COMPOSE, "up", "-d", "--build", "--wait", "--wait-timeout", "900", "eicat-ai-api"]).returncode:
                sys.exit(f"Eval stack failed to become healthy; inspect with: {' '.join(COMPOSE)} logs")
            asyncio.run(extract_all(todo, args.data_dir, extracted_dir, args.api_url, args.concurrency))
    finally:
        if args.down:
            subprocess.run([*COMPOSE, "down", "-v"], check=True)
    score(out)


# ── scoring ───────────────────────────────────────────────────────────────────


def canonical_mechanism(mechanism: str) -> str:
    return normalise_mechanism(APP_MECHANISM_ALIASES.get(mechanism, mechanism))


def max_category(categories) -> str | None:
    known = [c for c in categories if c in CAT_SEVERITY]
    return max(known, key=CAT_SEVERITY.get) if known else None


def max_by_mechanism(pairs) -> dict[str, str | None]:
    """Most severe category per mechanism; GISD and the app can both list a mechanism more than once."""
    grouped: dict[str, list[str]] = {}
    for mechanism, category in pairs:
        grouped.setdefault(canonical_mechanism(mechanism), []).append(category)
    return {m: max_category(cats) for m, cats in grouped.items()}


def distance(a: str | None, b: str | None) -> int | None:
    """Ordinal gap in category steps; undefined when either side is missing or Data Deficient."""
    if a in (None, "DD") or b in (None, "DD"):
        return None
    return abs(CAT_SEVERITY[a] - CAT_SEVERITY[b])


def prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def agreement(rows: list[dict], exact_key: str, distance_key: str) -> dict:
    distances = [r[distance_key] for r in rows if r[distance_key] is not None]
    return {
        "n": len(rows),
        "exact_accuracy": fmean(r[exact_key] for r in rows) if rows else None,
        "n_ordinal": len(distances),
        "mean_abs_distance": fmean(distances) if distances else None,
    }


def score(run_dir: Path) -> None:
    gold = pd.read_csv(run_dir / "gold.csv")
    records = {p.stem: json.loads(p.read_text()) for p in (run_dir / "extracted").glob("*.json")}

    case_rows, match_rows, impact_rows, failures = [], [], [], []
    for case_id, g in gold.groupby("case_id"):
        record = records.get(case_id)
        if record is None or record["status"] != "completed":
            failures.append({"case_id": case_id, "error": record["error"] if record else "not run"})
            continue
        impacts = record["impacts"]
        impact_rows += [{"case_id": case_id, **i, "impacted_species": "; ".join(i["impacted_species"])} for i in impacts]

        gold_mech = max_by_mechanism(zip(g["Impact mechanism"], g["EICAT Category"]))
        ext_mech = max_by_mechanism((i["mechanism"], i["category"]) for i in impacts)
        matched = sorted(gold_mech.keys() & ext_mech.keys())
        for m in matched:
            match_rows.append({
                "case_id": case_id, "mechanism": m,
                "gold_category": gold_mech[m], "extracted_category": ext_mech[m],
                "exact": gold_mech[m] == ext_mech[m], "distance": distance(gold_mech[m], ext_mech[m]),
            })  # fmt: skip

        tp, fp, fn = len(matched), len(ext_mech.keys() - gold_mech.keys()), len(gold_mech.keys() - ext_mech.keys())
        gold_max, ext_max = max_category(g["EICAT Category"]), max_category(i["category"] for i in impacts)
        case_rows.append({
            "case_id": case_id, "pdf": record["pdf"], "species": record["species"],
            "gold_mechanisms": "; ".join(sorted(gold_mech)), "extracted_mechanisms": "; ".join(sorted(ext_mech)),
            "tp": tp, "fp": fp, "fn": fn, **prf(tp, fp, fn),
            "gold_max_category": gold_max, "extracted_max_category": ext_max,
            "max_category_exact": gold_max == ext_max, "max_category_distance": distance(gold_max, ext_max),
        })  # fmt: skip

    tp, fp, fn = (sum(r[k] for r in case_rows) for k in ("tp", "fp", "fn"))
    metrics = {
        "n_cases_scored": len(case_rows),
        "n_cases_failed": len(failures),
        "mechanism": {
            "micro": {"tp": tp, "fp": fp, "fn": fn, **prf(tp, fp, fn)},
            "macro": {k: fmean(r[k] for r in case_rows) if case_rows else None for k in ("precision", "recall", "f1")},
        },
        "category_on_matched_mechanisms": agreement(match_rows, "exact", "distance"),
        "max_category": agreement(case_rows, "max_category_exact", "max_category_distance"),
        "failures": failures,
    }

    pd.DataFrame(case_rows).to_csv(run_dir / "cases.csv", index=False)
    pd.DataFrame(match_rows).to_csv(run_dir / "matches.csv", index=False)
    pd.DataFrame(impact_rows).to_csv(run_dir / "impacts.csv", index=False)
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print_summary(metrics, run_dir)


def print_summary(m: dict, run_dir: Path) -> None:
    fmt = lambda v: "-" if v is None else f"{v:.3f}"  # noqa: E731
    micro, macro = m["mechanism"]["micro"], m["mechanism"]["macro"]
    print(f"\nScored {m['n_cases_scored']} cases ({m['n_cases_failed']} failed/not run)")
    print(f"Mechanism  micro P/R/F1 {fmt(micro['precision'])} / {fmt(micro['recall'])} / {fmt(micro['f1'])}"
          f"  (tp={micro['tp']} fp={micro['fp']} fn={micro['fn']})")  # fmt: skip
    print(f"           macro P/R/F1 {fmt(macro['precision'])} / {fmt(macro['recall'])} / {fmt(macro['f1'])}")
    for label, key in (("Category on matched mechanisms", "category_on_matched_mechanisms"), ("Max category per case", "max_category")):
        a = m[key]
        print(f"{label}: exact {fmt(a['exact_accuracy'])} (n={a['n']}), mean |distance| {fmt(a['mean_abs_distance'])} (n={a['n_ordinal']})")
    for f in m["failures"]:
        print(f"  ! {f['case_id']}: {f['error']}")
    print(f"Results written to {run_dir}")


# ── cli ───────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("fetch", help="Download the latest GISD data and build or refresh the reference library page.")
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p.add_argument("--force", action="store_true", help="Re-download GISD even if gisd.xlsx exists.")

    p = sub.add_parser("run", help="Start the app stack, extract impacts from every PDF, then score.")
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="Directory of manually downloaded PDFs.")
    p.add_argument("--manifest", type=Path, help="Reference library page from utils/library.py. Default: <data-dir>/references.html")
    p.add_argument("--gisd", type=Path, help="Cleaned GISD CSV. Default: <data-dir>/gisd_clean.csv")
    p.add_argument("--out", type=Path, help="Run directory; pass an existing one to resume. Default: eval/runs/<timestamp>")
    p.add_argument("--api-url", default=DEFAULT_API_URL)
    p.add_argument("--concurrency", type=int, default=4, help="PDFs processed in parallel.")
    p.add_argument("--down", action="store_true", help="Tear down the eval stack and its database afterwards.")

    p = sub.add_parser("score", help="Re-score an existing run directory.")
    p.add_argument("run_dir", type=Path)

    args = parser.parse_args()
    sys.stdout.reconfigure(line_buffering=True)  # keep our output in order with docker's when piped
    if args.command == "fetch":
        fetch(args.data_dir, args.force)
    elif args.command == "run":
        run(args)
    else:
        score(args.run_dir)


if __name__ == "__main__":
    main()
