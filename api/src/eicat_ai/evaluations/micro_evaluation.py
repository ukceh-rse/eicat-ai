from pathlib import Path
from typing import Annotated

import typer

from eicat_ai.evaluations.evaluators import DEFAULT_EVAL_PATH


def main(
    eval_path: Annotated[
        Path,
        typer.Option("-e", "--eval-path", help="Path to the evaluation run."),
    ],
    data_path: Annotated[
        Path,
        typer.Option(
            "-i", "--input-path", help="Path to the evaluation data directory."
        ),
    ] = Path(DEFAULT_EVAL_PATH),
) -> None:
    for csv in eval_path.glob("*.csv"):
        gold_impacts_path = data_path / csv.stem
        print(csv.stem)


if __name__ == "__main__":
    typer.run(main)
