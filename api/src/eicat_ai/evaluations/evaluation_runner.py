import datetime
from pathlib import Path
from typing import List, Literal

import typer
from pydantic_ai import Agent
from pydantic_evals import Case, Dataset
from pydantic_evals.reporting import EvaluationReport, ReportCase
from rich.progress import Progress
from typing_extensions import Annotated

from eicat_ai.agents import data_extraction_agent
from eicat_ai.converters import extract_impacts
from eicat_ai.evaluations.evaluators import (
    DEFAULT_EVAL_PATH,
    DEFAULT_MODEL,
    AccuracyJudge,
)
from eicat_ai.models import Impact, Paper, SpeciesNames


async def impact_extraction(inputs: dict) -> List[Impact]:
    return await extract_impacts(inputs["agent"], inputs["paper"], inputs["species"])


def load_evaluation_test_case(
    test_case_path: Path, agent: Agent[Paper, List[Impact]]
) -> List[Case]:
    paper_path: Path = test_case_path / "paper.md"
    if not paper_path.exists():
        return []

    with open(paper_path, "r", encoding="utf-8") as file:
        paper_content = file.read()

    paper: Paper = Paper(content=paper_content)
    cases: List[Case] = []

    for gold_impacts_path in test_case_path.glob("gold_impacts_*"):
        species_name_underscored = gold_impacts_path.name.removeprefix(
            "gold_impacts_"
        ).removesuffix(".csv")
        species_name = species_name_underscored.replace("_", " ")
        cases.append(
            Case(
                name=f"{test_case_path.name}",
                inputs={
                    "agent": agent,
                    "paper": paper,
                    "species": SpeciesNames(
                        scientific_name=species_name, vernacular_names=[]
                    ),
                },
                expected_output=Impact.load_from_csv(str(gold_impacts_path)),
                metadata={
                    "paper": paper.title,
                    "species": species_name,
                    "output": f"{test_case_path.name}/impacts_{species_name_underscored}.csv",
                },
            )
        )
    return cases


def load_dynamic_evaluation_dataset(
    path: Path, model_name: str = DEFAULT_MODEL
) -> Dataset:
    cases = []
    test_case_dirs = [d for d in path.iterdir() if d.is_dir()]
    agent = data_extraction_agent(model_name)
    with Progress() as progress:
        task = progress.add_task(
            "Loading evaluation dataset...", total=len(test_case_dirs)
        )
        for test_case in test_case_dirs:
            cases.extend(load_evaluation_test_case(test_case, agent))
            progress.advance(task)
            progress.update(task, description="Loading evaluation dataset")
    return Dataset(cases=cases, evaluators=[AccuracyJudge()])


MODEL_MAP = {
    "claude": "bedrock:anthropic.claude-3-7-sonnet-20250219-v1:0",
}


def save_evaluation_output(p: Path, cases: list[ReportCase]) -> None:
    for case in cases:
        case_path = p / case.metadata["output"]
        case_path.parent.mkdir(parents=True, exist_ok=True)
        Impact.save_to_csv(case.output, str(case_path))


def generate_eval_output_path() -> Path:
    ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    return Path(f"eicat_ai_eval_{ts}")


def main(
    data_path: Annotated[
        Path,
        typer.Option(
            "-i", "--input-path", help="Path to the evaluation data directory."
        ),
    ] = Path(DEFAULT_EVAL_PATH),
    model: Annotated[
        Literal["claude"],
        typer.Option("-m", "--model", help="Model name to use for evaluation"),
    ] = "claude",
    output_path: Annotated[
        Path,
        typer.Option("-o", "--output-path", help="Path to save generated output to."),
    ] = generate_eval_output_path(),
):
    """Evaluate impact extraction model."""
    eval_dataset: Dataset = load_dynamic_evaluation_dataset(data_path, MODEL_MAP[model])
    report: EvaluationReport = eval_dataset.evaluate_sync(
        impact_extraction, max_concurrency=5
    )

    report.print(include_metadata=True)

    save_evaluation_output(output_path, report.cases)


if __name__ == "__main__":
    typer.run(main)
