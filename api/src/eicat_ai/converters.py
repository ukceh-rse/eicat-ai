import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

import requests
from botocore.exceptions import ClientError
from grobid_client.grobid_client import GrobidClient
from html_to_markdown import convert
from loguru import logger
from pydantic_ai import Agent

from eicat_ai.models import Category, Impact, Paper, SpeciesNames
from eicat_ai.settings import settings


def pdf_to_tei_xml(pdf_bytes: bytes) -> str:
    # long or scanned PDFs can take GROBID several minutes, more so with several uploads at once; the client default is 180s
    client = GrobidClient(grobid_server=settings.grobid_url, timeout=600)
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


MODEL_ERROR_ATTEMPTS = 3
CATEGORY_RANK = {Category.DATA_DEFICIENT: 0, Category.MINIMAL_CONCERN: 1, Category.MINOR: 2, Category.MODERATE: 3, Category.MAJOR: 4, Category.MASSIVE: 5}


def merge_by_mechanism(impacts: List[Impact]) -> List[Impact]:
    """One impact per mechanism, as EICAT assessments record them: models tend to split a mechanism across native taxa
    or passages. Merged records list every taxon and quote every passage, and take the most severe category."""
    merged: Dict[str, Impact] = {}
    for impact in impacts:
        m = merged.get(impact.mechanism)
        if m is None:
            merged[impact.mechanism] = impact.model_copy(update={"impacted_species": list(impact.impacted_species)})
            continue
        m.impacted_species += [s for s in impact.impacted_species if s not in m.impacted_species]
        if impact.evidence not in m.evidence:
            m.evidence += "\n\n" + impact.evidence
        if CATEGORY_RANK[impact.category] > CATEGORY_RANK[m.category]:
            m.category, m.reversibility = impact.category, impact.reversibility
            m.confidence, m.justification = impact.confidence, impact.justification
    return list(merged.values())


async def extract_impacts(
    agent: Agent[Paper, List[Impact]], paper: Paper, species: SpeciesNames
) -> Tuple[List[Impact], Dict[str, int]]:
    names = f" (also known as {', '.join(species.vernacular_names)})" if species.vernacular_names else ""
    prompt = [
        f"Extract all impacts caused by the alien species {species.scientific_name}{names}."
        " The paper may refer to it by a synonym, a former scientific name or a common name."
    ]
    for attempt in range(1, MODEL_ERROR_ATTEMPTS + 1):
        try:
            result = await agent.run(prompt, deps=paper)
            break
        except ClientError as e:
            # Bedrock's ModelErrorException is a transient failure of the model itself, e.g. Nova's
            # "Model produced invalid sequence as part of ToolUse"; the same request usually succeeds again
            if e.response.get("Error", {}).get("Code") != "ModelErrorException" or attempt == MODEL_ERROR_ATTEMPTS:
                raise
            logger.warning(f"Model error (attempt {attempt}/{MODEL_ERROR_ATTEMPTS}), retrying: {e}")
    usage = result.usage()
    return merge_by_mechanism(result.output), {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens, "requests": usage.requests}
