# review-audit-trail Specification

## Purpose

Records every review and run action on an analysis — when it happened, who or what did it, and exactly what changed — so expert decisions and AI output can be audited later.

## Requirements

### Requirement: Every state change is logged
The system SHALL append an audit event for every impact creation, field edit, evidence change, verify, unverify, remove, restore, supersede, suppression, sighting, run start and run completion.

#### Scenario: Edit logged
- **WHEN** a reviewer edits an impact
- **THEN** an audit event of action `updated` is recorded for that impact

#### Scenario: Run logged
- **WHEN** a run starts and completes
- **THEN** audit events `run_started` and `run_completed` are recorded with the run id

### Requirement: Events record time, actor and target
Each audit event SHALL record a UTC timestamp, the analysis id, the impact id and run id where relevant, and an actor with a kind of `human`, `ai` or `system` and a user id that is null until user accounts exist.

#### Scenario: Human action actor
- **WHEN** a reviewer removes an impact
- **THEN** the event's actor kind is `human` and its user id is null

#### Scenario: Run-driven action actor
- **WHEN** a run supersedes an unverified impact
- **THEN** the event's actor kind is `system`

#### Scenario: AI extraction actor
- **WHEN** a run creates an AI impact
- **THEN** the creation event's actor kind is `ai`

### Requirement: Field changes record old and new values
An event that changes impact values SHALL list each changed field with its old and new value. Evidence changes SHALL record the old and new spans.

#### Scenario: Category change
- **WHEN** a reviewer changes category from MO to MR
- **THEN** the event lists field `category` with old `MO` and new `MR`

#### Scenario: Automatic verification is distinguishable
- **WHEN** an edit verifies a previously unverified impact
- **THEN** the log contains the `updated` event and a separate `verified` event, so the log shows that verification came from the edit

### Requirement: Reasons are recorded
When a reviewer gives a reason for an action, the event SHALL store it.

#### Scenario: Removal with reason
- **WHEN** a reviewer removes an impact giving the reason "not caused by the alien species"
- **THEN** the removal event's note is "not caused by the alien species"

### Requirement: Audit events are immutable
Audit events SHALL NOT be modified or deleted through the API, and SHALL be kept when the analysis they belong to is deleted.

#### Scenario: Analysis deleted
- **WHEN** an analysis is deleted
- **THEN** its audit events can still be retrieved by analysis id

### Requirement: Audit trail can be queried
The API SHALL return an analysis's audit events in time order, optionally filtered to one impact.

#### Scenario: Impact history
- **WHEN** a client requests the audit events for one impact
- **THEN** it receives only that impact's events, oldest first

### Requirement: Impact history is shown in the UI
The UI SHALL show an impact's history — each event's time, actor kind, action, field changes and reason — from the impact's row.

#### Scenario: Open history
- **WHEN** a reviewer opens the history of an impact that was created by AI and later edited
- **THEN** the history lists the AI creation event followed by the edit with its old and new values
