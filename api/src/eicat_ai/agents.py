from typing import List

from pydantic_ai import Agent, ModelSettings, RunContext

from eicat_ai.models import Impact, Paper


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
    agent: Agent[None, Paper] = Agent[None, Paper](
        model=model_name,
        output_type=Paper,
        output_retries=2,
        model_settings=ModelSettings(max_tokens=10_000, temperature=0.0),
    )

    @agent.system_prompt
    async def get_system_prompt(ctx: RunContext[None]) -> str:
        return """
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
        """

    return agent


def data_extraction_agent(model_name: str) -> Agent[Paper, List[Impact]]:
    agent: Agent[Paper, List[Impact]] = Agent[Paper, List[Impact]](
        model=model_name,
        output_type=List[Impact],
        output_retries=5,
        model_settings=ModelSettings(max_tokens=10_000, temperature=0.0),
    )

    @agent.system_prompt
    async def get_system_prompt(ctx: RunContext[Paper]) -> str:
        return f"""
        ## SYSTEM PROMPT — IMPACT EXCTRACTION AGENT (EICAT)

        You are an extraction agent that reads an academic paper or article reporting on the environmental impacts of an invasive (alien) species.
        Return only structured data mapped to the provided Pydantic model `Impact` for each DISTINCT impact mechanism documented.

        You must follow the EICAT guidelines when interpreting impacts:

        Rules
        1) Extract only impacts observed in the alien range (ignore native-range studies).
        2) For an impact to be recorded, the text must report or allow inference of a change in a native taxon consistent with EICAT logic — not just hypothetical or projected; avoid extrapolations not supported by data.
        3) Evidence must be verbatim excerpt(s) from the paper supporting that impact.
        4) The category (MC/MN/MO/MR/MV/DD) must reflect the magnitude defined by EICAT.
        5) Confidence must follow EICAT guidance on evidence quality, scale, confounding, and inference.
        6) For each impact, list the native species impacted (scientific names if given; otherwise exact strings from text).
        7) Ignore impacts that are not environmental (e.g., socio-economic only), or that do not yield any ecological change on a native taxon.
        8) Consider all evidence that could be perceived as an impact based on the EICAT mechanisms, not just impacts or concerns explicilty highlighted by the author.

        For each impact you extract you must output exactly:
        - alien_species — invasive taxon name as stated
        - mechanism — one of the 12 allowed mechanisms from the schema docstring
        - category — an EICAT category (MC, MN, MO, MR, MV, DD)
        - evidence — verbatim excerpt supporting this impact (copy-paste only)
        - confidence — low / medium / high (per EICAT confidence logic)
        - justification — narrative explaining the confidence call (be brief)
        - impacted_species — list of impacted native taxa (empty list if none stated explicitly)

        Interpretation constraints
        - Do not infer species identity beyond what the text supports.
        - Do not conflate community metrics with population-level metrics unless the text links them.
        - If paper reports mechanisms but not magnitude → category = DD.
        - If study is plausibly confounded or inferred → reduce confidence.

        Output
        Return a JSON list of Impact objects — one object per distinct impact.

        If no valid impact according to EICAT is present, return an empty list [].

        ===== START OF PAPER =====
        {ctx.deps.content}
        ===== END OF PAPER =====
        """

    return agent
