from pydantic_evals import Case, Dataset
from eicat_ai.models import Paper, Impact, SpeciesNames
from eicat_ai.converters import extract_impacts
from eicat_ai.agents import data_extraction_agent
from typing import List, Literal
from pydantic_ai import Agent
from pathlib import Path
import typer
from typing_extensions import Annotated
from rich.progress import Progress
from eicat_ai.evaluations.evaluators import AccuracyLLMJudge

evaluation_model: str = "bedrock:anthropic.claude-3-7-sonnet-20250219-v1:0"


async def impact_extraction(inputs: dict) -> List[Impact]:
    return await extract_impacts(inputs["agent"], inputs["paper"], inputs["species"])


def load_evaluation_test_case(
    test_case_path: Path, agent: Agent[Paper, List[Impact]]
) -> List[Case]:
    paper_path: Path = test_case_path / "paper.json"
    if not paper_path.exists():
        return []

    paper: Paper = Paper.load(str(paper_path))
    cases: List[Case] = []

    for gold_impacts_path in test_case_path.glob("gold_impacts_*"):
        species_name = (
            gold_impacts_path.name.removeprefix("gold_impacts_")
            .removesuffix(".csv")
            .replace("_", " ")
        )
        cases.append(
            Case(
                name=f"{test_case_path.name} ({species_name})",
                inputs={
                    "agent": agent,
                    "paper": paper,
                    "species": SpeciesNames(
                        scientific_name=species_name, vernacular_names=[]
                    ),
                },
                expected_output=Impact.load_from_csv(str(gold_impacts_path)),
                metadata={"paper": paper.title, "species": species_name},
            )
        )
    return cases


def load_dynamic_evaluation_dataset(
    path: str, model_name: str = "bedrock:anthropic.claude-3-7-sonnet-20250219-v1:0"
) -> Dataset:
    cases = []
    test_case_dirs = [d for d in Path(path).iterdir() if d.is_dir()]
    agent = data_extraction_agent(model_name)
    with Progress() as progress:
        task = progress.add_task(
            "Loading evaluation dataset...", total=len(test_case_dirs)
        )
        for test_case in test_case_dirs:
            cases.extend(load_evaluation_test_case(test_case, agent))
            progress.advance(task)
            progress.update(task, description="Loading evaluation dataset")
    return Dataset(cases=cases, evaluators=[AccuracyLLMJudge()])


MODEL_MAP = {
    "claude": "bedrock:anthropic.claude-3-7-sonnet-20250219-v1:0",
}


def main(
    eval_path: Annotated[
        str, typer.Argument(help="Path to the evaluation dataset directory")
    ],
    model: Annotated[
        Literal["claude"],
        typer.Option("-m", "--model", help="Model name to use for evaluation"),
    ] = "claude",
):
    """Evaluate impact extraction model."""
    eval_dataset: Dataset = load_dynamic_evaluation_dataset(eval_path, MODEL_MAP[model])
    report = eval_dataset.evaluate_sync(impact_extraction)
    report.print(include_metadata=True)


if __name__ == "__main__":
    typer.run(main)
