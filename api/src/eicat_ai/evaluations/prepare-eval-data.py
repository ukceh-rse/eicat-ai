import sys
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger
from rich.progress import Progress, TaskID

from eicat_ai.evaluations.evaluators import DEFAULT_EVAL_PATH
from eicat_ai.routers.analysis import (
    convert_html_to_markdown,
    convert_pdf_to_tei,
    convert_tei_to_html,
)


def main(
    input_path: Annotated[
        Path,
        typer.Option(
            "-i", "--input-path", help="Path to the evaluation data directory."
        ),
    ] = Path(DEFAULT_EVAL_PATH),
) -> None:
    pdf_files = list(input_path.rglob("*.pdf"))
    if len(pdf_files) == 0:
        print(f"WARNING: No PDF files found in path: {input_path}")
        return
    with Progress() as p:
        task: TaskID = p.add_task("Preparing evaluation data...", total=len(pdf_files))
        for pdf_file in pdf_files:
            tei_file = convert_pdf_to_tei(pdf_file)
            html_file = convert_tei_to_html(tei_file)
            md_file = convert_html_to_markdown(html_file)
            p.update(task, advance=1)


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    typer.run(main)
