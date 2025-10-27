from __future__ import annotations
from pydantic import BaseModel
import json
import csv
from typing import List, Literal
from enum import Enum


class Paper(BaseModel):
    title: str
    """The full paper title exactly as it appears in the article, without markup."""
    authors: List[str]
    """An ordered list of author full names as printed in the article."""
    content: str
    """
    The entire body of the article excluding the References section,
    rendered in valid Markdown. Preserve original wording and structure,
    using appropriate Markdown syntax for headings, lists, math, etc.
    Do not summarize or paraphrase.
    """
    references: List[str]
    """
    An ordered list of individual references extracted from the article's
    References/Bibliography section. Each element is a single full reference
    string exactly as printed (no Markdown). One reference per list item.
    """

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

    COMPETITION = "(1) Competition"
    PREDATION = "(2) Predation"
    HYBRIDISATION = "(3) Hybridisation"
    TRANSMISSION_OF_DISEASES = "(4) Transmission of diseases to native species"
    PARASITISM = "(5) Parasitism"
    POISONING_TOXICITY = "(6) Poisoning/ toxicity"
    BIO_FOULING = "(7) Bio-fouling"
    GRAZING_HERBIVORY_BROWSING = "(8) Grazing/herbivory/browsing"
    CHEMICAL_IMPACT = "(9) Chemical Impact on ecosystem"
    PHYSICAL_IMPACT = "(10) Physical Impact on ecosystem"
    STRUCTURAL_IMPACT = "(11) Structural Impact on ecosystem"
    INDIRECT_IMPACTS = "(12) Indirect impacts through interactions with other species"

    @property
    def description(self) -> str:
        """Get the full description of the mechanism."""
        descriptions = {
            "(1) Competition": "Competing for resources with native species (e.g. food, water, space)",
            "(2) Predation": "Alien taxa predate on native species",
            "(3) Hybridisation": "Alien species mating with native species, eliminating native population",
            "(4) Transmission of diseases to native species": "Passing diseases to native species",
            "(5) Parasitism": "Alien taxa parasites native species",
            "(6) Poisoning/ toxicity": "Alien taxa is poisonous or toxic through ingestion or contact with native species",
            "(7) Bio-fouling": "Physically impeding native species",
            "(8) Grazing/herbivory/browsing": "Alien species eating a native plant species",
            "(9) Chemical Impact on ecosystem": "Chemical changes to environment caused by alien species that affect native species",
            "(10) Physical Impact on ecosystem": "Physical changes to environment caused by alien species that affect native species",
            "(11) Structural Impact on ecosystem": "Structural changes to environment caused by alien species that affect native species",
            "(12) Indirect impacts through interactions with other species": "Potential for the alien species to increase one native species population that as a result decrease the population of another native species",
        }
        return descriptions[self.value]

    @property
    def name_friendly(self) -> str:
        """Get a human-friendly name for the mechanism."""
        return self.name.replace("_", " ").title()


class Impact(BaseModel):
    alien_species: str
    """Name of the alien species causing the impact"""
    mechanism: Mechanism
    """Mechanism by which the impact occurs. Available options:
        (1) Competition: Competing for resources with native species (e.g. food, water, space).
        (2) Predation: Alien taxa predate on native species.
        (3) Hybridisation: Alien species mating with native species, eliminating native population.
        (4) Transmission: of diseases to native species - Passing diseases to natice species.
        (5) Parasitism: Alien taxa parasites native species.
        (6) Poisoning/toxicity: Alien taxa is poisonous or toxic through ingestion or contact with native species.
        (7) Bio-fouling: physically impeding native species.
        (8) Grazing/herbivory/browsing: Alien species eating a native plant species.
        (9) Chemical Impact on ecosystem: Chemical changes to environment caused by alien speceies that affect native species.
        (10) Physical Impact on ecosystem: Physical changes to environment caused by alien speceies that affect native species.
        (11) Structural Impact on ecosystem: Structural changes to environment caused by alien speceies that affect native species.
        (12) Indirect impacts through interactions with other species: Potential for the alien species to increase one native species population that as a result decrease the population of another native species.
    """
    category: Category
    """Category of the impact. Available options:
    MV (Massive): Irreversible extinction of a native species
    MR (Major): Extinction of local population of native species that is reversible
    MO (Moderate): Decline in native species population
    MN (Minor): No decline in population but some impact on performance of native species
    MC (Minimal Concern): No significant impact observed
    DD (Data Deficient): No data available or impacts or insufficient time for impacts to be observed"""
    evidence: str
    """Excerpt of text from the paper extracted verbatim as evidence for the impact."""
    confidence: Literal["low", "medium", "high"]
    """A confidence rating"""
    justification: str
    """Explanation of choice in confidence rating"""
    impacted_species: List[str]
    """A list of the impacted species"""

    @classmethod
    def save_to_csv(cls, impacts: List["Impact"], filepath: str) -> None:
        """Save a list of Impact instances to a CSV file.

        Args:
            impacts: List of Impact instances to save.
            filepath: Path where the CSV file will be written.
        """
        with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)

            # Write header
            writer.writerow(
                [
                    "alien_species",
                    "mechanism",
                    "category",
                    "evidence",
                    "confidence",
                    "justification",
                    "impacted_species",
                ]
            )

            # Write data rows
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
