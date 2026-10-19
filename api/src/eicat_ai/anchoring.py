from typing import List, Optional, Tuple

from eicat_ai.models import EvidenceSpan

PASSAGE_SEPARATOR = "\n\n"  # merge_by_mechanism joins merged evidence passages with this


def _normalise(text: str) -> Tuple[str, List[int]]:
    """Collapse whitespace runs to one space and casefold, returning the original offset of each output character."""
    out: List[str] = []
    index: List[int] = []
    in_space = False
    for i, c in enumerate(text):
        if c.isspace():
            if not in_space:
                out.append(" ")
                index.append(i)
            in_space = True
            continue
        in_space = False
        for f in c.casefold():
            out.append(f)
            index.append(i)
    return "".join(out), index


class _Locator:
    def __init__(self, markdown: str):
        self.markdown = markdown
        self._normalised: Optional[Tuple[str, List[int]]] = None

    def locate(self, passage: str) -> Optional[EvidenceSpan]:
        start = self.markdown.find(passage)
        if start >= 0:
            return EvidenceSpan(start=start, end=start + len(passage), text=passage)
        if self._normalised is None:
            self._normalised = _normalise(self.markdown)
        text, index = self._normalised
        needle, _ = _normalise(passage.strip())
        at = text.find(needle) if needle else -1
        if at < 0:
            return None
        start, end = index[at], index[at + len(needle) - 1] + 1
        return EvidenceSpan(start=start, end=end, text=self.markdown[start:end])


def anchor(markdown: str, evidence: str) -> List[EvidenceSpan]:
    """Locate AI evidence in the paper: the whole string first, then each passage, each by exact and then by
    whitespace- and case-insensitive match. Passages that cannot be found are kept as unanchored spans."""
    evidence = evidence.strip()
    if not evidence:
        return []
    locator = _Locator(markdown)
    whole = locator.locate(evidence)
    if whole is not None:
        return [whole]
    passages = [p.strip() for p in evidence.split(PASSAGE_SEPARATOR) if p.strip()]
    return [locator.locate(p) or EvidenceSpan(text=p) for p in passages]


def validate_spans(markdown: str, spans: List[EvidenceSpan]) -> None:
    """Check spans submitted by a reviewer: each must be anchored and cover exactly its text."""
    if not spans:
        raise ValueError("Evidence must have at least one span")
    for i, s in enumerate(spans):
        if s.start is None or s.end is None:
            raise ValueError(f"Span {i} has no offsets; evidence must be selected in the paper")
        if not 0 <= s.start < s.end <= len(markdown):
            raise ValueError(f"Span {i} offsets [{s.start}, {s.end}) are outside the paper")
        if markdown[s.start : s.end] != s.text:
            raise ValueError(f"Span {i} text does not match the paper at [{s.start}, {s.end})")


def evidence_text(spans: List[EvidenceSpan]) -> str:
    return PASSAGE_SEPARATOR.join(s.text for s in spans)
