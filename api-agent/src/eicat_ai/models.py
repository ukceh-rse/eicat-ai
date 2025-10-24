from __future__ import annotations
from pydantic import BaseModel
import json
from typing import List


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
