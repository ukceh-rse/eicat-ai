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
            "MV": "Irreversible extinction of a native species",
            "MR": "Extinction of local population of native species that is reversible",
            "MO": "Decline in native species population",
            "MN": "No decline in population but some impact on performance of native species",
            "MC": "No significant impact observed",
            "DD": "No data available or impacts or insufficient time for impacts to be observed",
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
            "Competition": "Competing for resources with native species (e.g. food, water, space)",
            "Predation": "Alien taxa predate on native species",
            "Hybridisation": "Alien species mating with native species, eliminating native population",
            "Transmission of diseases to native species": "Passing diseases to native species",
            "Parasitism": "Alien taxa parasites native species",
            "Poisoning/toxicity": "Alien taxa is poisonous or toxic through ingestion or contact with native species",
            "Bio-fouling": "Physically impeding native species",
            "Grazing/herbivory/browsing": "Alien species eating a native plant species",
            "Chemical Impact on ecosystem": "Chemical changes to environment caused by alien species that affect native species",
            "Physical Impact on ecosystem": "Physical changes to environment caused by alien species that affect native species",
            "Structural Impact on ecosystem": "Structural changes to environment caused by alien species that affect native species",
            "Indirect impacts through interactions with other species": (
                "Potential for the alien species to increase one native species population "
                "that as a result decrease the population of another native species"
            ),
        }[self.value]


class Impact(BaseModel):
    alien_species: str = Field(description="Name of the alien species causing the impact")
    mechanism: Mechanism = Field(description="Mechanism by which the impact occurs.")
    category: Category = Field(description="EICAT impact category.")
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
                impacts.append(cls(
                    alien_species=row["Species"],
                    mechanism=Mechanism(row["Impact mechanism"]),
                    category=Category(row["EICAT Category"]),
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
