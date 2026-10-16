"""LLM-as-judge: pair the impacts the app extracted with the GISD impacts for the same case.

Pairing is judged on the impact described (evidence text and impacted species) only; mechanism
and category labels are hidden from the judge so that label agreement can be scored afterwards
without the matching having been biased towards it. Each GISD impact pairs with at most one
extracted impact and vice versa.

One file per case is written to `<run>/judged/<case_id>.json` and reused on later runs unless
its extraction is newer or `--force` is given, so `score` never needs to call the model.
Needs AWS credentials with Bedrock access.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelSettings

DEFAULT_MODEL = "bedrock:anthropic.claude-3-7-sonnet-20250219-v1:0"

SYSTEM_PROMPT = """You compare two independent EICAT impact assessments of the same paper and alien species.
GOLD impacts were recorded by a human expert; EXTRACTED impacts by an automated system. Each impact is
an evidence passage from the paper plus the native taxa it affects, tagged G<n> or E<n>.

Pair each EXTRACTED impact with the GOLD impact describing the SAME underlying ecological impact
(the same effect of the alien species on the same native taxa or ecosystem property).

Rules:
- Judge only by the impact described; the two sides may quote different passages about the same impact.
- Each G and each E may appear in at most one pair. If several E describe one G, pair the closest one.
- Leave an impact unpaired when the other side has no impact describing it. Do not force pairs.
- Impacts on different native taxa, or different kinds of effect, are different impacts."""


class Pair(BaseModel):
    gold: str = Field(description="Gold impact id, e.g. G0.")
    extracted: str = Field(description="Extracted impact id, e.g. E2.")
    reason: str = Field(description="One sentence on why these describe the same impact.")


class Pairing(BaseModel):
    pairs: list[Pair]


def gold_impacts(gold: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """GISD rows per case, in file order; a row's position within its case is its gold index."""
    return {case_id: g.reset_index(drop=True) for case_id, g in gold.groupby("case_id", sort=False)}


def describe(tag: str, evidence, species) -> str:
    species = species if isinstance(species, str) and species.strip() else "not stated"
    return f"[{tag}] Impacted taxa: {species}\nEvidence: {evidence if isinstance(evidence, str) else ''}"


def prompt(record: dict, gold: pd.DataFrame) -> str:
    gold_text = "\n\n".join(
        describe(f"G{i}", r["Evidence for EICAT impact category"], r["Impacted native species"]) for i, r in gold.iterrows()
    )
    ext_text = "\n\n".join(
        describe(f"E{i}", imp["evidence"], "; ".join(imp["impacted_species"])) for i, imp in enumerate(record["impacts"])
    )
    return f"Alien species: {record['species']}\nPaper: {record['reference']}\n\nGOLD impacts:\n{gold_text}\n\nEXTRACTED impacts:\n{ext_text}"


def one_to_one(pairing: Pairing, n_gold: int, n_extracted: int, case_id: str) -> list[dict]:
    """Keep the first valid pair for each index; the model occasionally reuses or invents ids."""
    used_gold, used_ext, pairs = set(), set(), []
    for p in pairing.pairs:
        try:
            g, e = int(p.gold.lstrip("Gg")), int(p.extracted.lstrip("Ee"))
        except ValueError:
            g = e = -1
        if not (0 <= g < n_gold and 0 <= e < n_extracted) or g in used_gold or e in used_ext:
            print(f"  · {case_id}: dropped pair {p.gold}-{p.extracted} (unknown or already paired)")
            continue
        used_gold.add(g)
        used_ext.add(e)
        pairs.append({"gold": g, "extracted": e, "reason": p.reason})
    return pairs


async def judge_case(agent: Agent, sem: asyncio.Semaphore, record: dict, gold: pd.DataFrame, out: Path, model: str) -> None:
    pairs = []
    if record["impacts"]:  # nothing to pair otherwise, so skip the call
        async with sem:
            result = await agent.run(prompt(record, gold))
        pairs = one_to_one(result.output, len(gold), len(record["impacts"]), record["case_id"])
    out.write_text(json.dumps({"case_id": record["case_id"], "model": model, "pairs": pairs}, indent=2))
    print(f"  {record['case_id']}: {len(pairs)} pairs ({len(gold)} gold, {len(record['impacts'])} extracted)")


async def judge_all(todo: list[tuple[dict, pd.DataFrame, Path]], model: str, concurrency: int) -> None:
    agent = Agent(model, output_type=Pairing, system_prompt=SYSTEM_PROMPT, model_settings=ModelSettings(temperature=0.0, max_tokens=4000))
    sem = asyncio.Semaphore(concurrency)
    results = await asyncio.gather(*(judge_case(agent, sem, r, g, out, model) for r, g, out in todo), return_exceptions=True)
    for (record, _, _), result in zip(todo, results):
        if isinstance(result, Exception):
            print(f"  ! {record['case_id']}: judge failed - {result!r}")


def judge(run_dir: Path, model: str = DEFAULT_MODEL, concurrency: int = 4, force: bool = False) -> None:
    gold = gold_impacts(pd.read_csv(run_dir / "gold.csv"))
    judged_dir = run_dir / "judged"
    judged_dir.mkdir(exist_ok=True)

    todo = []
    for path in sorted((run_dir / "extracted").glob("*.json")):
        record = json.loads(path.read_text())
        out = judged_dir / path.name
        if record["status"] != "completed" or record["case_id"] not in gold:
            continue
        if not force and out.exists() and out.stat().st_mtime >= path.stat().st_mtime:
            continue  # already judged against this extraction
        todo.append((record, gold[record["case_id"]], out))

    print(f"Judging {len(todo)} cases with {model} -> {judged_dir}")
    if todo:
        asyncio.run(judge_all(todo, model, concurrency))
