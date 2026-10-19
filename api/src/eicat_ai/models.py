from __future__ import annotations

import csv
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from beanie import Document as MongoDocument, PydanticObjectId
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Domain types (used by agents and evaluation pipeline)
# ---------------------------------------------------------------------------

class SpeciesNames(BaseModel):
    scientific_name: str = Field(description="The scientific name of a particular species")
    vernacular_names: List[str] = Field(
        default_factory=list,
        description="A list of common or vernacular names that the particular species is also known by.",
    )


class Paper(BaseModel):
    title: str = Field(default="")
    authors: List[str] = Field(default_factory=list)
    content: str = Field(description="The full body of the article in Markdown.")
    references: List[str] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class Category(str, Enum):
    """EICAT impact category."""

    MASSIVE = "MV"
    MAJOR = "MR"
    MODERATE = "MO"
    MINOR = "MN"
    MINIMAL_CONCERN = "MC"
    DATA_DEFICIENT = "DD"

    @property
    def description(self) -> str:
        return {
            "MV": (
                "Naturally irreversible community change through local, sub-population, or global "
                "extinction of at least one native taxon caused by the alien taxon"
            ),
            "MR": (
                "Community change through local or sub-population extinction of at least one native "
                "taxon, which would be naturally reversible if the alien taxon were removed "
                "(i.e. the native taxon would return within 10 years or 3 generations)"
            ),
            "MO": (
                "Decline in population size of at least one native taxon, but no local extinction "
                "documented"
            ),
            "MN": (
                "Reductions in individual performance (e.g. growth, reproduction, survival) of "
                "native taxa, but no decline in native population sizes"
            ),
            "MC": (
                "Negligible impacts; impact has been actively studied but only negligible effects "
                "on individual performance detected; no population-level change observed. "
                "Requires evidence of study — not merely absence of data."
            ),
            "DD": (
                "Alien populations are known to exist in the wild, but current evidence is "
                "insufficient to assign an impact category"
            ),
        }[self.value]


class Mechanism(str, Enum):
    """Mechanism of impact."""

    COMPETITION = "Competition"
    PREDATION = "Predation"
    HYBRIDISATION = "Hybridisation"
    TRANSMISSION_OF_DISEASES = "Transmission of diseases to native species"
    PARASITISM = "Parasitism"
    POISONING_TOXICITY = "Poisoning/toxicity"
    BIO_FOULING = "Bio-fouling"
    GRAZING_HERBIVORY_BROWSING = "Grazing/herbivory/browsing"
    CHEMICAL_IMPACT = "Chemical Impact on ecosystem"
    PHYSICAL_IMPACT = "Physical Impact on ecosystem"
    STRUCTURAL_IMPACT = "Structural Impact on ecosystem"
    INDIRECT_IMPACTS = "Indirect impacts through interactions with other species"

    @property
    def description(self) -> str:
        return {
            "Competition": (
                "The alien taxon competes with native taxa for resources (e.g. food, water, space), "
                "leading to deleterious impact on native taxa"
            ),
            "Predation": (
                "The alien taxon predates on native taxa, leading to deleterious impact on native taxa"
            ),
            "Hybridisation": (
                "The alien taxon hybridises with native taxa, leading to deleterious impact on native "
                "taxa (impacts can range from reduced individual fitness through to local population "
                "extinction via genetic swamping)"
            ),
            "Transmission of diseases to native species": (
                "The alien taxon transmits diseases or acts as a host or vector for pathogens "
                "affecting native taxa, leading to deleterious impact on native taxa"
            ),
            "Parasitism": (
                "The alien taxon parasitises native taxa, leading to deleterious impact on native taxa"
            ),
            "Poisoning/toxicity": (
                "The alien taxon is toxic or allergenic by ingestion, inhalation, or contact, or is "
                "allelopathic to plants, leading to deleterious impact on native taxa"
            ),
            "Bio-fouling": (
                "Accumulation of individuals of the alien taxon on the surface of a native taxon "
                "(bio-fouling), or other direct physical disturbances not involved in a trophic "
                "interaction (e.g. trampling, rubbing), leading to deleterious impact on native taxa"
            ),
            "Grazing/herbivory/browsing": (
                "Grazing, herbivory, or browsing by the alien taxon leads to deleterious impact on "
                "native taxa"
            ),
            "Chemical Impact on ecosystem": (
                "The alien taxon causes changes to the chemical characteristics of the native "
                "environment (e.g. pH, nutrient and/or water cycling), leading to deleterious impact "
                "on native taxa"
            ),
            "Physical Impact on ecosystem": (
                "The alien taxon causes changes to the physical characteristics of the native "
                "environment (e.g. disturbance or light regimes), leading to deleterious impact on "
                "native taxa"
            ),
            "Structural Impact on ecosystem": (
                "The alien taxon causes changes to the habitat structure (e.g. changes in "
                "architecture or complexity), leading to deleterious impact on native taxa"
            ),
            "Indirect impacts through interactions with other species": (
                "The alien taxon interacts with other native or alien taxa (e.g. through pollination, "
                "seed dispersal, apparent competition, mesopredator release, or any other mechanism), "
                "facilitating indirect deleterious impact on native taxa"
            ),
        }[self.value]


class Impact(BaseModel):
    alien_species: str = Field(description="Name of the alien species causing the impact")
    mechanism: Mechanism = Field(description="Mechanism by which the impact occurs.")
    category: Category = Field(description="EICAT impact category.")
    reversibility: Optional[Literal["reversible", "irreversible", "unknown"]] = Field(
        default=None,
        description=(
            "Whether any documented local extinction is naturally reversible within 10 years or "
            "3 generations (whichever is longer) if the alien taxon were removed. Required when "
            "category is MR or MV; leave null for all other categories."
        ),
    )
    evidence: str = Field(description="Verbatim excerpt from the paper supporting this impact.")
    confidence: Optional[Literal["Low", "Medium", "High"]] = Field(default=None)
    justification: str = Field(description="Explanation of confidence rating.")
    impacted_species: List[str] = Field(description="List of impacted native taxa.")

    @classmethod
    def save_to_csv(cls, impacts: List[Impact], filepath: str) -> None:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            field_titles = [cls.model_fields[k].title or k for k in cls.model_fields]
            writer.writerow(field_titles)
            for impact in impacts:
                writer.writerow([
                    impact.alien_species,
                    impact.mechanism.value,
                    impact.category.value,
                    impact.reversibility or "",
                    impact.evidence,
                    impact.confidence,
                    impact.justification,
                    ", ".join(impact.impacted_species),
                ])


# ---------------------------------------------------------------------------
# MongoDB documents (Beanie)
# ---------------------------------------------------------------------------

class PaperStatus(str, Enum):
    CONVERTING = "converting"
    READY = "ready"
    FAILED = "failed"


class PaperDoc(MongoDocument):
    filename: str
    content_type: str
    size: int
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: PaperStatus = PaperStatus.CONVERTING
    pdf_data: bytes
    tei_xml: Optional[str] = None
    markdown: Optional[str] = None
    error: Optional[str] = None

    class Settings:
        name = "papers"


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EvidenceSpan(BaseModel):
    """A passage of the paper markdown; offsets are None when the passage could not be located (unanchored).
    Approximate spans are the closest passage to AI evidence that the paper doesn't contain word for word."""

    start: Optional[int] = None
    end: Optional[int] = None
    text: str
    approximate: bool = False


class Sighting(BaseModel):
    """One run's extraction of an impact whose key was held, kept in full on the suppressed record."""

    run_id: str
    at: datetime
    ai: Impact
    evidence: List[EvidenceSpan] = Field(default_factory=list)


class RunStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class VerifiedChoice(str, Enum):
    KEEP = "keep"
    DISCARD = "discard"


class AnalysisRun(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    model: str
    usage: Dict[str, int] = Field(default_factory=dict)
    verified_choice: Optional[VerifiedChoice] = None
    status: RunStatus = RunStatus.RUNNING


class ImpactOrigin(str, Enum):
    AI = "ai"
    HUMAN = "human"


class ImpactState(str, Enum):
    ACTIVE = "active"
    REMOVED = "removed"
    SUPERSEDED = "superseded"
    SUPPRESSED = "suppressed"


class ReviewedImpact(BaseModel):
    """An impact under review: `ai` is the frozen AI output (None for human-created impacts), `current` the reviewed
    values. `evidence` spans are the source of truth for `current.evidence`, which holds their texts joined."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    paper_id: str
    origin: ImpactOrigin
    run_id: Optional[str] = None
    ai: Optional[Impact] = None
    current: Impact
    evidence: List[EvidenceSpan] = Field(default_factory=list)
    evidence_edited: bool = False  # a reviewer changed the spans; until then `current.evidence` derives from the AI's
    verified: bool = False
    state: ImpactState = ImpactState.ACTIVE
    held_by: Optional[str] = None  # suppressed only: the impact holding this key
    sightings: List[Sighting] = Field(default_factory=list)  # suppressed only

    @property
    def key(self) -> tuple[str, Mechanism]:
        return self.paper_id, self.current.mechanism


class Analysis(MongoDocument):
    species: SpeciesNames
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: AnalysisStatus = AnalysisStatus.PENDING
    paper_ids: List[PydanticObjectId] = Field(default_factory=list)
    results: Dict[str, List[Impact]] = Field(default_factory=dict)
    error: Optional[str] = None
    completed_at: Optional[datetime] = None
    usage: Dict[str, int] = Field(default_factory=dict)  # summed LLM token usage over the run's papers
    runs: List[AnalysisRun] = Field(default_factory=list)
    impacts: List[ReviewedImpact] = Field(default_factory=list)

    def visible_impacts(self) -> List[ReviewedImpact]:
        """Impacts of the analysis's current papers; a removed paper's impacts are kept for when it is added back."""
        papers = {str(p) for p in self.paper_ids}
        return [i for i in self.impacts if i.paper_id in papers]

    class Settings:
        name = "analyses"
        use_revision = True


class ActorKind(str, Enum):
    HUMAN = "human"
    AI = "ai"
    SYSTEM = "system"


class Actor(BaseModel):
    kind: ActorKind
    user_id: Optional[str] = None  # reserved until user accounts exist


class FieldChange(BaseModel):
    field: str
    old: Any = None
    new: Any = None


class AuditEvent(MongoDocument):
    """Append-only record of a review or run action. Kept when its analysis is deleted."""

    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    analysis_id: PydanticObjectId
    impact_id: Optional[str] = None
    run_id: Optional[str] = None
    actor: Actor
    action: str
    changes: List[FieldChange] = Field(default_factory=list)
    note: Optional[str] = None

    class Settings:
        name = "audit_events"
        indexes = [[("analysis_id", 1), ("at", 1)], "impact_id"]


# ---------------------------------------------------------------------------
# API response schemas (exclude heavy fields from wire responses)
# ---------------------------------------------------------------------------

class AnalysisResponse(BaseModel):
    id: Optional[PydanticObjectId] = None
    species: SpeciesNames
    created_at: datetime
    status: AnalysisStatus
    paper_ids: List[PydanticObjectId] = Field(default_factory=list)
    results: Dict[str, List[Impact]] = Field(default_factory=dict)
    error: Optional[str] = None
    completed_at: Optional[datetime] = None
    usage: Dict[str, int] = Field(default_factory=dict)  # summed LLM token usage over the run's papers
    runs: List[AnalysisRun] = Field(default_factory=list)
    impacts: List[ReviewedImpact] = Field(default_factory=list)

    model_config = {"populate_by_name": True}

    @classmethod
    def from_doc(cls, doc: Analysis) -> AnalysisResponse:
        return cls(
            id=doc.id,
            species=doc.species,
            created_at=doc.created_at,
            status=doc.status,
            paper_ids=doc.paper_ids,
            results=doc.results,
            error=doc.error,
            completed_at=doc.completed_at,
            usage=doc.usage,
            runs=doc.runs,
            impacts=doc.visible_impacts(),
        )


class PaperResponse(BaseModel):
    id: Optional[PydanticObjectId] = None
    filename: str
    content_type: str
    size: int
    uploaded_at: datetime
    status: PaperStatus
    error: Optional[str] = None

    model_config = {"populate_by_name": True}

    @classmethod
    def from_doc(cls, doc: PaperDoc) -> PaperResponse:
        return cls(
            id=doc.id,
            filename=doc.filename,
            content_type=doc.content_type,
            size=doc.size,
            uploaded_at=doc.uploaded_at,
            status=doc.status,
            error=doc.error,
        )
