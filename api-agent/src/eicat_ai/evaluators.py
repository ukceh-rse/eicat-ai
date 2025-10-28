from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import EqualsExpected
from eicat_ai.models import Paper, Impact, Mechanism, Category
from eicat_ai.converters import extract_impacts
from eicat_ai.agents import data_extraction_agent

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
            },
            expected_output=[
                Impact(
                    alien_species="grey squirrel",
                    mechanism=Mechanism.COMPETITION,
                    category=Category.MAJOR,
                    evidence="After it's introduction there was a noticable decline in the number of native badgers. This is likely due to the squirrels stealing food.",
                    confidence="high",
                    justification="The paper reports on clear evidence of badgers numbers reducing.",
                    impacted_species=["badger"],
                )
            ],
        )
    ],
    evaluators=[EqualsExpected()],
)


if __name__ == "__main__":
    report = dataset.evaluate_sync(extract_impacts)
    report.print()
