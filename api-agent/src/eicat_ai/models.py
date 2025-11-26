from __future__ import annotations
from pydantic import BaseModel, Field
import json
import csv
from typing import List, Literal, Optional, Dict, Any
from enum import Enum
from pathlib import Path
import shutil


class SpeciesNames(BaseModel):
    scientific_name: str = Field(
        description="The scientific name of a particular species"
    )
    vernacular_names: List[str] = Field(
        descritpion="A list of common or vernacular names that the particular species is also known by."
    )

    def save(self, filepath: str) -> None:
        """Save the species names instance to a JSON file.

        Args:
            filepath: Path where the JSON file will be written.
        """
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, filepath: str) -> "SpeciesNames":
        """Load a species names instance from a JSON file.

        Args:
            filepath: Path to the JSON file to load.

        Returns:
            A SpeciesNames instance with data loaded from the file.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)


class Paper(BaseModel):
    title: str = Field(
        default="",
        title="Paper Title",
        description="The full paper title exactly as it appears in the article, without markup.",
    )

    authors: List[str] = Field(
        default_factory=list,
        title="Authors",
        description="An ordered list of author full names as printed in the article.",
    )

    content: str = Field(
        title="Paper Content",
        description="""The entire body of the article excluding the References section,
        rendered in valid Markdown. Preserve original wording and structure,
        using appropriate Markdown syntax for headings, lists, math, etc.
        Do not summarize or paraphrase.""",
    )

    references: List[str] = Field(
        default_factory=list,
        title="References",
        description="""An ordered list of individual references extracted from the article's
        References/Bibliography section. Each element is a single full reference
        string exactly as printed (no Markdown). One reference per list item.""",
    )

    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        title="Metadata",
        description="Optional metadata about the paper such as DOI, publication date, journal, keywords, etc.",
    )

    def save(self, filepath: str) -> None:
        """Save the paper instance to a JSON file.

        Args:
            filepath: Path where the JSON file will be written.
        """
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, filepath: str) -> Paper:
        """Load a paper instance from a JSON file.

        Args:
            filepath: Path to the JSON file to load.

        Returns:
            A Paper instance with data loaded from the file.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)


class Category(str, Enum):
    """EICAT impact category with their corresponding codes and descriptions."""

    MASSIVE = "MV"
    MAJOR = "MR"
    MODERATE = "MO"
    MINOR = "MN"
    MINIMAL_CONCERN = "MC"
    DATA_DEFICIENT = "DD"

    @property
    def description(self) -> str:
        """Get the full description of the impact category."""
        descriptions = {
            "MV": "Irreversible extinction of a native species",
            "MR": "Extinction of local population of native species that is reversible",
            "MO": "Decline in native species population",
            "MN": "No decline in population but some impact on performance of native species",
            "MC": "No significant impact observed",
            "DD": "No data available or impacts or insufficient time for impacts to be observed",
        }
        return descriptions[self.value]

    @property
    def name_friendly(self) -> str:
        """Get a human-friendly name for the impact level."""
        return self.name.replace("_", " ").title()


class Mechanism(str, Enum):
    """Mechanism of impact"""

    COMPETITION = "Competition"
    PREDATION = "Predation"
    HYBRIDISATION = "Hybridisation"
    TRANSMISSION_OF_DISEASES = "Transmission of diseases to native species"
    PARASITISM = "Parasitism"
    POISONING_TOXICITY = "Poisoning/ toxicity"
    BIO_FOULING = "Bio-fouling"
    GRAZING_HERBIVORY_BROWSING = "Grazing/herbivory/browsing"
    CHEMICAL_IMPACT = "Chemical Impact on ecosystem"
    PHYSICAL_IMPACT = "Physical Impact on ecosystem"
    STRUCTURAL_IMPACT = "Structural Impact on ecosystem"
    INDIRECT_IMPACTS = "Indirect impacts through interactions with other species"

    @property
    def description(self) -> str:
        """Get the full description of the mechanism."""
        descriptions = {
            "Competition": "Competing for resources with native species (e.g. food, water, space)",
            "Predation": "Alien taxa predate on native species",
            "Hybridisation": "Alien species mating with native species, eliminating native population",
            "Transmission of diseases to native species": "Passing diseases to native species",
            "Parasitism": "Alien taxa parasites native species",
            "Poisoning/ toxicity": "Alien taxa is poisonous or toxic through ingestion or contact with native species",
            "Bio-fouling": "Physically impeding native species",
            "Grazing/herbivory/browsing": "Alien species eating a native plant species",
            "Chemical Impact on ecosystem": "Chemical changes to environment caused by alien species that affect native species",
            "Physical Impact on ecosystem": "Physical changes to environment caused by alien species that affect native species",
            "Structural Impact on ecosystem": "Structural changes to environment caused by alien species that affect native species",
            "Indirect impacts through interactions with other species": "Potential for the alien species to increase one native species population that as a result decrease the population of another native species",
        }
        return descriptions[self.value]

    @property
    def name_friendly(self) -> str:
        """Get a human-friendly name for the mechanism."""
        return self.name.replace("_", " ").title()


class Impact(BaseModel):
    alien_species: str = Field(
        title="Species", description="Name of the alien species causing the impact"
    )

    mechanism: Mechanism = Field(
        title="Impact mechanism",
        description="Mechanism by which the impact occurs. Use one of the available Mechanism enum values.",
    )

    category: Category = Field(
        title="EICAT Category",
        description="Category of the impact. Use one of the available Category enum values.",
    )

    evidence: str = Field(
        title="Evidence for EICAT impact category",
        description="Excerpt of text from the paper extracted verbatim as evidence for the impact.",
    )

    confidence: Optional[Literal["Low", "Medium", "High"]] = Field(
        default=None, title="Confidence rating", description="A confidence rating"
    )

    justification: str = Field(
        title="Justification for confidence rating",
        description="Explanation of choice in confidence rating",
    )

    impacted_species: List[str] = Field(
        title="Impacted native species", description="A list of the impacted species"
    )

    @classmethod
    def save_to_csv(cls, impacts: List["Impact"], filepath: str) -> None:
        """Save a list of Impact instances to a CSV file.

        Args:
            impacts: List of Impact instances to save.
            filepath: Path where the CSV file will be written.
        """
        with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            field_titles = [
                cls.model_fields[field_name].title or field_name
                for field_name in cls.model_fields.keys()
            ]
            writer.writerow(field_titles)

            for impact in impacts:
                writer.writerow(
                    [
                        impact.alien_species,
                        impact.mechanism.value,
                        impact.category.value,
                        impact.evidence,
                        impact.confidence,
                        impact.justification,
                        ", ".join(impact.impacted_species),
                    ]
                )

    @classmethod
    def load_from_csv(cls, filepath: str) -> List["Impact"]:
        """Load a list of Impact instances from a CSV file.

        Args:
            filepath: Path to the CSV file to load.

        Returns:
            A list of Impact instances loaded from the CSV file.
        """
        impacts = []
        with open(filepath, "r", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                impacted_species = [
                    species.strip()
                    for species in row["Impacted native species"].split(",")
                    if species.strip()
                ]
                confidence_value = row["Confidence rating"].strip()
                confidence = confidence_value if confidence_value else None

                impact = cls(
                    alien_species=row["Species"],
                    mechanism=Mechanism(row["Impact mechanism"]),
                    category=Category(row["EICAT Category"]),
                    evidence=row["Evidence for EICAT impact category"],
                    confidence=confidence,
                    justification=row["Justification for confidence rating"],
                    impacted_species=impacted_species,
                )
                impacts.append(impact)
        return impacts


class UploadMetadata(BaseModel):
    id: str
    filename: str
    content_type: str
    size: int
    timestamp: str
    markdown_available: bool

    def save(self, base_path: Path) -> None:
        """Save metadata to JSON file in the upload folder"""
        file_folder = base_path / self.id
        file_folder.mkdir(parents=True, exist_ok=True)

        metadata_path = file_folder / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(self.model_dump(), f, indent=2)

    @classmethod
    def load(cls, folder_path: Path) -> Optional["UploadMetadata"]:
        """Load metadata from JSON file in the upload folder"""
        metadata_path = folder_path / "metadata.json"
        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path, "r") as f:
                metadata_dict = json.load(f)
            metadata_dict["id"] = folder_path.name
            return cls(**metadata_dict)
        except (json.JSONDecodeError, IOError, ValueError):
            return None

    @classmethod
    def load_by_id(cls, upload_id: str, base_path: Path) -> Optional["UploadMetadata"]:
        """Load metadata for a specific upload by ID"""
        file_folder = base_path / upload_id

        if not file_folder.exists():
            return None

        return cls.load(file_folder)

    @classmethod
    def load_all(cls, base_path: Path) -> List["UploadMetadata"]:
        """Load all metadata from upload folders"""
        uploads = []

        if not base_path.exists():
            return uploads

        for folder in base_path.iterdir():
            if folder.is_dir():
                metadata = cls.load(folder)
                if metadata:
                    uploads.append(metadata)

        uploads.sort(key=lambda x: x.timestamp, reverse=True)
        return uploads

    @classmethod
    def delete(cls, upload_id: str, base_path: Path) -> bool:
        """Delete an upload folder and all its contents"""
        file_folder = base_path / upload_id

        if not file_folder.exists():
            return False

        try:
            shutil.rmtree(file_folder)
            return True
        except OSError:
            return False
