## ADDED Requirements

### Requirement: A paper is locked from review while queued or running
While a paper has a queued or running run, the system SHALL refuse review actions on that paper's impacts, including adding an impact on it, and the UI SHALL show that paper's impacts read-only. Review of the analysis's other papers SHALL remain available.

#### Scenario: Review a queued paper
- **WHEN** a reviewer tries to verify an impact of a paper whose run is queued
- **THEN** the API rejects the action and the impact is unchanged

#### Scenario: Review another paper during a run
- **WHEN** paper A is running and a reviewer edits an impact of paper B of the same analysis
- **THEN** the edit is saved

#### Scenario: Cancelling unlocks
- **WHEN** a reviewer cancels a paper's queued run
- **THEN** that paper's impacts can be reviewed again

### Requirement: Papers are run from their section
Each paper's section on the analysis page SHALL show the paper's run state and when it last completed a run, and SHALL offer Cancel for a queued run and, for a paper that is not queued or running, Re-run if it has completed a run and Run otherwise. The page header SHALL offer Run all.

#### Scenario: Queued paper
- **WHEN** a paper's run is queued
- **THEN** its section shows it as queued with a Cancel action and its impacts read-only

#### Scenario: Run state updates
- **WHEN** a paper's run moves from queued to running to completed
- **THEN** its section shows each state without the reviewer reloading the page, and then shows the new impacts
