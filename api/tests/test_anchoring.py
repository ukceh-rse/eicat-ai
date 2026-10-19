import pytest

from eicat_ai.anchoring import Locator, anchor, evidence_text, validate_spans
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


def test_markdown_and_punctuation_in_paper_are_matched_through():
    [span] = anchor(PAPER, "Rats ate most eggs of the native petrel")
    check(span)
    assert span.text == "Rats ate **most** eggs of the native petrel"
    assert not span.approximate


CITED = (
    "## Discussion\n\n"
    "Kererū numbers rose after control [[7]](#b6 \"Bird counts (2010) in Northland\"). "
    "Unrelated text about rainfall follows here. "
    "Magpies were seen chasing tūī from feeding trees on several occasions.\n"
)


def check_in(paper: str, span: EvidenceSpan):
    assert span.start is not None and span.end is not None
    assert paper[span.start : span.end] == span.text


def test_citation_links_accents_and_quotes_are_ignored():
    [span] = anchor(CITED, "\u201cKereru numbers rose after control [7].\u201d")
    check_in(CITED, span)
    assert span.text.startswith("Kererū numbers") and span.text.endswith('Northland")')
    assert not span.approximate


def test_ellipsis_spans_first_to_last_part():
    [span] = anchor(CITED, "Kererū numbers rose after control ... Magpies were seen chasing tūī")
    check_in(CITED, span)
    assert span.text.startswith("Kererū") and span.text.endswith("chasing tūī")


def test_ellipsis_does_not_bridge_distant_text():
    paper = "The species was recorded on the island.\n\n" + "Soil chemistry and rainfall varied. " * 100 + "\n\nNumbers declined."
    spans = anchor(paper, "The species was recorded ... declined")
    assert all(s.start is None or s.end - s.start < 200 or s.approximate for s in spans)
    assert not any(s.start == 0 and s.end > len(paper) - 20 for s in spans)


def test_short_passage_does_not_anchor_inside_a_word():
    [span] = anchor("These were analysed separately in each plot.\n\nMice ate seeds.", "Rate.")
    assert span.text != "separately" and (span.start is None or span.approximate)


def test_sentences_from_different_places_are_anchored_separately():
    spans = anchor(CITED, "Magpies were seen chasing tūī from feeding trees on several occasions. "
                          "Kererū numbers rose after control [7].")
    assert len(spans) == 2
    for s in spans:
        check_in(CITED, s)
        assert not s.approximate
    assert spans[0].text.startswith("Magpies") and spans[1].text.startswith("Kererū")


def test_adjacent_sentences_merge_into_one_span():
    # quoted without the citation between them, so the whole passage doesn't match
    [span] = anchor(CITED, "Kererū numbers rose after control. Unrelated text about rainfall follows here.")
    check_in(CITED, span)
    assert "Kererū" in span.text and "rainfall" in span.text


def test_near_verbatim_quote_is_not_approximate():
    paper = "Kalij Pheasants destroyed a signi cantly smaller percentage of ingested seeds than francolins.\n"
    [span] = anchor(paper, "Kalij Pheasants destroyed a significantly smaller percentage of ingested seeds than francolins.")
    check_in(paper, span)
    assert span.text.startswith("Kalij") and span.text.endswith("francolins")
    assert not span.approximate


def test_paraphrase_anchors_to_closest_sentence_as_approximate():
    [span] = anchor(CITED, "Tūī were chased away from trees by magpies.")
    check_in(CITED, span)
    assert span.text.startswith("Magpies were seen chasing")
    assert span.approximate


def test_one_locator_anchors_many():
    locator = Locator(CITED)
    assert [s.approximate for e in ["Unrelated text about rainfall", "rainfall is mentioned"] for s in locator.anchor(e)] == [False, True]


def test_nothing_in_common_is_unanchored():
    assert anchor(PAPER, "Zzyzx qwerty.") == [EvidenceSpan(text="Zzyzx qwerty.")]
    assert anchor("", "Rats ate eggs.") == [EvidenceSpan(text="Rats ate eggs.")]


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


def test_aligned_span_keeps_whole_words():
    paper = "Intro.\n\nBoth markers suggested the presence of T. carnifex and hybrids at Beam Brook and at Sturtwood Farm.\n"
    [span] = anchor(paper, "The markers supported the presence of T. carnifex and hybrids at Beam Brook and at Sturtwood Farm.")
    check_in(paper, span)
    assert span.text.startswith("markers suggested") and span.text.endswith("Farm")
