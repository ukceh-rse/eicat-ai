from pydantic_ai import Agent, BinaryContent
from eicat_ai.models import Paper
from pathlib import Path


async def pdf_to_markdown(agent: Agent[None, Paper], pdf_filepath: str) -> Paper:
    """Convert a PDF document to markdown format using an AI agent.

    Args:
        agent: A Pydantic AI agent configured to process PDF content and return Paper objects.
        pdf_filepath: Path to the PDF file to be converted.

    Returns:
        A Paper object containing the markdown representation of the PDF content.
    """
    p = Path(pdf_filepath)
    result = await agent.run(
        [
            "Convert the following pdf document into markdown format.",
            BinaryContent(data=p.read_bytes(), media_type="application/pdf"),
        ]
    )
    return result.output
