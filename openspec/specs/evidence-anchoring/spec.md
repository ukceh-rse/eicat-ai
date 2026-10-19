# evidence-anchoring Specification

## Purpose

Ties each impact's evidence to exact passages of the paper text, so evidence can be shown in context, changed only by selecting text, and checked against what the paper actually says.

## Requirements

### Requirement: Evidence is a set of paper text spans
An impact's evidence SHALL be stored as one or more spans, each giving start and end character offsets into the paper's markdown and the text those offsets cover.

#### Scenario: Span text matches the paper
- **WHEN** an anchored evidence span is stored with start S and end E
- **THEN** its text equals the paper markdown from offset S up to offset E

#### Scenario: Impact with several passages
- **WHEN** an impact's evidence comes from two separate passages
- **THEN** the impact has two spans, one per passage

### Requirement: AI evidence is located in the paper
When a run produces an impact, the system SHALL split its evidence into passages and locate each passage in the paper markdown, first by exact match and then by whitespace- and case-insensitive match.

#### Scenario: Verbatim passage
- **WHEN** an AI evidence passage appears verbatim in the paper
- **THEN** the impact has an anchored span at that location

#### Scenario: Passage differs only in whitespace
- **WHEN** an AI evidence passage matches the paper only after collapsing whitespace and ignoring case
- **THEN** the impact has an anchored span covering the matching paper text

### Requirement: Unlocatable AI evidence is flagged
An AI evidence passage that cannot be located SHALL be kept as an unanchored span holding the AI's text and no offsets, and the UI SHALL warn the reviewer on that impact.

#### Scenario: Paraphrased evidence
- **WHEN** an AI evidence passage does not occur in the paper by either matching rule
- **THEN** the impact has an unanchored span with the AI's text and the review table shows a warning that the evidence could not be found in the paper

### Requirement: Evidence is edited only by selecting paper text
The system SHALL NOT accept free-text evidence from a reviewer. A reviewer SHALL change evidence only by selecting passages in the paper viewer, and every span a reviewer saves SHALL be anchored.

#### Scenario: Reselect evidence
- **WHEN** a reviewer opens an impact's evidence editor, clears the existing spans, highlights a new passage and saves
- **THEN** the impact's evidence is a single anchored span covering the highlighted passage

#### Scenario: Add a second passage
- **WHEN** a reviewer highlights an additional passage in the evidence editor and saves
- **THEN** the impact keeps its existing spans and gains a span for the new passage

#### Scenario: Span not matching paper rejected
- **WHEN** the API receives a span whose text does not equal the paper markdown between its offsets
- **THEN** the API rejects the edit with a validation error

### Requirement: Evidence is shown in context
The paper viewer SHALL highlight an impact's anchored spans and scroll to the first one when opened from that impact.

#### Scenario: View evidence in paper
- **WHEN** a reviewer chooses to view an impact's evidence in the paper
- **THEN** the paper viewer opens with that impact's spans highlighted and the first span in view
