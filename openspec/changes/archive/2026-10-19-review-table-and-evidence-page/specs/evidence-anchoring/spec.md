## MODIFIED Requirements

### Requirement: AI evidence is located in the paper
When a run produces an impact, the system SHALL locate its evidence in the paper markdown, as a whole and then passage by passage, first by exact match, then by whitespace- and case-insensitive match, then by matching letters and digits only (ignoring punctuation, accents, markdown links and HTML tags, with `...` matching any text). A passage still not located SHALL be located sentence by sentence by the same rules, and spans adjacent in the paper SHALL be merged.

#### Scenario: Verbatim passage
- **WHEN** an AI evidence passage appears verbatim in the paper
- **THEN** the impact has an anchored span at that location

#### Scenario: Passage differs only in whitespace
- **WHEN** an AI evidence passage matches the paper only after collapsing whitespace and ignoring case
- **THEN** the impact has an anchored span covering the matching paper text

#### Scenario: Passage differs in formatting
- **WHEN** an AI evidence passage matches the paper only on letters and digits, e.g. it quotes `[7]` for the citation link `[[7]](#b6 "title")`
- **THEN** the impact has an anchored span covering the matching paper text, including the citation

#### Scenario: Passage joins sentences from different places
- **WHEN** an AI evidence passage joins sentences that are apart in the paper
- **THEN** the impact has an anchored span for each

### Requirement: Evidence is edited only by selecting paper text
The system SHALL NOT accept free-text evidence from a reviewer. A reviewer SHALL change evidence only by selecting passages of the paper on the evidence page, and every span a reviewer saves SHALL be anchored.

#### Scenario: Reselect evidence
- **WHEN** a reviewer opens an impact's evidence page, clears the existing spans, highlights a new passage and saves
- **THEN** the impact's evidence is a single anchored span covering the highlighted passage

#### Scenario: Add a second passage
- **WHEN** a reviewer highlights an additional passage on the evidence page and saves
- **THEN** the impact keeps its existing spans and gains a span for the new passage

#### Scenario: Span not matching paper rejected
- **WHEN** the API receives a span whose text does not equal the paper markdown between its offsets
- **THEN** the API rejects the edit with a validation error

### Requirement: Evidence is shown in context
Each impact SHALL have an evidence page, with its own address, showing the paper with the impact's anchored spans highlighted and the first span in view, beside a panel listing the impact's spans. The UI SHALL NOT show the paper in a popup.

#### Scenario: View evidence in paper
- **WHEN** a reviewer clicks an impact's evidence in the review table
- **THEN** the impact's evidence page opens with its spans highlighted, the first span in view, and the spans listed in the side panel

#### Scenario: Evidence page opened by address
- **WHEN** a reviewer opens the address of an impact's evidence page directly
- **THEN** the same page is shown for that impact

#### Scenario: Return to the table
- **WHEN** a reviewer saves or cancels on the evidence page
- **THEN** the analysis page is shown with that impact's row highlighted

## ADDED Requirements

### Requirement: AI evidence not quoted word for word is anchored approximately
A sentence that cannot be located SHALL be anchored to the run of consecutive paper sentences most like it, by IDF-weighted word overlap, trimmed to the text aligned with it. The span SHALL be marked approximate unless at least 90% of its letters and digits align, and the UI SHALL tell the reviewer that the closest passage is shown.

#### Scenario: Paraphrased evidence
- **WHEN** an AI evidence passage paraphrases the paper
- **THEN** the impact has an approximate span on the closest paper passage and the review table marks that the evidence is not quoted word for word

#### Scenario: OCR glitch or dropped citation
- **WHEN** an AI evidence sentence differs from the paper only by a few characters, so at least 90% of its letters and digits align
- **THEN** the impact has an anchored span on that passage that is not marked approximate

#### Scenario: Reviewer keeps an approximate span
- **WHEN** a reviewer saves evidence that includes a span the AI anchored approximately
- **THEN** the saved span is no longer approximate

### Requirement: Evidence sharing no words with the paper is left unanchored
An AI evidence sentence that shares no words with the paper SHALL be kept as an unanchored span holding the AI's text and no offsets, and the UI SHALL flag that span to the reviewer.

#### Scenario: Evidence absent from the paper
- **WHEN** an AI evidence sentence shares no words with the paper
- **THEN** the impact has an unanchored span with the AI's text, and the review table and evidence page flag that span as not found in the paper

### Requirement: An AI impact's evidence is paper text
An AI impact's evidence SHALL be its spans' texts in order, so every anchored span shows the paper text it covers even when another span of the impact is unanchored; only unanchored spans show the AI's text. The AI's own wording SHALL be kept as the AI's value, and the UI SHALL show it with an approximate or unanchored span's status, not as a reviewer's change.

#### Scenario: Paraphrased evidence is shown as paper text
- **WHEN** a run anchors an AI evidence passage approximately
- **THEN** the impact's evidence is the text of the closest paper passage, and the AI's wording is shown as its original value

#### Scenario: One passage cannot be anchored
- **WHEN** a run anchors two of an impact's evidence sentences and leaves a third unanchored
- **THEN** the impact's evidence is the paper text of the two anchored spans followed by the AI's text of the third, and only the third is flagged

#### Scenario: Evidence stored before approximate anchoring
- **WHEN** the API starts and a stored AI impact or sighting has an unanchored span
- **THEN** its evidence is anchored again from the AI's evidence, an impact whose evidence no reviewer changed takes the text of its new spans, and reviewers' spans and evidence are left as they are

## REMOVED Requirements

### Requirement: Unlocatable AI evidence is flagged
**Reason**: Evidence the exact and whitespace-insensitive rules miss is now anchored approximately; only evidence sharing no words with the paper stays unanchored.
**Migration**: Covered by "AI evidence not quoted word for word is anchored approximately" and "Evidence sharing no words with the paper is left unanchored"; stored unanchored spans are re-anchored on startup.
