import tempfile
from pathlib import Path
from typing import List

import requests
from grobid_client.grobid_client import GrobidClient
from html_to_markdown import convert
from loguru import logger
from pydantic_ai import Agent

from eicat_ai.models import Impact, Paper, SpeciesNames
from eicat_ai.settings import settings


def pdf_to_tei_xml(pdf_bytes: bytes) -> str:
    client = GrobidClient(grobid_server=settings.grobid_url)
    logger.debug("Calling GROBID service")
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "paper.pdf"
        pdf_path.write_bytes(pdf_bytes)
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
        return output
    raise RuntimeError(f"GROBID failed for {filename} ({status}): {output}")


def tei_xml_to_markdown(tei_xml: str) -> str:
    endpoint = f"{settings.tei_url}/tei2html"
    logger.debug(f"Calling TEI stylesheets service: {endpoint}")
    response = requests.post(
        endpoint,
        files={"file": ("paper.tei.xml", tei_xml.encode("utf-8"), "text/xml")},
    )
    if response.status_code != 200:
        raise RuntimeError(f"TEI service failed ({response.status_code}): {response.text}")
    logger.debug("Converting HTML to markdown")
    return convert(response.text)


async def extract_impacts(
    agent: Agent[Paper, List[Impact]], paper: Paper, species: SpeciesNames
) -> List[Impact]:
    result = await agent.run(
        [
            f"Extract all impacts caused by the alien species {species.scientific_name}"
            f" (also known as {', '.join(species.vernacular_names)})"
        ],
        deps=paper,
    )
    return result.output
