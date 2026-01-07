from typing import Dict, List, Tuple

from pydantic_evals.evaluators import (
    Evaluator,
    EvaluatorContext,
    EvaluatorOutput,
)
from sklearn.metrics import classification_report

from eicat_ai.models import Impact

DEFAULT_EVAL_MODEL: str = "bedrock:amazon.nova-lite-v1:0"
DEFAULT_EVAL_PATH: str = "./eval-data"
DEFAULT_MODEL: str = "bedrock:amazon.nova-lite-v1:0"


class AccuracyJudge(Evaluator):
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
        """Evaluate extracted impacts against gold standard.

        Matches the expected impacts with the extracted impacts based on the identified mechanism.

        Args:
            ctx: Evaluation context containing extracted impacts and expected outputs

        Returns:
            Dictionary with confusion matrix values and calculated metrics
        """

        extracted_impacts: List[Impact] = ctx.output
        gold_impacts: List[Impact] = ctx.expected_output

        extracted_mechanisms = set([impact.mechanism for impact in extracted_impacts])
        gold_mechanisms = set([impact.mechanism for impact in gold_impacts])

        tp = len(extracted_mechanisms & gold_mechanisms)
        fp = len(extracted_mechanisms - gold_mechanisms)
        fn = len(gold_mechanisms - extracted_mechanisms)

        return {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            **self.calculate_metrics(tp, fp, fn),
        }
