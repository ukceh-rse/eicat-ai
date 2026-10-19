# analysis-reruns Specification

## Purpose

Defines what happens to an analysis's existing impacts when the pipeline runs again, so expert decisions survive re-runs and nothing the AI produced is lost.

## Requirements

### Requirement: Runs are recorded
Each run of an analysis SHALL be recorded with a run id, start and completion times, the model used and its token usage.

#### Scenario: Completed run
- **WHEN** a run finishes
- **THEN** the analysis lists that run with its id, start time, completion time, model and usage

### Requirement: Raw AI results remain available
After each run, the analysis's `results` field SHALL hold the AI's raw impacts for that run per paper, in the same shape as before this change, unaffected by review actions.

#### Scenario: Eval harness reads results
- **WHEN** a client reads `results[paper_id]` after a run completes
- **THEN** it receives the list of impacts the AI extracted for that paper in that run

#### Scenario: Review does not change results
- **WHEN** a reviewer edits or removes an impact
- **THEN** `results` is unchanged

### Requirement: Re-run supersedes unverified AI impacts
On a re-run, every active, unverified AI impact SHALL be marked superseded. Superseded impacts SHALL be retained but not shown in the review view.

#### Scenario: Unverified impact replaced
- **WHEN** an analysis with an active unverified AI impact is re-run
- **THEN** that impact is superseded and the new run's impacts are shown instead

### Requirement: Re-run over verified impacts requires an explicit choice
When an analysis has active verified AI impacts, the run endpoint SHALL refuse with HTTP 409 unless the request states whether to keep or discard them.

#### Scenario: Run without a choice
- **WHEN** a client requests a run on an analysis with verified AI impacts and gives no keep/discard choice
- **THEN** the API responds 409 with the number of verified and unverified impacts, and no run starts

#### Scenario: Keep verified impacts
- **WHEN** a client requests a run choosing keep
- **THEN** verified AI impacts stay active and verified

#### Scenario: Discard verified impacts
- **WHEN** a client requests a run choosing discard
- **THEN** verified AI impacts are superseded along with unverified ones

#### Scenario: No verified impacts
- **WHEN** a client requests a run on an analysis with no verified AI impacts
- **THEN** the run starts without requiring a choice

### Requirement: Human-created and removed impacts survive every re-run
Re-runs SHALL NOT change the state of human-created impacts or removed impacts, whatever keep/discard choice is made.

#### Scenario: Discard keeps human-created impacts
- **WHEN** a client requests a run choosing discard
- **THEN** human-created impacts remain active and removed impacts remain removed

### Requirement: UI confirms a re-run
Before re-running an analysis that has impacts, the UI SHALL show how many impacts will be kept and how many replaced, and SHALL require a second confirmation before discarding verified impacts.

#### Scenario: Confirm re-run keeping verified impacts
- **WHEN** a reviewer clicks Run on an analysis with 3 verified and 7 unverified AI impacts
- **THEN** a dialog states that 3 verified impacts will be kept and 7 unverified impacts replaced, with options to proceed or cancel

#### Scenario: Discard verified impacts
- **WHEN** a reviewer chooses to discard verified impacts in that dialog
- **THEN** a second confirmation is shown before the run starts

### Requirement: Expert decisions hold their impact key
An impact's key SHALL be its paper and current mechanism. A key SHALL be held by any impact that is active and verified, active and human-created, or removed.

#### Scenario: Mechanism change moves the key
- **WHEN** a reviewer changes a verified impact's mechanism from Predation to Competition
- **THEN** that impact holds the Competition key for its paper and no longer holds the Predation key

### Requirement: New AI impacts with a held key are suppressed
A new AI impact whose key is held SHALL NOT become active. It SHALL be stored as a suppressed impact that references the impact holding the key.

#### Scenario: Re-run finds a verified impact again
- **WHEN** a re-run extracts a Predation impact for a paper that already has a verified Predation impact
- **THEN** no new active Predation impact appears and a suppressed impact records the new extraction

#### Scenario: Re-run finds a removed impact again
- **WHEN** a re-run extracts a Predation impact for a paper whose Predation impact a reviewer removed
- **THEN** no new active Predation impact appears and a suppressed impact records the new extraction

#### Scenario: Unheld key
- **WHEN** a re-run extracts a Competition impact for a paper with no impact holding the Competition key
- **THEN** the impact is added as an active, unverified AI impact

### Requirement: Suppressed impacts accumulate sightings
Each paper and mechanism SHALL have at most one suppressed impact. Each time a run suppresses an AI impact with that key, the system SHALL append a sighting holding the run id, time, and full snapshot of the AI's impact and evidence.

#### Scenario: Suppressed on two runs
- **WHEN** two successive runs both extract a suppressed Predation impact for the same paper
- **THEN** there is one suppressed Predation impact for that paper with two sightings, each holding that run's AI values

### Requirement: Suppressed impacts can be viewed and restored
A reviewer SHALL be able to view each suppressed impact's sightings and the impact holding its key, and to restore it. Restoring SHALL make it an active, verified AI impact with the values of its latest sighting.

#### Scenario: Restore an accidentally overridden impact
- **WHEN** a reviewer restores a suppressed impact
- **THEN** it becomes active and verified with the latest sighting's values, and the impact holding the key is unchanged

#### Scenario: Restore creates a same-mechanism pair
- **WHEN** a reviewer restores a suppressed Predation impact while a verified Predation impact is active on the same paper
- **THEN** both impacts are active
