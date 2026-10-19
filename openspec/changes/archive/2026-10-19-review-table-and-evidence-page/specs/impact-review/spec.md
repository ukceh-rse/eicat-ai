## MODIFIED Requirements

### Requirement: AI output is preserved unchanged
An AI impact SHALL keep a snapshot of the AI's original values that is never modified by review actions, separate from the impact's current values. Evidence that differs from the AI's only because the run anchored it to paper text SHALL NOT count as a difference from the AI.

#### Scenario: Edit leaves AI snapshot intact
- **WHEN** a reviewer changes an AI impact's category from MO to MR
- **THEN** the impact's current category is MR and its AI snapshot category is still MO

#### Scenario: Differences from AI are visible
- **WHEN** a reviewer views an AI impact whose current values differ from its AI snapshot
- **THEN** the UI marks the impact as changed from AI and lists each differing field with the AI's original value on demand

#### Scenario: Anchored evidence is not a change
- **WHEN** a run anchors an AI impact's paraphrased evidence to paper text and no reviewer has changed the impact
- **THEN** the impact is not marked as changed from AI, and the AI's wording is shown with the evidence's approximate status

### Requirement: All impact fields are editable
A reviewer SHALL be able to edit alien species, mechanism, category, reversibility, confidence, justification and impacted species of any active impact, with the same allowed values as AI-extracted impacts.

#### Scenario: Invalid value rejected
- **WHEN** a reviewer submits a category that is not an EICAT category code
- **THEN** the API rejects the edit with a validation error and the impact is unchanged

#### Scenario: Reversibility applies to MR and MV
- **WHEN** a reviewer changes the category to MR or MV in the review table
- **THEN** the category cell asks for a reversibility value and the edit is saved only once one is chosen, and for other categories reversibility is cleared

### Requirement: Edits accept an optional reason
A reviewer SHALL be able to attach an optional free-text reason to any review action. A reason SHALL never be required. For edits in the review table, the reason SHALL be entered in the row's detail and SHALL be recorded with the next change saved on that row, after which the reason field is cleared.

#### Scenario: Edit with reason
- **WHEN** a reviewer enters a reason in an impact's row detail and then changes its mechanism
- **THEN** the reason is recorded with that change in the audit trail and the reason field is empty again

#### Scenario: Edit without reason
- **WHEN** a reviewer edits an impact without entering a reason
- **THEN** the edit is saved

### Requirement: Reviewer can add impacts
A reviewer SHALL be able to create an impact on a paper from a new-impact page, with its own address, showing the paper beside a panel of the impact's fields, by selecting its evidence in the paper text and filling in its fields. Such impacts SHALL have origin `human`, no AI snapshot, and be treated as verified.

#### Scenario: Add impact from highlighted text
- **WHEN** a reviewer chooses to add an impact on a paper, highlights a passage on the new-impact page, fills in the fields and saves
- **THEN** a new active impact with origin `human` exists on that paper with the highlighted passage as its evidence, and the analysis page is shown with its row highlighted

#### Scenario: Incomplete impact cannot be saved
- **WHEN** a reviewer tries to save a new impact with no evidence selected or no mechanism or category
- **THEN** the impact cannot be saved

## ADDED Requirements

### Requirement: Impact fields are edited in the review table
A reviewer SHALL edit category, reversibility, mechanism, confidence and impacted species in the impact's cells of the review table, and alien species and justification in the row's expandable detail. Each change SHALL be saved when made, without a confirmation step, except that a change to MR or MV SHALL be saved once its reversibility is chosen. The UI SHALL NOT edit impact fields in a popup.

#### Scenario: Change category in the table
- **WHEN** a reviewer picks MO in the category cell of an impact whose category is MN
- **THEN** the impact is saved with category MO and verified, and the row shows MO

#### Scenario: Edit justification in the row detail
- **WHEN** a reviewer expands an impact's row and changes its justification
- **THEN** the impact is saved with the new justification

#### Scenario: Edit fails
- **WHEN** the API rejects a change made in the table
- **THEN** the cell shows its previous value and the reviewer sees the error

### Requirement: Categories are offered in severity order
Every category selector SHALL list the EICAT categories from most to least severe, MV, MR, MO, MN, MC, followed by DD, each shown with its code and full name.

#### Scenario: Category choices
- **WHEN** a reviewer opens a category selector
- **THEN** the choices are, in order, "MV – Massive", "MR – Major", "MO – Moderate", "MN – Minor", "MC – Minimal Concern" and "DD – Data Deficient"

### Requirement: Review table reads as a compact table
The review table SHALL use fixed column widths that give the evidence column the width left after narrow columns for verified, category, mechanism, impacted species, confidence, origin and actions. Each row SHALL show its evidence clamped to three lines and keep other cells to one line where they fit.

#### Scenario: Long evidence
- **WHEN** an impact's evidence is longer than three lines at the column's width
- **THEN** the cell shows three lines ending in an ellipsis, and clicking it opens the impact's evidence page

#### Scenario: Evidence status
- **WHEN** an impact has an approximate or unanchored span
- **THEN** its evidence cell shows an icon whose tooltip explains the status, rather than a banner

#### Scenario: Origin and changes from AI
- **WHEN** a reviewer has changed a field of an AI impact
- **THEN** the impact's origin cell shows that it is an AI impact changed by a reviewer, with no separate "changed from AI" chip

#### Scenario: Row actions
- **WHEN** a reviewer opens an active impact's actions
- **THEN** remove and history are offered in a menu on the row

### Requirement: Papers and their impacts are listed together
The analysis page SHALL list every paper of the analysis in one section per paper, including papers not yet run and papers with no impacts. Each paper's section SHALL hold its impacts table with its Removed and Suppressed sections, and actions to add an impact on that paper and to remove the paper from the analysis.

#### Scenario: Paper not yet run
- **WHEN** a paper has been added to an analysis but not run
- **THEN** its section is listed and says it has not been run

#### Scenario: Remove a paper from its section
- **WHEN** a reviewer chooses to remove a paper from its section
- **THEN** the paper and its section leave the analysis page
