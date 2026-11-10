# Learn the dispatcher workbench

## Your story for the panel

“I own the roster and dispatcher experience: helping a person see who is available, understand a proposed crew, record their decision, and leave the next shift clear follow-up. I also test the failure cases. The data is synthetic, and a local adapter now connects my console to a pinned copy of Deshawn’s scheduling engine. Shared storage and the team merge remain separate decisions.”

This is decision support in a local demonstration. It neither sends a crew into the field nor updates the official work-order system.

## Follow one work order

1. `demo_adapter/fixtures.py` creates fictional tickets. Each ticket has an internal ID such as ED-001. The queue also presents a fictional numeric work-order reference; that number is not a real Maximo identifier.
2. `models.py` defines the shared shapes: Ticket, Technician, CrewRule and Proposal. The dataclasses make required fields explicit instead of passing anonymous lists around.
3. `roster.py` creates staff, authorized boroughs/depots, attendance, shifts and required crew roles. Internally, `sector` and `sectors` currently hold borough names; that is a demo shortcut to resolve with Deshawn.
4. `validators.py` returns reason codes when an input fails. UNKNOWN attendance does not become PRESENT. A helper outside the authorized area does not become eligible because another helper is absent.
5. `integrations/deshawn_adapter.py` maps our fields and roles to Deshawn’s format, asks his pinned engine for recommendations, and converts the result back into our Proposal model. It filters exact local eligibility first, maps existing overlapping commitments into each trial slot, and validates the returned crew. Its shadow board reserves proposed capacity without writing assignments.
6. `app.py` displays the proposal. The dispatcher reviews it, checks confirmation and provides a reason. `Store.commit` checks the current committed board again, inside a database transaction.
7. `state/audit.py` saves the whole crew with one atomic group ID and a status event, or rolls everything back. A proposal shown earlier can be rejected if the board changes before confirmation.
8. The dispatcher enters progress, responsible owner and next action. The report combines the same ticket, assignment and progress records into a CSV handover.

## Component ownership

| Component | Owner / boundary |
|---|---|
| roster.py, app.py, work_queue.py, display_time.py | Racheal’s local demo workstream |
| tests/ | Racheal QA now; joint acceptance with Deshawn later |
| models.py, validators.py, state/audit.py | Proposed joint contract, not a unilateral production schema |
| demo_adapter/ | Synthetic data plus the original scheduler retained for comparison; the old scheduler is no longer the app backend |
| integrations/deshawn_adapter.py | Local field/role/time conversions and protective validation |
| integrations/vendor/ | Unmodified upstream engine snapshot and exact source manifest |
| ingest.py, triage.py, engine.py | Deshawn’s ownership; snapshot scheduling functions are used locally; no upstream files were edited |

## Python and Streamlit concepts, with meaning

**Import:** `from roster import demo_roster` makes a function available to another file. Keeping responsibilities in separate files makes a roster change easier to review without rewriting the UI.

**Function:** `eligible(...)` takes facts and returns exclusion reasons. A pure decision function is easier to test than a button that directly changes a database.

**Dataclass:** `Technician` names the role, attendance and authorization fields. `frozen=True` discourages accidental mutation; `replace(person, attendance='ABSENT')` makes a new version.

**Tuple and list:** authorized boroughs and required roles are tuples. The roster is a list of technicians. A list comprehension builds a display table or filters a set of candidates.

**Dictionary:** rules map work types to requirements. Exception dictionaries map a ticket ID to its reason codes. Matching by ID is safer than matching by a screen row position.

**Set and Counter:** sets compare qualification membership; Counter checks the exact number of required crew roles. Two mechanics cannot satisfy a mechanic-plus-helper requirement.

**Datetime:** UTC is stored consistently; `display_time.py` displays New York time with daylight-saving-aware conversion. A displayed shift is a demo window, not evidence that a person is working now.

**Streamlit rerun:** changing a widget reruns the Python script. `st.session_state` retains browser-session selections and attendance. SQLite retains committed records across restarts. These solve different problems.

**Form:** groups related inputs so the program processes them on submission. The confirmation checkbox prevents an unreviewed click from saving a proposed assignment.

**Transaction:** BEGIN IMMEDIATE protects validation and writing as one operation. COMMIT completes it. ROLLBACK restores the previous database if any validation or event write fails.

**Audit event:** records actor, time, old/new values and reason. The responsible owner of a follow-up is separate from the dispatcher who recorded it. The log is not production tamper-proof auditing.

**CSV:** a portable table for handover. All nonempty reports share consistent columns. Formula-like cell text is prefixed so opening exported text in a spreadsheet is less likely to execute it as a formula.

## Explain the screens

| Screen | What to show | What to say |
|---|---|---|
| Crew readiness | Present, absent and unknown people; float helper | “Each person has explicit checks. Individual readiness still needs a complete crew and valid ticket.” |
| Work queue | Search, borough filter, incomplete record, hazard-review record | “We retain questionable work for review instead of silently discarding it.” |
| Dispatch plan | Proposed crew, window, reason and confirmation | “This is a recommendation until the dispatcher commits the whole crew.” |
| Progress | Owner, blocker, next action, RESTORED versus CLOSED | “These are dispatcher-entered updates, not live field telemetry.” |
| Shift handover | Open-work CSV and history | “The next shift can see what remains and who is responsible.” |

## Practice exercises

1. Find ED-002. Explain why a report mentioning “stuck” is held for review without declaring an emergency.
2. Find T06. Predict what UNKNOWN attendance does before reading the screen explanation.
3. Try a manual crew containing only T01. It must fail and leave the board unchanged.
4. Commit a valid pair, then propose the same pair on a different ticket in the same window. Explain the collision result.
5. Enter BLOCKED without a blocker. Explain why the save fails. Then supply owner, next action and blocker.
6. Record RESTORED, then CLOSED as distinct events. State that these do not close a Maximo order.
7. Export handover, locate a ticket and reconcile its crew/status/owner with the screen.
8. Confirm reset. Show that crew assignments disappear while history remains.

## Questions the panel may ask

**Why not schedule everyone?** Capacity, attendance, qualification, location and ticket holds restrict eligibility. Leaving a reason-coded exception is useful behavior.

**Is this NYCHA policy?** No. Crew requirements, taxonomy and timing are illustrative. The responsible operational stakeholders must approve production rules.

**How do you know it works?** The automated suite exercises negative cases, rollback, determinism, status ownership, display time and queue behavior. Streamlit interaction checks and a browser visual review complement those tests. Passing tests does not establish live operational suitability.

**What comes next?** Review the tested local adapter with Deshawn, agree shared storage, integrate approved data and external commitments, validate operations rules and finish the full P0 release gate. The supplied PRD’s research references still require source verification; the supplied original JD is now preserved in sources/NYCHA_ELEVATOR_DISPATCHER_647208.txt; its original URL remains unavailable.

## Why we added a translator

Our `MECHANIC` becomes his `Mechanic`; our `sector` (currently a demo borough) becomes his `borough`; our `priority` becomes his `source_priority`. IDs stay unchanged. CORRECTIVE maps to Elevator outage; INSPECTION maps to Planned maintenance as an explicit demo-only mapping with matching crew roles. The adapter rejects unsupported mappings rather than guessing. It uses UTC clock values on a private engine instance and maps actual overlaps into each trial slot. The database still owns the final decision, with fresh validation inside its transaction.

The two local bugs are fixed: all interval comparisons use timezone-aware UTC instants, and UNASSIGNED requires complete-crew removal. Saving a status alone cannot free a crew.

## Explain the role using its actual JD

Job ID 647208 names dispatching teams, recording elevator/crew activity, Maximo data entry/reporting, data accuracy and equipment maintenance. Our strongest demonstrated connection is coordination and data accuracy, plus selected work-activity records. Maximo integration and equipment maintenance are not implemented. See [JD_ALIGNMENT.md](JD_ALIGNMENT.md) for the complete mapping and the distinction between explicit duties and design inferences.
