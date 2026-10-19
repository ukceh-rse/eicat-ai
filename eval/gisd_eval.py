"""Evaluate the EICAT AI application end-to-end against GISD impact assessments.

Papers are PDFs downloaded by hand into a flat directory (`gisd_data/` by default), each named
as in the reference library page (`references.html`) built by `utils/library.py`.
Every paper is pushed through the real application stack (upload -> GROBID/TEI conversion ->
one analysis per GISD species for that reference), an LLM judge pairs the extracted impacts
with the GISD rows for the same reference and species, and the pairs are scored into a report.

Each stage reads the previous stage's files from the run directory, so any can be re-run alone:

    uv run --project eval eval/gisd_eval.py fetch                    # latest GISD + reference library
    uv run --project eval eval/gisd_eval.py extract                  # start stack, extract -> eval/runs/<new>
    uv run --project eval eval/gisd_eval.py judge  eval/runs/<run>   # pair impacts with GISD (Bedrock)
    uv run --project eval eval/gisd_eval.py score  eval/runs/<run>   # metrics.json + CSVs
    uv run --project eval eval/gisd_eval.py report eval/runs/<run>   # report.md + figures
    uv run --project eval eval/gisd_eval.py run                      # all four stages after fetch
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

import httpx
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "utils"))
from library import load_library  # noqa: E402

from gisd_judge import DEFAULT_MODEL, judge  # noqa: E402
from gisd_report import report  # noqa: E402
from gisd_score import score  # noqa: E402

DEFAULT_DATA_DIR = REPO / "gisd_data"
DEFAULT_RUNS_DIR = REPO / "eval" / "runs"
DEFAULT_API_URL = "http://localhost:18000"
FEWSHOT_EXAMPLES = REPO / "api" / "src" / "eicat_ai" / "fewshot_examples.json"  # built by build_fewshot.py
COMPOSE = [
    "docker", "compose", "-p", "eicat-gisd-eval",
    "-f", str(REPO / "docker-compose.yml"),
    "-f", str(REPO / "eval" / "compose.gisd-eval.yml"),
]  # fmt: skip

POLL_SECONDS = 5
PAPER_TIMEOUT = 15 * 60
ANALYSIS_TIMEOUT = 60 * 60


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


GOLD_IMPACT_KEY = ["Impact mechanism", "EICAT Category", "Evidence for EICAT impact category", "Impacted native species"]


def merge_countries(rows: pd.DataFrame) -> pd.DataFrame:
    """GISD repeats an impact once per country of impact; the app has no country field, so merge those rows."""
    return rows.groupby(GOLD_IMPACT_KEY, dropna=False, sort=False, as_index=False).agg(
        lambda s: ", ".join(dict.fromkeys(s.dropna().astype(str))) if s.name == "Countries of impact" else s.iloc[0]
    )[rows.columns]


def load_cases(data_dir: Path, manifest_path: Path, gisd_path: Path) -> tuple[list[dict], pd.DataFrame]:
    """Pair each PDF with its GISD reference, giving one case per (PDF, species)."""
    refs_by_file: dict[str, list[str]] = {}
    for entry in load_library(manifest_path):
        refs_by_file.setdefault(entry["file"], []).append(entry["reference"])
    gisd = pd.read_csv(gisd_path)
    gisd["Reference"] = gisd["Reference"].str.strip()
    # references shown to the extraction model as few-shot examples must never be scored
    fewshot = {e["reference"] for e in json.loads(FEWSHOT_EXAMPLES.read_text())} if FEWSHOT_EXAMPLES.exists() else set()

    cases, gold = [], []
    for pdf in sorted(p for p in data_dir.iterdir() if p.suffix.lower() == ".pdf"):
        refs = refs_by_file.get(pdf.name, [])
        if len(refs) != 1:
            reason = "not in the library" if not refs else f"matches {len(refs)} references in the library"
            print(f"  ! skipping {pdf.name}: {reason}")
            continue
        if refs[0] in fewshot:
            print(f"  ! skipping {pdf.name}: its reference is a few-shot example in {FEWSHOT_EXAMPLES.name}")
            continue
        rows = gisd[gisd["Reference"] == refs[0]]
        if rows.empty:
            print(f"  ! skipping {pdf.name}: reference has no GISD EICAT rows in {gisd_path.name}")
            continue
        for species, group in rows.groupby("Species"):
            case_id = f"{pdf.stem}__{re.sub(r'\W+', '_', species)}"
            cases.append({"case_id": case_id, "pdf": pdf.name, "reference": refs[0], "species": species})
            gold.append(merge_countries(group).assign(case_id=case_id))
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


def save_record(extracted_dir: Path, case: dict, status: str, error: str | None, impacts: list, usage: dict | None = None) -> None:
    record = {**case, "model": os.environ.get("EICAT_MODEL"), "status": status, "error": error, "impacts": impacts, "usage": usage or {}}
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
                save_record(extracted_dir, case, analysis["status"], analysis["error"], impacts, analysis.get("usage"))
            except Exception as e:
                save_record(extracted_dir, case, "failed", str(e) or repr(e), [])


async def extract_all(cases: list[dict], data_dir: Path, extracted_dir: Path, api_url: str, concurrency: int) -> None:
    by_pdf: dict[str, list[dict]] = {}
    for case in cases:
        by_pdf.setdefault(case["pdf"], []).append(case)
    sem = asyncio.Semaphore(concurrency)
    # no keep-alive: uvicorn drops idle connections after 5s, the same as POLL_SECONDS, and a request sent
    # on a connection it is closing fails with "Server disconnected without sending a response"
    limits = httpx.Limits(max_keepalive_connections=0)
    async with httpx.AsyncClient(base_url=api_url, timeout=120, limits=limits) as client:
        await asyncio.gather(*(extract_pdf(client, sem, data_dir / pdf, cs, extracted_dir) for pdf, cs in by_pdf.items()))


def extract(args: argparse.Namespace) -> Path:
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
    return out


# ── cli ───────────────────────────────────────────────────────────────────────


def add_extract_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="Directory of manually downloaded PDFs.")
    p.add_argument("--manifest", type=Path, help="Reference library page from utils/library.py. Default: <data-dir>/references.html")
    p.add_argument("--gisd", type=Path, help="Cleaned GISD CSV. Default: <data-dir>/gisd_clean.csv")
    p.add_argument("--out", type=Path, help="Run directory; pass an existing one to resume. Default: eval/runs/<timestamp>")
    p.add_argument("--api-url", default=DEFAULT_API_URL)
    p.add_argument("--concurrency", type=int, default=4, help="PDFs processed in parallel.")
    p.add_argument("--down", action="store_true", help="Tear down the eval stack and its database afterwards.")


def add_judge_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--judge-model", default=DEFAULT_MODEL, help="Pydantic AI model id for the judge.")
    p.add_argument("--judge-concurrency", type=int, default=4, help="Cases judged in parallel.")
    p.add_argument("--force-judge", action="store_true", help="Re-judge cases that already have a judgement.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("fetch", help="Download the latest GISD data and build or refresh the reference library page.")
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p.add_argument("--force", action="store_true", help="Re-download GISD even if gisd.xlsx exists.")

    add_extract_args(sub.add_parser("extract", help="Start the app stack and extract impacts from every PDF."))
    add_judge_args(p := sub.add_parser("judge", help="Pair a run's extracted impacts with its GISD impacts using an LLM judge."))
    p.add_argument("run_dir", type=Path)
    sub.add_parser("score", help="Compute metrics for a judged run.").add_argument("run_dir", type=Path)
    sub.add_parser("report", help="Write report.md and figures for a scored run.").add_argument("run_dir", type=Path)
    p = sub.add_parser("run", help="extract, judge, score and report in one go.")
    add_extract_args(p)
    add_judge_args(p)

    args = parser.parse_args()
    sys.stdout.reconfigure(line_buffering=True)  # keep our output in order with docker's when piped
    if args.command == "fetch":
        fetch(args.data_dir, args.force)
        return
    run_dir = extract(args) if args.command in ("extract", "run") else args.run_dir
    if args.command in ("judge", "run"):
        judge(run_dir, args.judge_model, args.judge_concurrency, args.force_judge)
    if args.command in ("score", "run"):
        score(run_dir)
    if args.command in ("report", "run"):
        report(run_dir)


if __name__ == "__main__":
    main()
