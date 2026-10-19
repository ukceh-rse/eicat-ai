# Spec Delta

## Purpose

Lets EICAT experts review the impacts the pipeline extracts for an analysis — verifying, correcting, adding and removing them — while keeping the AI's original output traceable.

## ADDED Requirements

### Requirement: Impacts have stable identity and provenance
Every impact on an analysis SHALL have a stable id, the paper it belongs to, and an origin of `ai` or `human`. Origin SHALL never change after creation.

#### Scenario: AI impact created by a run
- **WHEN** a run extracts an impact from a paper
- **THEN** the impact is stored with a new id, the paper id, origin `ai` and the id of the run that produced it

#### Scenario: Impact id survives edits
- **WHEN** a reviewer edits any field of an impact
- **THEN** the impact keeps the same id and origin

### Requirement: AI output is preserved unchanged
An AI impact SHALL keep a snapshot of the AI's original values that is never modified by review actions, separate from the impact's current values.

#### Scenario: Edit leaves AI snapshot intact
- **WHEN** a reviewer changes an AI impact's category from MO to MR
- **THEN** the impact's current category is MR and its AI snapshot category is still MO

#### Scenario: Differences from AI are visible
- **WHEN** a reviewer views an AI impact whose current values differ from its AI snapshot
- **THEN** the UI marks each differing field and shows the AI's original value on demand

### Requirement: Reviewer can verify AI impacts
Each AI impact SHALL have a verified flag, initially false, that a reviewer can set and clear.

#### Scenario: Verify an impact
- **WHEN** a reviewer ticks the verified checkbox on an unverified AI impact
- **THEN** the impact is stored as verified

#### Scenario: Unverify an impact
- **WHEN** a reviewer unticks the verified checkbox on a verified AI impact
- **THEN** the impact is stored as unverified

### Requirement: Editing verifies an impact
Any reviewer edit to an AI impact's fields or evidence SHALL set the impact's verified flag to true.

#### Scenario: Edit auto-verifies
- **WHEN** a reviewer edits the mechanism of an unverified AI impact
- **THEN** the impact is stored with the new mechanism and verified set to true

### Requirement: All impact fields are editable
A reviewer SHALL be able to edit alien species, mechanism, category, reversibility, confidence, justification and impacted species of any active impact, with the same allowed values as AI-extracted impacts.

#### Scenario: Invalid value rejected
- **WHEN** a reviewer submits a category that is not an EICAT category code
- **THEN** the API rejects the edit with a validation error and the impact is unchanged

#### Scenario: Reversibility applies to MR and MV
- **WHEN** a reviewer sets the category to MR or MV
- **THEN** the edit form requires a reversibility value, and for other categories reversibility is cleared

### Requirement: Edits accept an optional reason
A reviewer SHALL be able to attach an optional free-text reason to any review action. A reason SHALL never be required.

#### Scenario: Edit with reason
- **WHEN** a reviewer edits an impact and enters a reason
- **THEN** the reason is recorded with that action in the audit trail

#### Scenario: Edit without reason
- **WHEN** a reviewer edits an impact without entering a reason
- **THEN** the edit is saved

### Requirement: Reviewer can add impacts
A reviewer SHALL be able to create an impact on a paper by selecting its evidence in the paper text and filling in its fields. Such impacts SHALL have origin `human`, no AI snapshot, and be treated as verified.

#### Scenario: Add impact from highlighted text
- **WHEN** a reviewer highlights a passage in a paper, chooses to add an impact, and saves the form
- **THEN** a new active impact with origin `human` exists on that paper with the highlighted passage as its evidence

### Requirement: Reviewer can remove and restore impacts
Removing an impact SHALL mark it removed rather than delete it. A removed impact SHALL be restorable to active.

#### Scenario: Remove an impact
- **WHEN** a reviewer removes an active impact
- **THEN** the impact no longer appears among the paper's active impacts and appears in that paper's removed list

#### Scenario: Restore a removed impact
- **WHEN** a reviewer restores a removed impact
- **THEN** the impact is active again with the values it had when removed

### Requirement: Review view groups impacts by state
For each paper, the UI SHALL list active impacts with their verified state, and SHALL provide collapsed sections listing removed impacts and suppressed impacts with their counts.

#### Scenario: Paper with removed and suppressed impacts
- **WHEN** a paper has 3 active, 1 removed and 2 suppressed impacts
- **THEN** the paper shows 3 rows in its table, a collapsed "Removed (1)" section and a collapsed "Suppressed (2)" section

#### Scenario: Review progress
- **WHEN** a paper has 3 active impacts of which 2 are verified or human-created
- **THEN** the paper header shows "2/3 verified"

### Requirement: Impacts of papers removed from an analysis are retained
Removing a paper from an analysis SHALL hide its impacts from the review view without deleting them.

#### Scenario: Paper removed and re-added
- **WHEN** a reviewer removes a paper from an analysis and later adds it back
- **THEN** the paper's impacts, in their previous states, are shown again
