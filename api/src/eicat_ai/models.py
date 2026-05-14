from __future__ import annotations

import csv
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

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

    @classmethod
    def load_from_csv(cls, filepath: str) -> List[Impact]:
        impacts = []
        with open(filepath, "r", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                impacted = [s.strip() for s in row["Impacted native species"].split(",") if s.strip()]
                confidence_raw = row["Confidence rating"].strip()
                reversibility_raw = row.get("reversibility", "").strip() or None
                impacts.append(cls(
                    alien_species=row["Species"],
                    mechanism=Mechanism(row["Impact mechanism"]),
                    category=Category(row["EICAT Category"]),
                    reversibility=reversibility_raw,
                    evidence=row["Evidence for EICAT impact category"],
                    confidence=confidence_raw or None,
                    justification=row["Justification for confidence rating"],
                    impacted_species=impacted,
                ))
        return impacts


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


class Analysis(MongoDocument):
    species: SpeciesNames
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: AnalysisStatus = AnalysisStatus.PENDING
    paper_ids: List[PydanticObjectId] = Field(default_factory=list)
    results: Dict[str, List[Impact]] = Field(default_factory=dict)
    error: Optional[str] = None
    completed_at: Optional[datetime] = None

    class Settings:
        name = "analyses"


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
