from pydantic_ai import Agent, ModelSettings
from eicat_ai.models import Paper, Impact
from typing import List


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


def data_extraction_agent(model_name: str) -> Agent[None, List[Impact]]:
    return Agent[None, List[Impact]](
        model_name,
        output_type=List[Impact],
        output_retries=2,
        model_settings=ModelSettings(max_tokens=10_000, temperature=0.0),
        system_prompt="""
        You will be provided with text from an academic paper. 
        You must extract from the paper the impacts caused by an invasive species on any native local species.
        These impacts should be returned as a list of JSON objects in the following Pydantic schema:

        class Impact(BaseModel):
            excerpt: str
            level: Literal["MV", "MR", "MO", "MN", "MC", "DD", "NA", "NE"]
            category: Literal[
                "Competition",
                "Predation",
                "Hybridisation",
                "Disease Transmission",
                "Parasitism",
                "Poisoning/Toxicity",
                "Bio-fouling",
                "Grazing",
                "Chemical Impact",
                "Physical Impact",
                "Structural Impact",
                "Indirect Impact",
            ]

        "excerpt" should be the text from the paper describing the impact verbatim
        "level" should be a level of the impact based on the EICAT descriptions:
            - MV: Massive (Irreversible extinction of a native species)
            - MR: Major (Extinction of local population of native species that is reversible)
            - MO: Moderate (Decline in native species population)
            - MN: Minor (No decline in population but some impact on performance of native species)
            - MC: Minimal Concern (No significant impact observed)
            - DD: Data Deficent (No data available or impacts or insufficient time for impacts to be observed)
            - NA: No Alien Populations (No alien species in non-native area)
            - NE: Not Evaluated
        "categroy" should describe the mechanism by which the invasive species impacts the local population.
        """,
    )
