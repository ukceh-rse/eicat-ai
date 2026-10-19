import json
from dataclasses import replace
from pathlib import Path
from typing import List

from pydantic_ai import Agent, ModelSettings, PromptedOutput, RunContext
from pydantic_ai.models import Model
from pydantic_ai.models.bedrock import BedrockConverseModel
from pydantic_ai.providers.bedrock import BedrockProvider

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


def _render_examples(path: Path) -> str:
    """Few-shot examples from GISD expert assessments (built by eval/build_fewshot.py), as plain text:
    Nova models produced invalid tool calls more often with JSON examples in the prompt."""
    out = []
    for n, e in enumerate(json.loads(path.read_text()), 1):
        ids = {p: f"P{k}" for k, p in enumerate(e["passages"], 1)}
        passages = "\n".join(f"[{ids[p]}] {p}" for p in e["passages"])
        records = "\n".join(
            f"- {i['mechanism']} | {i['category']} | impacted: {', '.join(i['impacted_species']) or 'not stated'}"
            f" | evidence: {ids.get(i['evidence'], '-')}"
            for i in e["impacts"]
        )
        out.append(
            f"### Example {n}: {e['species']}\nPassages:\n{passages}\n\n"
            f"Expert records (mechanism | category | impacted taxa | evidence passage):\n{records}"
        )
    return "\n\n".join(out)


FEWSHOT_EXAMPLES = _render_examples(Path(__file__).parent / "fewshot_examples.json")


# Newer Bedrock models reject request options older ones accept: `temperature` (Claude 5.5, GPT-5.x)
# and a forced tool_choice (Claude Sonnet 5.5), which pydantic-ai sends for tool output. For the latter
# tool output is kept (prompted JSON output extracted noticeably fewer impacts) but tool_choice is left
# unset, so the model chooses to call the output tool and pydantic-ai retries if it replies with text.
NO_TEMPERATURE = ("claude-haiku-5-5", "claude-sonnet-5-5", "openai.gpt-5")
NO_FORCED_TOOL = ("claude-sonnet-5-5",)
# Nova often fails long structured outputs as tool calls ("Model produced invalid sequence as part of ToolUse"),
# even on retry; prompted JSON output fails far less often for it.
PROMPTED_OUTPUT = ("amazon.nova",)


def _model(model_name: str) -> Model | str:
    if not (model_name.startswith("bedrock:") and any(m in model_name for m in NO_FORCED_TOOL)):
        return model_name
    provider = BedrockProvider()
    name = model_name.removeprefix("bedrock:")
    profile = replace(provider.model_profile(name), bedrock_supports_tool_choice=False)
    return BedrockConverseModel(name, provider=provider, profile=profile)


def data_extraction_agent(model_name: str) -> Agent[Paper, List[Impact]]:
    settings = ModelSettings(max_tokens=10_000)
    if not any(m in model_name for m in NO_TEMPERATURE):
        settings["temperature"] = 0.0
    agent: Agent[Paper, List[Impact]] = Agent[Paper, List[Impact]](
        model=_model(model_name),
        output_type=PromptedOutput(List[Impact]) if any(m in model_name for m in PROMPTED_OUTPUT) else List[Impact],
        output_retries=5,
        model_settings=settings,
    )

    @agent.system_prompt
    async def get_system_prompt(ctx: RunContext[Paper]) -> str:
        return f"""

        ## EICAT IMPACT EXTRACTION AGENT

        You are an expert extraction agent applying the IUCN Environmental Impact Classification for Alien Taxa (EICAT) standard to academic literature. Read the paper below and return structured Impact records for every impact it documents, suggests or rules out.

        ---
        ## EXTRACTION RULES

        Your records are compared with those of expert EICAT assessors, who record **every** impact a source documents, suggests or rules out, including weak and indirect evidence. A missed impact is a worse error than an extra one: when in doubt, record it (with the appropriate category and Low confidence) rather than leave it out.

        1. **Scope.** Record impacts in the alien (introduced) range. This includes impacts the paper reports from cited studies, reviews or other regions where the species is alien, and statements in risk assessments or species accounts. Discard only native-range effects and purely modelled projections.
        2. **Record suggested and ruled-out impacts too.**
           - An impact the authors suggest, hypothesise, describe as possible or potential, or report as anecdote, but without a measured effect on native individuals, is recorded with category **DD**.
           - An impact that was looked for and not found (no significant effect, no difference between invaded and uninvaded sites, no evidence of the mechanism) is recorded with category **MC**.
        3. **One record per mechanism per impacted native taxon (or group).** Do not merge different mechanisms or different native taxa into one record. The same passage can support several records: e.g. an alien that both eats a native species and competes with it for food gives one Predation and one Competition record.
        4. **Diet is evidence.** If the alien is reported eating native animals, record Predation (at least MN when native individuals are killed or eaten). If it eats native plants, fruit, seeds or nectar, record Grazing/herbivory/browsing (DD unless harm to the plants is shown). Prey identified only to broad groups (insects, lizards) still counts.
        5. **Indirect interactions.** Seed dispersal or pollination of other alien plants, apparent competition, facilitation of other invaders, and hosting pathogens or parasites that could reach natives are impacts too (Indirect impacts, or Transmission of diseases when the alien hosts a pathogen of natives).
        6. **Only native taxa can be impacted.** Do not list the alien itself or other alien species as impacted taxa (except as intermediaries in an indirect impact on natives).
        7. **Consider all 12 mechanisms** for every interaction between the alien and native biota the paper mentions, not only impacts flagged as such by the authors. Ignore purely socio-economic impacts.
        8. **Precautionary principle**: when it is unclear whether the alien taxon or another stressor drives an observed change in native biota, assume the alien is the driver and record the uncertainty in confidence and justification.
        9. An empty list is correct only when the paper says nothing at all about any interaction between the alien and native species or ecosystems.

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
        | **DD** (Data Deficient)  | The impact is suggested, hypothesised, anecdotal or inferred, but **no effect on native individuals was observed or measured**. |

        **Key distinctions to apply carefully:**
        - MC vs DD: MC requires that the effect was looked for and found negligible or absent. DD means the impact is suggested but its effect is unknown.
        - DD vs MN: a mechanism observed acting on native individuals (individuals eaten, killed, hybrids produced, nests usurped, growth reduced) is at least MN.
        - MN vs MO: MN = individual performance down, population size stable. MO = population size, abundance or density down. Effects measured only on individuals (growth, survival in experiments) are MN however large.
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
        ## OUTPUT FIELDS (one Impact object per mechanism and impacted native taxon)

        - `alien_species` — taxon name as stated in the paper
        - `mechanism` — exactly one of the 12 mechanisms listed above
        - `category` — MC / MN / MO / MR / MV / DD
        - `reversibility` — reversible / irreversible / unknown (MR and MV only; null otherwise)
        - `evidence` — verbatim excerpt(s) from the paper (copy exactly, do not paraphrase)
        - `confidence` — Low / Medium / High
        - `justification` — brief explanation of the category and confidence assignments
        - `impacted_species` — list of native taxa affected (scientific names preferred; use text verbatim if no scientific name given; empty list if none stated)

        If the paper says nothing about any interaction between the alien and native species or ecosystems, return an empty list [].

        ---
        ## WORKED EXAMPLES

        The following are expert EICAT records from GISD for other papers, showing how assessors record impacts: suggested impacts as DD, null results as MC, diet as Predation or Grazing, one record per mechanism and native taxon (the same passage often gives several records). They are not from the paper below.

        {FEWSHOT_EXAMPLES}

        ---

        ===== START OF PAPER =====
        {ctx.deps.content}
        ===== END OF PAPER =====
        """

    return agent
