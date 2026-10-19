# analysis-reruns Specification

## Purpose

Defines what happens to an analysis's existing impacts when the pipeline runs again, so expert decisions survive re-runs and nothing the AI produced is lost.

## Requirements

### Requirement: Runs are recorded
Each run SHALL cover one paper of an analysis and SHALL be recorded with a run id, the paper id, its state (queued, running, completed, failed or cancelled), the time it was queued, start and completion times, the model used, its token usage and, for a failed run, its error.

#### Scenario: Completed run
- **WHEN** a run finishes
- **THEN** the analysis lists that run with its id, paper id, state completed, queued, start and completion times, model and usage

#### Scenario: Failed run
- **WHEN** extraction fails for a paper
- **THEN** that paper's run is recorded as failed with the error

### Requirement: Raw AI results remain available
After a run of a paper completes, the analysis's `results` entry for that paper SHALL hold the AI's raw impacts from that run, in the same shape as before, unaffected by review actions. The entries of other papers SHALL NOT change.

#### Scenario: Eval harness reads results
- **WHEN** a client reads `results[paper_id]` after a run of that paper completes
- **THEN** it receives the list of impacts the AI extracted for that paper in that run

#### Scenario: Running one paper keeps the others' results
- **WHEN** a run of paper A completes on an analysis whose paper B was run earlier
- **THEN** `results` holds A's new impacts and B's impacts from its earlier run

#### Scenario: Review does not change results
- **WHEN** a reviewer edits or removes an impact
- **THEN** `results` is unchanged

### Requirement: Re-run supersedes unverified AI impacts
When a run of a paper completes, every active, unverified AI impact of that paper SHALL be marked superseded. Superseded impacts SHALL be retained but not shown in the review view. Impacts of other papers SHALL NOT change.

#### Scenario: Unverified impact replaced
- **WHEN** a paper with an active unverified AI impact is re-run
- **THEN** that impact is superseded and the new run's impacts are shown instead

#### Scenario: Other papers untouched
- **WHEN** paper A is re-run on an analysis where paper B has active unverified AI impacts
- **THEN** paper B's impacts are unchanged

### Requirement: Re-run over verified impacts requires an explicit choice
When any of the papers a request would queue has active verified AI impacts, the run endpoint SHALL refuse with HTTP 409 unless the request states whether to keep or discard them. Papers already queued or running SHALL NOT count toward this check or the counts returned. The choice SHALL be stored with each run it queues.

#### Scenario: Run without a choice
- **WHEN** a client asks to run papers that have verified AI impacts and gives no keep/discard choice
- **THEN** the API responds 409 with the total number of verified and unverified AI impacts of the papers it would queue, and no run is queued

#### Scenario: Keep verified impacts
- **WHEN** a client asks to run a paper choosing keep
- **THEN** when that run completes, the paper's verified AI impacts stay active and verified

#### Scenario: Discard verified impacts
- **WHEN** a client asks to run a paper choosing discard
- **THEN** when that run completes, the paper's verified AI impacts are superseded along with unverified ones

#### Scenario: No verified impacts
- **WHEN** a client asks to run papers none of which has verified AI impacts
- **THEN** the runs are queued without requiring a choice

#### Scenario: Other papers' verified impacts
- **WHEN** a client asks to run paper A, which has no verified AI impacts, on an analysis where paper B has verified AI impacts
- **THEN** A's run is queued without requiring a choice

#### Scenario: Already queued paper not counted
- **WHEN** a client asks to run all papers while paper A, which has verified AI impacts, is queued, and no other paper has verified AI impacts
- **THEN** the other papers are queued without requiring a choice and A's queued run keeps its stored choice

### Requirement: Human-created and removed impacts survive every re-run
Re-runs SHALL NOT change the state of human-created impacts or removed impacts, whatever keep/discard choice is made.

#### Scenario: Discard keeps human-created impacts
- **WHEN** a client requests a run choosing discard
- **THEN** human-created impacts remain active and removed impacts remain removed

### Requirement: UI confirms a re-run
Before queuing runs of papers that have impacts, the UI SHALL show how many of those papers' AI impacts will be kept and how many replaced, and SHALL require a second confirmation before discarding verified impacts.

#### Scenario: Confirm re-run keeping verified impacts
- **WHEN** a reviewer clicks Re-run on a paper with 3 verified and 7 unverified AI impacts
- **THEN** a dialog states that 3 verified impacts will be kept and 7 unverified impacts replaced, with options to proceed or cancel

#### Scenario: Confirm Run all
- **WHEN** a reviewer clicks Run all on an analysis whose papers have 5 verified and 9 unverified AI impacts in total
- **THEN** the dialog states those totals and one choice applies to every paper queued

#### Scenario: Discard verified impacts
- **WHEN** a reviewer chooses to discard verified impacts in that dialog
- **THEN** a second confirmation is shown before the runs are queued

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

### Requirement: Paper runs are queued and processed one at a time
Asking to run papers SHALL queue one run per paper. Each analysis SHALL process its queued runs one at a time, in the order queued. Asking to run a paper that is already queued or running SHALL NOT queue it again.

#### Scenario: Run all
- **WHEN** a reviewer runs all papers of an analysis with three papers, none queued or running
- **THEN** three runs are queued, the first starts, and each of the others starts only after the one before it finishes

#### Scenario: Run a paper while another runs
- **WHEN** a reviewer runs paper B while paper A of the same analysis is running
- **THEN** B's run is queued and starts after A's finishes

#### Scenario: Paper already queued
- **WHEN** a reviewer runs all papers while paper A is queued
- **THEN** A keeps its one queued run and only the other papers are queued

### Requirement: A failed run does not stop the queue
When a paper's run fails, the next queued run of the analysis SHALL start, and the failed paper's impacts SHALL be left as they were before the run.

#### Scenario: Middle paper fails
- **WHEN** three papers are queued and the second one's extraction fails
- **THEN** the second run is recorded as failed with its impacts unchanged, and the third run starts

### Requirement: Queued runs can be cancelled
A reviewer SHALL be able to cancel a queued run. A cancelled run SHALL be recorded as cancelled and SHALL NOT start, and the paper's impacts SHALL be unchanged.

#### Scenario: Cancel a queued paper
- **WHEN** a reviewer cancels paper B's queued run
- **THEN** B's run is recorded as cancelled, B's impacts are unchanged, and the next queued run starts in its turn

### Requirement: Removing a paper cancels its run
Removing a paper from an analysis SHALL cancel its queued run, or stop its running run and record it as cancelled without changing its impacts.

#### Scenario: Remove a running paper
- **WHEN** a reviewer removes paper A from an analysis while A is running
- **THEN** A's run is recorded as cancelled, its impacts are unchanged, and the next queued run starts

### Requirement: Queued runs survive an API restart
The queue SHALL be stored with the analysis. When the API starts, queued runs SHALL remain queued and be processed, and any run recorded as running SHALL be marked failed with an error saying it was interrupted, leaving its paper's impacts unchanged.

#### Scenario: Restart during a run
- **WHEN** the API restarts while paper A is running and paper B is queued
- **THEN** A's run is failed as interrupted, A's impacts are unchanged, and B's run starts

### Requirement: Each paper shows its run state
For each paper of an analysis, the system SHALL report its run state, which is that of its latest run that was not cancelled, or not run when it has none, with the time it last completed a run. The analysis status SHALL be derived from the run states of its current papers: running while any is queued or running, failed when any is failed, completed when any is completed, and pending otherwise.

#### Scenario: Mixed paper states
- **WHEN** an analysis has one paper completed, one running and one not run
- **THEN** each paper reports that state and the analysis status is running

#### Scenario: Failed paper
- **WHEN** no paper of an analysis is queued or running and one paper's latest run failed
- **THEN** the analysis status is failed and that paper reports failed with its error

#### Scenario: Cancelled run
- **WHEN** a paper that completed a run earlier has its next run cancelled
- **THEN** the paper reports completed with the time of that earlier run

#### Scenario: Nothing completed
- **WHEN** no paper of an analysis has a run that was not cancelled
- **THEN** every paper reports not run and the analysis status is pending
