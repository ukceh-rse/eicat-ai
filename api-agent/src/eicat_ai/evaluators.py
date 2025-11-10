from dataclasses import dataclass
from pydantic_ai.settings import ModelSettings
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import (
    LLMJudge,
    Evaluator,
    EvaluatorContext,
    EvaluatorOutput,
)
from eicat_ai.models import Paper, Impact, Mechanism, Category, F1Evaluation
from eicat_ai.converters import extract_impacts
from eicat_ai.agents import data_extraction_agent
from typing import List

evidence_recall_llm_judge = LLMJudge(
    rubric="""
    Based on the evidence field, determine the recall metric of the impacts that were automatically extract.
    You should ignore if the impact has been labelled differently in other fields. 
    Only consider whether the evidence of each impact is consistent with the expected output.
    """,
    include_input=True,
    include_expected_output=True,
    score={"evaluation_name": "recall"},
    assertion=False,
    model_settings=ModelSettings(temperature=0.0),
    model="bedrock:anthropic.claude-3-7-sonnet-20250219-v1:0",
)


@dataclass
class AccuracyLLMJudge(Evaluator):
    async def evaluate(self, ctx: EvaluatorContext) -> EvaluatorOutput:
        return {"precision": 0.0, "recall": 0.0, "f1_score": 0.0}


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
                )
            ],
        )
    ],
    evaluators=[evidence_recall_llm_judge, AccuracyLLMJudge()],
)


async def evaluate_extract_impacts(inputs: dict) -> List[Impact]:
    return await extract_impacts(inputs["agent"], inputs["paper"], inputs["species"])


if __name__ == "__main__":
    report = dataset.evaluate_sync(evaluate_extract_impacts)
    report.print()
