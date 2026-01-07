"""CLI for evaluation commands."""

import sys
from pathlib import Path
from typing import Literal

import typer
from loguru import logger
from typing_extensions import Annotated

from eicat_ai.evaluations.data_fetcher import main as fetch_main
from eicat_ai.evaluations.data_prepper import main as prepare_main
from eicat_ai.evaluations.evaluation_runner import main as run_main
from eicat_ai.evaluations.evaluators import DEFAULT_EVAL_PATH
from eicat_ai.evaluations.micro_evaluation import main as eval_main

logger.remove()
logger.add(sys.stderr, level="INFO")
app = typer.Typer(help="EICAT evaluation tools")


@app.command("fetch")
def fetch_command(
    output_path: Annotated[
        Path,
        typer.Option(
            "-o",
            "--output-path",
            help="Path to save the evaluation data to.",
        ),
    ] = Path(DEFAULT_EVAL_PATH),
) -> None:
    """Download and structure evaluation data from GISD."""
    fetch_main(output_path)
    print(
        f"Data fetched and saved to {output_path}. ",
        'Please follow the links "reference.html" and download any PDFs wanted for evaluation. ',
        'Then run "evals prepare". ',
    )


@app.command("prepare")
def prepare_command(
    input_path: Annotated[
        Path,
        typer.Option(
            "-i", "--input-path", help="Path to the evaluation data directory."
        ),
    ] = Path(DEFAULT_EVAL_PATH),
) -> None:
    """Convert evaluation PDFs to markdown."""
    prepare_main(input_path)
    print(
        f"Converted PDFs to markdown in {input_path}. ",
        'Run "evals run" to perform evaluation.',
    )


@app.command("run")
def run_command(
    eval_path: Annotated[
        Path,
        typer.Option(
            "-i", "--input-path", help="Path to the evaluation data directory."
        ),
    ] = Path(DEFAULT_EVAL_PATH),
    model: Annotated[
        Literal["claude"],
        typer.Option("-m", "--model", help="Model name to use for evaluation"),
    ] = "claude",
) -> None:
    """Run impact extraction evaluations."""
    run_main(eval_path, model)


@app.command("eval")
def eval_command(
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
    eval_main(eval_path, data_path)


if __name__ == "__main__":
    app()
