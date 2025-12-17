import os
from pathlib import Path
from typing import List

import requests
from grobid_client.grobid_client import GrobidClient
from html_to_markdown import convert
from loguru import logger
from pydantic_ai import Agent

from eicat_ai.models import Impact, Paper, SpeciesNames


def convert_pdf_to_tei(pdf_path: Path) -> Path:
    """Process PDF file using GROBID service to generate TEI XML"""
    grobid_service_name = os.getenv("GROBID_URL", "localhost")
    client: GrobidClient = GrobidClient(
        grobid_server=f"http://{grobid_service_name}:8070"
    )
    logger.debug("Calling GROBID service to process PDF")
    filename, status, output = client.process_pdf(
        "processFulltextDocument",
        str(pdf_path),
        generateIDs=True,
        consolidate_header=True,
        consolidate_citations=True,
        include_raw_citations=True,
        include_raw_affiliations=True,
        tei_coordinates=True,
        segment_sentences=False,
    )
    if status == 200:
        tei_path: Path = pdf_path.parent / f"{pdf_path.stem}.tei.xml"
        with open(tei_path, "w", encoding="utf-8") as f:
            f.write(output)
        return tei_path
    else:
        raise HTTPException(
            status_code=status,
            detail=f"GROBID service failed to convert {filename} ({status}): {output}",
        )


def convert_tei_to_html(tei_file: Path) -> Path:
    """Convert TEI XML file to HTML using TEI stylesheets service"""
    logger.debug("Calling TEI stylesheets service to convert XML to HTML")

    tei_service_name = os.getenv("TEI_URL", "localhost")
    endpoint = f"http://{tei_service_name}:8001/tei2html"
    logger.debug(f"Making request to TEI stylesheets endpoint: {endpoint}")

    with open(tei_file, "r") as f:
        files = {"file": f}
        response = requests.post(endpoint, files=files)

    if response.status_code == 200:
        html_file = tei_file.parent / f"{tei_file.stem}.html"
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(response.text)
            logger.debug("TEI stylesheets service completed HTML conversion")
        return html_file
    else:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"TEI service failed to convert {tei_file.stem} ({response.status_code}): {response.text}",
        )


def convert_html_to_markdown(html_file: Path) -> Path:
    """Convert HTML file to markdown and save both the file and return the content"""
    logger.debug("Converting HTML to markdown")

    markdown_file: Path = html_file.parent / f"paper.md"
    with (
        open(html_file, "r", encoding="utf-8") as input_file,
        open(markdown_file, "w", encoding="utf-8") as output_file,
    ):
        html_content: str = input_file.read()
        markdown_content: str = convert(html_content)
        output_file.write(markdown_content)
    return markdown_file


async def extract_impacts(
    agent: Agent[Paper, List[Impact]], paper: Paper, species: SpeciesNames
) -> List[Impact]:
    result = await agent.run(
        [
            f"Extract all impacts caused by the alien species {species.scientific_name} (also known as {', '.join(species.vernacular_names)})"
        ],
        deps=paper,
    )
    return result.output
