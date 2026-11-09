# PRD requirements and acceptance mapping

This is an explicitly bounded demonstration slice. It does **not** satisfy the full PRD release gate. The full supplied PRD was read; its cited research and JD claims are not independently verified here.

| Journey | Implemented in this slice | Remaining before full P0 |
|---|---|---|
| Review intake | Bounded seed load, source disclosure, freshness display, missing-data hold, related-asset view, searchable/filtered queue | Deshawn ingestion; network error/retry/fallback; complete canonical source fields; duplicate-ID quarantine; approved taxonomy; human hazard correction; richer priority/age/asset filters |
| Review roster | 10 fictional people, attendance, active flag, shifts, demo borough/depot authorization, qualification label, configurable roles, float helper | Approved feed, expiry display in roster UI, persisted attendance, actual sector model, authoritative external commitments |
| Assign crew | Pinned-engine preview through tested local adapter; exact roles; shared validator; atomic commit/replacement/removal; no automatic preemption | Team merge/shared-storage agreement; richer change-impact preview; approved crew/qualification rules; production authorization |
| Follow progress | Listed MVP status vocabulary; dispatcher-entry disclosure; owner, next action, blocker; timestamped events; distinct RESTORED/CLOSED | Approved lifecycle transitions; elapsed acknowledgement/arrival timers; dedicated escalation acknowledgement workflow; validated timer; notifications/accessibility handoff |
| Handover/report | Assignment/open/unassigned/handover CSV; audit; confirmed schedule reset; counts and local compute time | Full KPI instrumentation, daily-date filtering, complete reason fields in exports, official history/reconciliation, retention/security controls |

## PRD QA checklist coverage

“Pass” below means the named local behavior is tested, not that the full production scenario is accepted.

| PRD ID | Local evidence / disposition |
|---|---|
| QA-01 50 tickets | Adapter benchmark runs 50 synthetic tickets / 10 staff; full 50-ticket UI acceptance remains pending |
| QA-02 missing fields | Invalid building fixture retained; validator blocks missing ID/location; malformed/naive scheduling windows rejected; complete ingestion schema testing remains pending |
| QA-03 duplicate ID | Deferred to ingestion contract; adapter rejects duplicate input IDs; ingestion quarantine/review remains pending |
| QA-04 related complaints | Repeated-asset candidates retained; heuristic accuracy not validated |
| QA-05 keyword hazard | ED-002 is review-held; no emergency classification is made |
| QA-06 unstaffed emergency | Critical fixture visible; confirmed-emergency model and approved procedure not integrated |
| QA-07 no crew | No eligible complete crew returns reason-coded exception |
| QA-08 attendance/active/shift | Negative tests reject UNKNOWN, ABSENT, inactive and off-shift |
| QA-09 qualifications | Missing, expired and UNVERIFIED qualifications rejected; DEMO_CONFIGURED disclosed |
| QA-10 area/depot | Mismatch rejected under demo borough/depot configuration |
| QA-11 overlapping staff | Second overlapping crew rejected; adjacent windows accepted |
| QA-12 paired crew | One complete crew/group saved in one transaction |
| QA-13 partial conflict | Whole proposal rejected; no partial write or audit of a successful assignment |
| QA-14 replacement/removal | Failed replacement preserves old state; complete-crew removal logged |
| QA-15 preemption | No automatic displacement implemented; displacement-plan UI remains deferred |
| QA-16 status | RESTORED and CLOSED produce separate timestamped events; no rigid transition policy claimed |
| QA-17 handover/timer | Owner/action/blocker persistence tested; official difficult-repair timer deferred |
| QA-18 API failures | Not applicable to local seed transport; integrated fallback tests deferred |
| QA-19 override | Manual and automatic paths share validator; invalid manual proposal preserves board |
| QA-20 reset | Confirmation required; assignments cleared; history retained |
| QA-21 determinism | Reversing input order produces identical proposals/exceptions |
| QA-22 KPI | Queue counts reconcile in UI; full PRD metric acceptance deferred |
| QA-23 exports | Nonempty CSV columns consistent; handover IDs/status/owner/action from common state; richer exception fields pending |
| QA-24 usability | Browser visual review plus Streamlit interactions; formal accessibility/keyboard audit pending |

## Open release decisions

The original JD text (Job ID 647208) has been supplied and mapped in JD_ALIGNMENT.md; its original URL and independent webpage verification remain outstanding. Team acceptance of the local adapter and shared-storage agreement remain outstanding. Repository Racheal-Winstead/Elevator-Dispatch and engine commit 6aff648 are now known. Monday’s date/time needs team confirmation. NYCHA authorities must validate staffing, role composition, area authorization, qualification requirements, priority mapping, emergency procedures, timer thresholds and minimum necessary resident-impact fields. No tenant personal information is present.
