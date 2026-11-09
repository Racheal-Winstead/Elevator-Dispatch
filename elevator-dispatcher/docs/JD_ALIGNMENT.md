# Connect the workbench to the dispatcher’s job

Source: the [NYCHA Elevator Dispatcher posting, Job ID 647208](sources/NYCHA_ELEVATOR_DISPATCHER_647208.txt), supplied by Racheal on November 9, 2026. The vacancy is marked expired and its posted-until field is 09/12/2024. Its original URL has not been supplied; the text is preserved without claiming independent website verification. This source is distinct from the proposed PRD.

## Product statement

We help an elevator dispatcher coordinate crews and maintain clear, accurate work records while keeping assignment decisions under human control.

## Six duties, with honest coverage

| JD duty | Implemented demonstration | Where / evidence | Boundary |
|---|---|---|---|
| 1. Dispatch elevator teams as required | Inspect available people, review an explained complete-crew proposal, confirm or reject it, remove/reassign through validation | app.py, roster.py, integrations/deshawn_adapter.py; adapter and Streamlit interaction tests | A local assignment record is not an actual dispatch or field notification. Crew composition and eligibility remain configured demo rules. |
| 2. Record elevator performance and mechanic/helper activities | Record dispatcher-entered progress, owner, blocker, next action and timestamped activity associated with a ticket/crew | state/audit.py, Progress & exceptions, handover export; progress/ownership/persistence tests | Covers selected work-activity records. No authoritative elevator-performance history, uptime, outage trend or field telemetry is implemented. |
| 3. Perform Maximo work-order data entry | Structured ticket and progress records demonstrate preparation and review of information | models.py, queue, status form, shared validators | Maximo access, data entry, schema verification, reconciliation and write-back are not implemented. The engine uses local synthetic inputs. |
| 4. Print elevator reports from Maximo as needed | Export assignment, open-work, exception and handover CSV tables | state/audit.py report/csv_export; report/export tests | CSV files are local demonstration reports, not official Maximo reports. No Maximo retrieval or print integration is implemented. |
| 5. Ensure accuracy of computer data | Retain invalid work for review; block unknown attendance, partial crews, unverified qualification and actual overlap; record decisions transactionally | validators.py, time_windows.py, state/audit.py; negative, rollback and stale-preview tests | Protects defined local invariants. Does not verify the factual truth of synthetic/source records or establish production data quality. |
| 6. Maintain terminals and related equipment | No feature in this slice | Explicitly out of scope | Software UI does not demonstrate hardware maintenance, troubleshooting, repairs or equipment support. |

The strongest demonstrated alignment is with duties 1 and 5, plus the activity-recording portion of duty 2. Duties 3 and 4 motivate future approved integration, not claims of current Maximo capability.

## Connect with the person doing the work

The JD explicitly values coordinating simultaneous tasks, interpersonal communication and accurate typing/data entry. It explicitly includes nights and weekends and describes the role as entry-level with no formal education or experience requirement. That requirement applies to this dispatcher role; it does not waive mechanic/helper qualifications or establish a staffing policy.

A useful design inference is that the screen should help someone regain context after an interruption: which ticket is selected, whether it needs review, who can take it, what has been decided, and what happens next. Plain labels, visible reasons, deliberate confirmation and a next-action handover support that inference. The JD does not itself establish current workload, stress levels, digital literacy or dispatch procedures, and we have not interviewed a dispatcher.

### A fictional walkthrough, not an observed interview

A dispatcher starts a shift, reviews a reported outage and finds missing building information. They retain it for follow-up rather than scheduling against incomplete data. For a different complete ticket, they inspect attendance, see an unknown helper excluded, review an eligible pair, and confirm the assignment. Later they record a blocker and responsible owner, then export open work for the next shift.

This story connects the demonstrated screens to coordination and recordkeeping. It does not establish a real NYCHA operating procedure.

## Questions worth validating with someone in the role

- What interrupts your work most often, and what do you need to see when returning to a ticket?
- Which information must be verified before assigning a team, and where is that information authoritative?
- Which fields and reports do you enter or retrieve from Maximo each shift?
- How do you distinguish service restoration from administrative work-order closure?
- What must the next shift receive, and who must acknowledge unresolved work?
- What changes on nights/weekends, including staffing, communication and supervisor availability?

## Presentation language

Say: “This demo supports crew coordination and accurate activity records. We preserve review holds, require confirmation and leave unresolved work with a next action.”

Say: “The JD names Maximo entry and reports. We demonstrate structured local records and CSV handover, while approved Maximo integration is future work.”

Do not claim measured administrative time savings, faster repairs, official staffing rules, live dispatch or complete fulfillment of all six duties. Describe the local test results as software evidence, not validation by NYCHA.
