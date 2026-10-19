import pytest

from eicat_ai.anchoring import anchor, evidence_text, validate_spans
from eicat_ai.models import EvidenceSpan

PAPER = (
    "# Results\n\n"
    "Rats ate **most** eggs of the native petrel.\n"
    "Nest   success fell to 12%.\n\n"
    "Predation by rats was observed at every site.\n\n"
    "Predation by rats was observed at every site.\n"
)


def check(span: EvidenceSpan):
    assert span.start is not None and span.end is not None
    assert PAPER[span.start : span.end] == span.text


def test_verbatim():
    [span] = anchor(PAPER, "Nest   success fell to 12%.")
    check(span)
    assert span.text == "Nest   success fell to 12%."


def test_whitespace_and_case_differences():
    [span] = anchor(PAPER, "nest success\nFELL to 12%.")
    check(span)
    assert span.text == "Nest   success fell to 12%."


def test_whole_string_found_before_split():
    evidence = "Nest   success fell to 12%.\n\nPredation by rats was observed at every site."
    [span] = anchor(PAPER, evidence)
    check(span)
    assert span.text == evidence


def test_multi_passage():
    spans = anchor(PAPER, "# Results\n\nNest success fell to 12%.")
    assert len(spans) == 2
    for s in spans:
        check(s)
    assert spans[0].start < spans[1].start


def test_repeated_passage_anchors_first_occurrence():
    [span] = anchor(PAPER, "Predation by rats was observed at every site.")
    check(span)
    assert span.start == PAPER.find("Predation by rats")


def test_not_found_is_unanchored():
    spans = anchor(PAPER, "Rats were eradicated in 2004.\n\nNest success fell to 12%.")
    assert spans[0] == EvidenceSpan(text="Rats were eradicated in 2004.")
    check(spans[1])


def test_markdown_syntax_in_paper_is_not_matched_through():
    # the AI quotes rendered text, so "Rats ate most eggs" doesn't match "Rats ate **most** eggs"
    [span] = anchor(PAPER, "Rats ate most eggs of the native petrel.")
    assert span.start is None


def test_empty_evidence():
    assert anchor(PAPER, "  ") == []


def test_evidence_text_joins_passages():
    assert evidence_text([EvidenceSpan(text="a"), EvidenceSpan(text="b")]) == "a\n\nb"


def test_valid_span():
    start = PAPER.find("Nest")
    validate_spans(PAPER, [EvidenceSpan(start=start, end=start + 4, text="Nest")])


@pytest.mark.parametrize(
    "span, message",
    [
        (EvidenceSpan(text="Nest"), "no offsets"),
        (EvidenceSpan(start=0, end=4, text="Nest"), "does not match"),
        (EvidenceSpan(start=len(PAPER) - 2, end=len(PAPER) + 3, text="x"), "outside"),
        (EvidenceSpan(start=-1, end=3, text="x"), "outside"),
        (EvidenceSpan(start=5, end=5, text=""), "outside"),
    ],
)
def test_invalid_span(span, message):
    with pytest.raises(ValueError, match=message):
        validate_spans(PAPER, [span])


def test_no_spans():
    with pytest.raises(ValueError, match="at least one"):
        validate_spans(PAPER, [])
