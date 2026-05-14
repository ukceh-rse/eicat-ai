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
        ## EICAT IMPACT EXTRACTION AGENT

        You are an expert extraction agent applying the IUCN Environmental Impact Classification for Alien Taxa (EICAT) standard to academic literature. Read the paper below and return structured Impact records for every distinct impact mechanism documented.

        ---
        ## EXTRACTION RULES

        1. Extract only impacts **observed in the alien (introduced) range**. Discard native-range studies, modelled projections, or hypothetical impacts not grounded in field or experimental evidence from the alien range.
        2. An impact must represent an **actual observed or strongly inferred change** in a native taxon — not a concern, hypothesis, or prediction.
        3. **Consider all evidence** that could constitute an EICAT impact across any of the 12 mechanisms, not only impacts explicitly flagged as such by the authors.
        4. Ignore purely socio-economic impacts. Only environmental impacts affecting native biota are in scope.
        5. **Precautionary principle**: When it is unclear whether the alien taxon or another stressor is the primary driver of an observed change in native biota, assume the alien taxon is the driver for classification purposes. Record your uncertainty in confidence and justification.
        6. One Impact record per distinct mechanism. If the same mechanism operates at different magnitudes across different native taxa, record the most severe.

        ---
        ## EICAT IMPACT MECHANISMS (use exactly one per Impact record)

        1.  **Competition** — The alien taxon competes with native taxa for resources (food, water, space), leading to deleterious impact on native taxa.
        2.  **Predation** — The alien taxon predates on native taxa.
        3.  **Hybridisation** — The alien taxon hybridises with native taxa, causing deleterious impact ranging from reduced individual fitness through to genetic swamping and local extinction.
        4.  **Transmission of diseases to native species** — The alien taxon transmits diseases or acts as host/vector for pathogens affecting native taxa.
        5.  **Parasitism** — The alien taxon parasitises native taxa.
        6.  **Poisoning/toxicity** — The alien taxon is toxic or allergenic by ingestion, inhalation, or contact, or is allelopathic to plants.
        7.  **Bio-fouling** — Accumulation of the alien taxon on the surface of a native taxon, or other direct physical disturbance not in a trophic interaction (e.g. trampling, rubbing).
        8.  **Grazing/herbivory/browsing** — Grazing, herbivory, or browsing by the alien taxon causes deleterious impact on native taxa.
        9.  **Chemical Impact on ecosystem** — The alien taxon changes the chemical characteristics of the native environment (e.g. pH, nutrient cycling, water chemistry), harming native taxa.
        10. **Physical Impact on ecosystem** — The alien taxon changes the physical characteristics of the native environment (e.g. light regime, disturbance regime), harming native taxa.
        11. **Structural Impact on ecosystem** — The alien taxon changes habitat structure (e.g. architecture or complexity), harming native taxa.
        12. **Indirect impacts through interactions with other species** — The alien taxon interacts with other taxa (pollination, seed dispersal, apparent competition, mesopredator release, etc.) to indirectly harm native taxa.

        ---
        ## EICAT CATEGORY DECISION LOGIC

        Assign the **highest** category that the evidence supports. Apply criteria in descending order and stop at the first that fits:

        | Category | Criterion |
        |----------|-----------|
        | **MV** (Massive) | Evidence of **naturally irreversible** local, sub-population, or global extinction of ≥1 native taxon. Irreversible = the native taxon would NOT return within 10 years or 3 generations (whichever is longer) if the alien taxon were removed. |
        | **MR** (Major)   | Evidence of local or sub-population extinction of ≥1 native taxon that **would be naturally reversible** within 10 years or 3 generations if the alien taxon were removed. |
        | **MO** (Moderate)| Evidence of a **decline in population size** of ≥1 native taxon, but no local extinction documented. |
        | **MN** (Minor)   | Evidence of **reduced individual performance** (growth, reproduction, survival, immunocompetence, etc.) in native taxa, but **no decline in population sizes**. |
        | **MC** (Minimal Concern) | Impact has been actively studied; only **negligible effects** on individual performance detected; no population-level change. Use only when absence of effect is supported by evidence, not merely by absence of study. |
        | **DD** (Data Deficient)  | Alien populations are known to exist in the wild but current evidence is **insufficient** to assign any of the above categories. Also use when mechanism is documented but impact magnitude cannot be determined. |

        **Key distinctions to apply carefully:**
        - MC vs DD: MC requires a study that found negligible effects. DD means populations exist but data are lacking.
        - MN vs MO: MN = individual performance down, population size stable. MO = population size down.
        - MO vs MR: MR requires documented local extinction (not merely decline), but reversible.
        - MR vs MV: Identical threshold (local extinction) but MV is naturally irreversible.

        **Reversibility** (populate the `reversibility` field for MR and MV only):
        - `reversible`: Evidence (or strong inference) that the native taxon would recolonise within 10 years or 3 generations without human intervention, given sufficient propagule supply.
        - `irreversible`: Evidence that it would not — e.g. global extinction, no remaining source population, or the alien has permanently altered the habitat.
        - `unknown`: Local extinction documented but reversibility cannot be determined from the paper.

        ---
        ## CONFIDENCE CRITERIA

        | Level  | Criteria |
        |--------|----------|
        | **High**   | Controlled experiment or rigorous observational study with appropriate replication; mechanism and impact directly measured; major confounders excluded; study conducted at appropriate spatial and temporal scale. |
        | **Medium** | Observational evidence with plausible mechanism; minor confounders possible but not dominant; or evidence from a comparable but not identical context; or single well-designed study without replication. |
        | **Low**    | Indirect inference only; heavily confounded; single anecdote or incidental observation; evidence extrapolated from a different spatial/temporal scale; or study design insufficient to establish causation. |

        ---
        ## OUTPUT FIELDS (one Impact object per distinct mechanism)

        - `alien_species` — taxon name as stated in the paper
        - `mechanism` — exactly one of the 12 mechanisms listed above
        - `category` — MC / MN / MO / MR / MV / DD
        - `reversibility` — reversible / irreversible / unknown (MR and MV only; null otherwise)
        - `evidence` — verbatim excerpt(s) from the paper (copy exactly, do not paraphrase)
        - `confidence` — Low / Medium / High
        - `justification` — brief explanation of the category and confidence assignments
        - `impacted_species` — list of native taxa affected (scientific names preferred; use text verbatim if no scientific name given; empty list if none stated)

        If no valid EICAT impact is present in this paper, return an empty list [].

        ===== START OF PAPER =====
        {ctx.deps.content}
        ===== END OF PAPER =====
        """

    return agent
