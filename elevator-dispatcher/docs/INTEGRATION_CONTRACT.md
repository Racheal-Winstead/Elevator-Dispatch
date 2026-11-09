# Local data adapter contract — November 8, 2026

Racheal’s console now uses an unmodified local snapshot of Deshawn’s engine at commit `6aff6485ae97a8166beaf15678fa3bbf3f0edbb3` from [Racheal-Winstead/Elevator-Dispatch](https://github.com/Racheal-Winstead/Elevator-Dispatch). This is a tested local compatibility layer. Deshawn’s repository, app, messaging and audit implementation were not modified. Shared SQLite adoption and the team merge are still pending agreement.

## Entry point and ownership

```python
from integrations.deshawn_adapter import recommend
proposals, exceptions = recommend(tickets, roster, rules, windows, assignments)
```

Racheal retains app.py, roster.py, local model/validator/state integration and QA. The upstream engine source stays unchanged under `integrations/vendor/deshawn_engine.py`; `SOURCE.json` records repository, commit, path, Git blob SHA and SHA-256. Scheduling uses a fresh private module instance for each request. Configuration changes affect that instance only.

The adapter returns immutable Proposal objects and `{ticket_id: [reason_code, ...]}`. It never writes SQLite, changes status, dispatches a message or imports external data. The UI previews each complete crew; the dispatcher reviews and confirms; SQLite validates again inside its transaction before storing.

## Field mappings

| Local data | Engine data | Treatment |
|---|---|---|
| ticket_id / source_record_id | same | Preserved exactly; numeric work-order screen labels remain display-only |
| created_at | reported_at | Aware timestamp → UTC → engine naive UTC representation |
| sector | borough | Current local sector values are demo boroughs; actual sector modeling remains pending |
| building | building and development | Local model has no separate development; duplicated for synthetic demo only |
| asset | elevator_asset_id | Preserved |
| priority | source_priority | Integer 1–5 → string |
| critical | no_service | Explicit synthetic critical-impact mapping, not an inference about actual NYCHA service |
| hazard_review | no equivalent confirmation | Ticket is withheld before scheduling; never becomes hazard_confirmed=Y |
| MECHANIC / HELPER | Mechanic / Helper | Explicit reversible role map |
| CORRECTIVE | Elevator outage | Demo mapping; matching role requirements required |
| INSPECTION | Planned maintenance | Demo-only category mapping; preserves one-mechanic requirement, not official taxonomy |
| Native engine work-type names | unchanged | Allowed when local rules specify the same required roles |
| Local window | Private LOCAL-n slot | Minute-resolution UTC clocks on that request’s dated context |
| Existing crew commitments | group_id, slot, role→ID dictionary | Every actual overlap is represented as occupied in the current trial slot |
| Returned group | Proposal | Crew IDs, dated UTC start/end, local rule version and engine provenance |

Unknown work types, unrepresentable role counts and changed crew-role requirements are rejected with explicit reason codes. Duplicated ticket or staff IDs are rejected at this boundary; retaining conflicting raw import records remains an ingestion task. Windows must be aware, positive, minute-aligned and start/end within one UTC date. Unsupported or malformed times return no plan rather than guessing a conversion.

## Safety order

1. Check ticket completeness and review holds.
2. Check the local role configuration matches the engine’s crew requirements.
3. Order normalized tickets using the pinned engine’s deterministic policy.
4. For each trial window, prefilter staff using local attendance, active status, full shift coverage, exact qualification set, verification status, certification expiry at the end of work, borough and depot authorization.
5. Convert every existing or proposed overlapping commitment into engine occupancy. This protects against the upstream slot-name-only collision assumption.
6. Call the actual engine scheduler with eligible staff and the converted board.
7. Convert its complete group back; run the shared local validator against the shadow board. Invalid output cannot become a proposal.
8. Show the proposal. On confirmation, validate again against the current roster and stored board in the SQLite transaction. Commit the crew, status event and assignment event together or roll all writes back.

The prefilter deliberately compensates for the reviewed upstream gap that can accept PRESENT staff with UNVERIFIED certification. It does not claim that Deshawn’s source was fixed. New engine versions require renewed compatibility and regression testing.

## State and provenance

Assignments now save `scheduler_source`, `engine_rule_version` and `engine_commit` alongside existing IDs, windows, group ID and local rule version. Report exports include those provenance fields. Manual UI proposals use MANUAL; old stored rows without new fields remain readable with blank provenance.

Window comparisons parse endpoints and normalize to UTC before comparing real instants. Committed timestamps are stored as UTC ISO values. UNKNOWN attendance remains unavailable. Naive/malformed windows fail closed. A status-only change cannot mark committed work UNASSIGNED; complete-crew removal is required. That check and the update share one transaction.

Source refresh does not clear audit, assignments or progress. No backend source picker was added. Runtime conversion/snapshot errors return explicit reasons and no plan; there is no silent return to the original fixture scheduler.

## Remaining integration work

Agree whether the team adopts this adapter and SQLite; resolve approved source fields, actual development/sector/depot model, qualifications, rule ownership, external commitments and operational procedures. Ingestion/fallback, messaging, source-switch migration and complete PRD delivery are not included in this update. The old merge-readiness report remains a historical upstream/local review; its two local defects are now fixed here, while its observations about the unchanged upstream version still stand.
