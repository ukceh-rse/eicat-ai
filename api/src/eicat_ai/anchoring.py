import math
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Set, Tuple

from eicat_ai.models import EvidenceSpan

PASSAGE_SEPARATOR = "\n\n"  # merge_by_mechanism joins merged evidence passages with this

# markdown the AI never quotes: link targets (citations are `[[7]](#b6 "title")`) and HTML tags
_MARKUP = re.compile(r'\]\((?:[^()"\n]|"[^"\n]*")*\)|</?[a-zA-Z][^<>\n]*>')
# brackets, quotes and markup around a passage matched by letters and digits alone, so its span doesn't stop short
_OPENING = re.compile(r"[\[(\"'“‘*_]+$")
_CLOSING = re.compile(r'(?:\]\((?:[^()"\n]|"[^"\n]*")*\)|[\])}"\'”’%*_])+')
# a link whose text is short enough to be a citation, e.g. `[8,](#b7 "title")`
_CITATION = re.compile(r'\[[^\[\]\n]{0,60}\]\((?:[^()"\n]|"[^"\n]*")*\)')
_ELLIPSIS = re.compile(r"\[?(?:\.\s*){3}\]?|\[?…\]?")
# sentence ends, and line breaks, which end headings, list items and table rows
_UNIT_END = re.compile(r"(?<=[.!?])\s+(?=[^a-z])|\n+")
_WORD = re.compile(r"\w+")
MAX_WINDOW = 8  # sentences an approximate match may span
MIN_BLOCK = 8  # shortest run of letters and digits an alignment keeps
ALIGNED = 0.5  # share of the passage aligned for the match to be trimmed to the aligned text
VERBATIM = 0.9  # share aligned for the match to count as the passage itself (OCR glitches, dropped citations)
MIN_SENTENCE = 20  # letters and digits; a shorter sentence is anchored with its neighbour, as it may occur anywhere
MAX_GAP = 10  # letters and digits, besides citations, between spans merged as adjacent
MAX_ELISION = 1000  # letters and digits an elision (`...`) may skip, about a paragraph
# letters and digits by which an alignment's first or last block is further from the rest in the paper than in the
# passage, for it to be dropped as a word of the passage matched in a neighbouring sentence
STRAY = 20


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


def _fold(text: str, skip_markup: bool = False) -> Tuple[str, List[int]]:
    """Keep only letters and digits, casefolded and without accents, so formatting, punctuation and markup don't
    matter; returns the original offset of each output character."""
    skipped = [(m.start(), m.end()) for m in _MARKUP.finditer(text)] if skip_markup else []
    out: List[str] = []
    index: List[int] = []
    k = 0
    for i, c in enumerate(text):
        while k < len(skipped) and skipped[k][1] <= i:
            k += 1
        if k < len(skipped) and skipped[k][0] <= i:
            continue
        if c.isascii():
            if c.isalnum():
                out.append(c.lower())
                index.append(i)
            continue
        for d in unicodedata.normalize("NFKD", c):
            for f in d.casefold():
                if f.isalnum():
                    out.append(f)
                    index.append(i)
    return "".join(out), index


def _sentences(passage: str) -> List[str]:
    out: List[str] = []
    for p in (p.strip() for p in _UNIT_END.split(passage)):
        if not p:
            continue
        if out and len(_fold(out[-1])[0]) < MIN_SENTENCE:
            out[-1] += " " + p
        else:
            out.append(p)
    if len(out) > 1 and len(_fold(out[-1])[0]) < MIN_SENTENCE:
        tail = out.pop()
        out[-1] += " " + tail
    return out


def _matches(needle: str, region: str, b0: int = 0) -> List[Tuple[int, int, int]]:
    """(needle offset, region offset + b0, size) of the runs of at least MIN_BLOCK characters aligned in order."""
    blocks = SequenceMatcher(None, needle, region, autojunk=False).get_matching_blocks()
    return [(a, b + b0, size) for a, b, size in blocks if size >= MIN_BLOCK]


def _alignment(needle: str, region: str) -> List[Tuple[int, int, int]]:
    """Runs of the needle aligned in order with the region. An end run further from the rest in the region than in
    the needle, by more than STRAY, is a word of the needle matched in a neighbouring sentence: it's dropped, and the
    end of the needle aligned again only within reach of the rest."""
    blocks = _matches(needle, region)
    stray = lambda x, y: (y[1] - x[1]) - (y[0] - x[0]) > STRAY
    while len(blocks) > 1 and stray(blocks[0], blocks[1]):
        blocks = blocks[1:]
    while len(blocks) > 1 and stray(blocks[-2], blocks[-1]):
        blocks = blocks[:-1]
    if not blocks:
        return []
    a, b, _ = blocks[0]
    if a > 0:
        lo = max(b - a - STRAY, 0)
        blocks = _matches(needle[:a], region[lo:b], lo) + blocks
    a, b, size = blocks[-1]
    a, b = a + size, b + size
    if a < len(needle):
        hi = min(b + len(needle) - a + STRAY, len(region))
        blocks += [(x + a, y, n) for x, y, n in _matches(needle[a:], region[b:hi], b)]
    return blocks


def _words(text: str) -> List[str]:
    return [w for w in _WORD.findall(_fold_words(text)) if len(w) > 1 or w.isdigit()]


def _fold_words(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))


class Locator:
    """Finds evidence passages in one paper. Build one per paper: the folded text and sentence index are computed
    once, on first need, and reused for every passage."""

    def __init__(self, markdown: str):
        self.markdown = markdown
        self._normalised: Optional[Tuple[str, List[int]]] = None
        self._folded: Optional[Tuple[str, List[int]]] = None
        self._units: Optional[List[Tuple[int, int, Set[str]]]] = None
        self._idf: Dict[str, float] = {}

    def anchor(self, evidence: str) -> List[EvidenceSpan]:
        """Locate AI evidence in the paper: the whole string first, then each passage, then each sentence of a
        passage, as the AI joins quotes from different places. Sentences the paper doesn't contain word for word are
        anchored to the closest passage, marked approximate. Spans adjacent in the paper are merged."""
        evidence = evidence.strip()
        if not evidence:
            return []
        whole = self.locate(evidence)
        if whole is not None:
            return [whole]
        spans: List[EvidenceSpan] = []
        for passage in (p.strip() for p in evidence.split(PASSAGE_SEPARATOR)):
            if not passage:
                continue
            found = self.locate(passage)
            if found is not None:
                spans.append(found)
                continue
            for sentence in _sentences(passage):
                span = self.locate(sentence) or self.closest(sentence) or EvidenceSpan(text=sentence)
                last = spans[-1] if spans else None
                if last is not None and self._adjacent(last, span):
                    approximate = last.approximate or span.approximate
                    spans[-1] = self._span(min(last.start, span.start), max(last.end, span.end), approximate)
                else:
                    spans.append(span)
        return spans

    def _adjacent(self, a: EvidenceSpan, b: EvidenceSpan) -> bool:
        """Whether b overlaps a or follows it with little more than punctuation, whitespace or markup between."""
        if a.start is None or b.start is None:
            return False
        if b.start <= a.end and a.start <= b.end:
            return True
        gap = _CITATION.sub(" ", self.markdown[a.end : b.start]) if a.end < b.start else None
        return gap is not None and len(_fold(gap, skip_markup=True)[0]) <= MAX_GAP

    def _span(self, start: int, end: int, approximate: bool = False) -> EvidenceSpan:
        return EvidenceSpan(start=start, end=end, text=self.markdown[start:end], approximate=approximate)

    def locate(self, passage: str) -> Optional[EvidenceSpan]:
        """The passage as written, by exact, whitespace- and case-insensitive, then letters-and-digits-only match;
        an elided passage (`...`) matches from its first part to its last."""
        start = self.markdown.find(passage)
        while start >= 0 and not self._whole_words(start, start + len(passage)):
            start = self.markdown.find(passage, start + 1)
        if start >= 0:
            return EvidenceSpan(start=start, end=start + len(passage), text=passage)
        if self._normalised is None:
            self._normalised = _normalise(self.markdown)
        found = self._find(self._normalised, [_normalise(passage.strip())[0]])
        if found is None:
            if self._folded is None:
                self._folded = _fold(self.markdown, skip_markup=True)
            parts = [_fold(p, skip_markup=True)[0] for p in _ELLIPSIS.split(passage)]
            found = self._find(self._folded, [p for p in parts if p])
        if found is None:
            return None
        return self._span(*self._widen(*found))

    def _widen(self, start: int, end: int) -> Tuple[int, int]:
        """Take in the rest of the words at either end of a match of letters and digits, and the brackets, quotes
        and markup that open and close it."""
        text = self.markdown
        while start > 0 and text[start - 1].isalnum():
            start -= 1
        while end < len(text) and text[end].isalnum():
            end += 1
        opening = _OPENING.search(self.markdown, max(start - 8, 0), start)
        closing = _CLOSING.match(self.markdown, end)
        return opening.start() if opening else start, closing.end() if closing else end

    def _whole_words(self, start: int, end: int) -> bool:
        """Whether a match neither starts nor ends inside a word of the paper, so a short passage can't anchor to
        part of an unrelated word."""
        text = self.markdown
        cut_start = 0 < start < len(text) and text[start - 1].isalnum() and text[start].isalnum()
        cut_end = 0 < end < len(text) and text[end - 1].isalnum() and text[end].isalnum()
        return not cut_start and not cut_end

    def _find(self, haystack: Tuple[str, List[int]], needles: List[str]) -> Optional[Tuple[int, int]]:
        """Original offsets spanning the needles found in order, each after the last and at most MAX_ELISION
        characters on, and starting and ending at word boundaries."""
        text, index = haystack
        if not needles:
            return None
        first = text.find(needles[0])
        while first >= 0:
            at = first + len(needles[0])
            for needle in needles[1:]:
                found = text.find(needle, at, at + MAX_ELISION + len(needle))
                if found < 0:
                    break
                at = found + len(needle)
            else:
                start, end = index[first], index[at - 1] + 1
                if self._whole_words(start, end):
                    return start, end
            first = text.find(needles[0], first + 1)
        return None

    def closest(self, passage: str) -> Optional[EvidenceSpan]:
        """The run of consecutive sentences most like the passage, by IDF-weighted word overlap (F1)."""
        if self._units is None:
            self._index_units()
        words = set(_words(_MARKUP.sub(" ", passage)))
        want = sum(self._idf.get(w, 0.0) for w in words)
        if want == 0:
            return None
        units = self._units
        best, best_score = None, 0.0
        for i in range(len(units)):
            if not units[i][2] & words:
                continue  # a best window can always drop a leading sentence that shares no words
            seen: Set[str] = set()
            have = hit = 0.0
            for j in range(i, min(i + MAX_WINDOW, len(units))):
                new = units[j][2] - seen
                seen |= new
                have += sum(self._idf[w] for w in new)
                hit += sum(self._idf[w] for w in new & words)
                score = 2 * hit / (have + want)
                if score > best_score:
                    best, best_score = (units[i][0], units[j][1]), score
        if best is None:
            return None
        return self._align(passage, *best)

    def _align(self, passage: str, start: int, end: int) -> EvidenceSpan:
        """Trim a sentence window, widened by a sentence each side, to the text aligned with the passage, when
        enough of it aligns; otherwise keep the window."""
        units = self._units
        i = next(k for k, u in enumerate(units) if u[0] == start)
        j = next(k for k, u in enumerate(units) if u[1] == end)
        lo, hi = units[max(i - 1, 0)][0], units[min(j + 1, len(units) - 1)][1]
        region, index = _fold(self.markdown[lo:hi], skip_markup=True)
        needle = _fold(passage, skip_markup=True)[0]
        blocks = _alignment(needle, region)
        aligned = sum(size for _, _, size in blocks) / len(needle) if needle else 0.0
        if aligned >= ALIGNED:
            (_, first, _), (_, last, size) = blocks[0], blocks[-1]
            start, end = self._widen(lo + index[first], lo + index[last + size - 1] + 1)
        return self._span(start, end, aligned < VERBATIM)

    def _index_units(self):
        units: List[Tuple[int, int, Set[str]]] = []
        at = 0
        for m in [*_UNIT_END.finditer(self.markdown), None]:
            end = m.start() if m else len(self.markdown)
            raw = self.markdown[at:end]
            stripped = raw.strip()
            if stripped:
                start = at + raw.index(stripped)
                words = set(_words(_MARKUP.sub(" ", stripped)))
                if words:
                    units.append((start, start + len(stripped), words))
            at = m.end() if m else at
        df: Dict[str, int] = {}
        for _, _, words in units:
            for w in words:
                df[w] = df.get(w, 0) + 1
        self._idf = {w: math.log((len(units) + 1) / n) for w, n in df.items()}
        self._units = units


def anchor(markdown: str, evidence: str) -> List[EvidenceSpan]:
    """Locate AI evidence in a paper; see `Locator.anchor`. Use a `Locator` to anchor several in the same paper."""
    return Locator(markdown).anchor(evidence)


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
