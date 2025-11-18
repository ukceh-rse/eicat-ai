from dataclasses import dataclass
from pydantic_ai.settings import ModelSettings
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import (
    Evaluator,
    EvaluatorContext,
    EvaluatorOutput,
)
from eicat_ai.models import Paper, Impact, Mechanism, Category, SpeciesNames
from eicat_ai.converters import extract_impacts
from eicat_ai.agents import data_extraction_agent
from typing import List, Tuple, Optional, Dict, Literal
from pydantic_ai import Agent, RunContext
from pydantic import BaseModel, Field
from pathlib import Path
import typer
from typing_extensions import Annotated

evaluation_model: str = "bedrock:anthropic.claude-3-7-sonnet-20250219-v1:0"


class Pairing(BaseModel):
    """Results of LLM-based semantic matching evaluation between predicted and gold standard impacts.

    Contains the pairings between predicted and expected impacts, along with
    confusion matrix values for calculating precision, recall, and F1 metrics.
    """

    prediceted_index: int = Field(..., description="Index of the predicted impact.")
    gold_index: Optional[int] = Field(
        None,
        description="Index of the matched gold impact, or None if no suitable match.",
    )
    justification: str = Field(..., description="Reasoning for the match or mismatch.")


class LLMMatchingEvaluation(BaseModel):
    """Results of LLM-based semantic matching evaluation between predicted and gold standard impacts.

    Contains the pairings between predicted and expected impacts, along with
    confusion matrix values for calculating precision, recall, and F1 metrics.
    """

    pairings: List[Pairing]
    true_positives: int
    false_positives: int
    false_negatives: int


@dataclass
class AccuracyLLMJudge(Evaluator):
    @staticmethod
    def calculate_metrics(tp: int, fp: int, fn: int) -> Dict[str, float]:
        """Calculate precision, recall, and F1 score from confusion matrix values.

        Args:
            tp: True positives
            fp: False positives
            fn: False negatives

        Returns:
            Dict containing precision, recall, and f1 scores
        """
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2 * (precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        return {"precision": precision, "recall": recall, "f1": f1}

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluatorOutput:
        """Evaluate extracted impacts against gold standard using LLM semantic matching.

        Creates an LLM agent that intelligently pairs predicted impacts with gold
        standard impacts based on semantic similarity. The agent considers evidence
        text and impact mechanisms while ignoring formatting differences.

        Args:
            ctx: Evaluation context containing extracted impacts and expected outputs

        Returns:
            Dictionary with confusion matrix values and calculated metrics
        """
        agent: Agent[Tuple[List[Impact], List[Impact]], LLMMatchingEvaluation] = Agent[
            Tuple[List[Impact], List[Impact]], LLMMatchingEvaluation
        ](
            model=evaluation_model,
            output_type=LLMMatchingEvaluation,
            output_retries=2,
            model_settings=ModelSettings(max_tokens=1_000, temperature=0.0),
        )

        @agent.system_prompt
        async def get_system_prompt(
            ctx: RunContext[Tuple[List[Impact], List[Impact]]],
        ) -> str:
            return (
                "You are an expert evaluator of impacts of invasive species that have been automatically extracted from academic texts. "
                "You are given two short lists (<=5 each): predicted impacts from an LLM and gold-standard impacts extracted by a human. "
                "Match predicted impacts to gold impacts if they describe the same invasive species impact "
                "(even if wording differs). Each predicted impact can match at most one gold impact. "
                "If none match, assign None. Then compute TP, FP, FN"
                "Partial overlaps count as correct (TP)."
                "You should consider the evidence text and the impact mechanism when pairing impacts. "
                "Other properties such as the category and the confidence will be evaluated seperately. "
                "===== START OF EXTRACTED IMPACTS ====="
                f"{ctx.deps[0]}"
                "===== END OF EXTRACTED IMPACTS ====="
                "===== START OF GOLD IMPACTS ====="
                f"{ctx.deps[1]}"
                "===== END OF GOLD IMPACTS ====="
            )

        extracted_impacts: List[Impact] = ctx.output
        gold_impacts: List[Impact] = ctx.expected_output

        result = await agent.run(
            "Evaluate the extracted impacts against the gold standard impacts.",
            deps=(extracted_impacts, gold_impacts),
        )
        eval: LLMMatchingEvaluation = result.output
        return {
            "true_positives": eval.true_positives,
            "false_positives": eval.false_positives,
            "false_negatives": eval.false_negatives,
            **self.calculate_metrics(
                eval.true_positives, eval.false_positives, eval.false_negatives
            ),
        }


dataset = Dataset(
    cases=[
        Case(
            name="simple_case",
            inputs={
                "agent": data_extraction_agent(
                    "bedrock:anthropic.claude-3-7-sonnet-20250219-v1:0"
                ),
                "paper": Paper(
                    content="The grey squirrel is alien to the study area. After it's introduction there was a noticable decline in the number of native badgers. This is likely due to the squirrels stealing food."
                ),
                "species": "grey squirrel",
            },
            expected_output=[
                Impact(
                    alien_species="grey squirrel",
                    mechanism=Mechanism.COMPETITION,
                    category=Category.MAJOR,
                    evidence="After it's introduction there was a noticable decline in the number of native badgers. This is likely due to the squirrels stealing food.",
                    confidence="High",
                    justification="The paper reports on clear evidence of badgers numbers reducing.",
                    impacted_species=["badger"],
                ),
                Impact(
                    alien_species="grey squirrel",
                    mechanism=Mechanism.PREDATION,
                    category=Category.MAJOR,
                    evidence="There was evidence of squirells killing infant badgers",
                    confidence="High",
                    justification="The paper reports on clear evidence of badgers young being killed.",
                    impacted_species=["badger"],
                ),
            ],
        ),
    ],
    evaluators=[AccuracyLLMJudge()],
)


async def impact_extraction(inputs: dict) -> List[Impact]:
    return await extract_impacts(inputs["agent"], inputs["paper"], inputs["species"])


def load_dynamic_evaluation_dataset(
    path: str, model_name: str = "bedrock:anthropic.claude-3-7-sonnet-20250219-v1:0"
) -> Dataset:
    cases = []
    for test_case in Path(path).iterdir():
        if not test_case.is_dir():
            continue
        paper = test_case / "paper.json"
        species = test_case / "alien-species.json"
        gold_impacts = test_case / "gold-impacts.csv"
        print(test_case)
        if paper.exists() and species.exists() and gold_impacts.exists():
            cases.append(
                Case(
                    name=test_case.name,
                    inputs={
                        "agent": data_extraction_agent(model_name),
                        "paper": Paper.load(str(paper)),
                        "species": SpeciesNames.load(str(species)),
                    },
                    expected_output=Impact.load_from_csv(str(gold_impacts)),
                )
            )
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
    report.print()


if __name__ == "__main__":
    typer.run(main)
