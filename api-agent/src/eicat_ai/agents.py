from pydantic_ai import Agent, ModelSettings
from eicat_ai.models import Paper


def paper_agent(model_name: str) -> Agent[None, Paper]:
    """
    Create a PydanticAI agent for converting academic papers from a PDFs to structured Paper objects.

    This agent processes PDF-extracted text and converts it into a structured JSON format
    following the Paper schema, including title, authors, content (in Markdown), and references.

    Args:
        model_name: The name/identifier of the language model to use for the conversion

    Returns:
        Agent[None, Paper]: A configured PydanticAI agent that converts PDF academic paper
        text into Paper objects with proper formatting and structure
    """
    return Agent[None, Paper](
        model_name,
        output_type=Paper,
        output_retries=2,
        model_settings=ModelSettings(max_tokens=10_000, temperature=0.0),
        system_prompt="""
        You must convert an academic article (supplied later as a PDF) into a JSON object conforming to the following Pydantic schema:

        class Paper(BaseModel):
            title: str
            authors: List[str]
            content: str          # the full body of the paper in Markdown
            references: List[str] # each reference as its own string

        CONVERSION RULES
        1) Derive `title` from the article title.
        2) Derive `authors` as a list of author names.
        3) Derive `references` from the References / Bibliography section — one full formatted reference per list element; no markdown inside references.
        4) Derive `content` as the full body of the article (excluding the References section) in valid Markdown form:
        - Use `#` for the article title
        - `##` for top-level sections (Abstract, Introduction, Methods, Results, Discussion, Conclusion, etc.)
        - `###` for subsections
        - Remove page numbers, headers, footers, running heads
        - Repair PDF line-break artifacts (join wrapped lines and de-hyphenate)
        - Preserve wording verbatim except for those repairs
        - Use *italic*, **bold**, lists, blockquotes, math (`$` / `$$`), figure/table placeholders as appropriate
        - If text is unrecoverable, insert `[UNREADABLE segment]`

        5) Do not summarise, paraphrase, reorder, or omit content except headers/footers removal.

        OUTPUT FORMAT
        - Output a **single JSON object** with keys `title`, `authors`, `content`, `references`
        - Do not include any wrapper text, commentary, or explanations — JSON only
        """,
    )
