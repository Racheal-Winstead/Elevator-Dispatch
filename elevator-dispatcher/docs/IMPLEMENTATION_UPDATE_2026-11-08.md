# Implementation update — November 8, 2026

**Completed locally; no commits, pushes, branch changes or team merge performed.** This document explains the changes and provides detailed descriptions for future commits after reviewing the dedicated repository checkout and branch.

## What changed and why

### Connect Racheal’s console to Deshawn’s scheduler using a data adapter

`integrations/deshawn_adapter.py` converts local tickets, roster, roles, existing commitments and dated windows into the dictionary/DataFrame format expected by Deshawn’s engine. His recommendations convert back to the local Proposal model. IDs are preserved rather than replaced by display work-order numbers.

`integrations/vendor/deshawn_engine.py` is the exact upstream source from commit 6aff648. Its Git blob and checksum are recorded in SOURCE.json and tested. It is intentionally retained separately from Racheal’s modules to make attribution and review clear. A fresh private engine instance prevents slot/demo-clock configuration from leaking across requests. The original local scheduler is retained for comparison; app.py no longer calls it.

The adapter uses local exact eligibility checks before calling upstream, including qualifications and depot authorization missing from the engine’s current checks. It maps actual commitment overlaps into every trial slot, protecting against different slot labels hiding a collision. Returned proposals pass the same local hard validator used at final commit. Mapping errors, incompatible rules and invalid upstream output return reason codes and no partial plan.

### Fix timezone-based collision checking

`time_windows.py` centralizes parsing, aware-time validation, UTC conversion and half-open interval comparison. `validators.py`, the adapter and roster-readiness display use that boundary. SQLite stores normalized UTC endpoints. A 13:00–15:00 UTC booking now conflicts with 09:00–11:00 UTC−05:00 because these intervals truly overlap. Adjacent windows remain allowed. Naive, malformed, reversed or zero-length windows are rejected.

### Keep status consistent with committed crew capacity

`Store.status` now checks assignment presence inside the status-update transaction. UNASSIGNED is rejected when a crew remains committed. Complete-crew removal records status and removal together. The progress screen excludes UNASSIGNED for assigned work and directs the dispatcher to remove the crew on Dispatch plan. All crew-progress statuses still require an existing assignment.

### Preserve review, audit and local ownership

The console still previews recommendations and requires dispatcher review and reason before commitment. The final store validation uses current roster/commitments, so stale previews cannot bypass changed attendance or bookings. The scheduler makes no database changes.

Assignment records, their audit new-value payloads and CSV reports retain scheduler source, engine rule version and upstream commit. Manual assignment records identify MANUAL. Existing SQLite rows remain readable. Synthetic refresh preserves activity and booked work; shared SQLite adoption was not assumed or implemented in Deshawn’s app.

### Make documentation and runtime requirements match the implementation

The sidebar and Dispatch plan disclose the pinned engine connection and pending team merge/shared storage. README, learning guide, demo script, acceptance mapping and integration contract explain the current local connection. Requirements match the installed/tested Streamlit 1.61.1 and Pandas 3.0.5 runtime. There was no dependency installation for the app during this update.

## Validation

46 tests pass: the original 24 plus six local safety-regression cases and 16 adapter-contract cases. The adapter tests call the actual pinned engine and cover field conversion, deterministic ordering, invalid qualification/attendance/depot/expiry, overlapping named slots, mixed timezone commitments, unsupported inputs, malformed engine output, checksum/source identity, stale previews and persistence. The UI test covers confirmation-required assignment, invalid manual proposal rejection, engine provenance, refresh-history retention, status choices and complete-crew removal. An integration test covers preview → commit → status → export → restart → reset/history retention.

The initial targeted regression run reproduced both original local bugs (two failures) and naive-time handling (one error) before the fixes. All those cases now pass. See TEST_RESULTS.txt and BENCHMARK.json for current results. Browser review checked the updated engine disclosure and review-and-confirm proposal screen at a narrow responsive viewport.

## Limits

This connects a pinned scheduler locally with synthetic data. It is not a team merge, partner acceptance of SQLite, approved ingestion, live dispatch, Maximo/REMS access or production operational approval. Deshawn’s separate app, messaging and audit-reset defects are not changed by this work. Unknown attendance, incomplete crews, unverified qualification and actual overlap are still blocked locally. Demo category mappings and policies need operations validation before real use.

## Proposed future commit descriptions

These descriptions are prepared, not committed. Since the local app has not yet been imported into the personal remote branch, the actual first commit may need a clearly scoped baseline import before these logical changes can be separated. Do not pretend a baseline exists on that branch or commit this whole chat directory.

### 1. `fix: normalize dispatch windows and keep status consistent with crew bookings`

Normalize all comparison endpoints to timezone-aware UTC instants instead of ISO string ordering. Reject invalid or naive windows, preserve adjacent-window behavior, and reuse the same interval check in readiness and final validation. Store committed windows in UTC. Validate status/assignment consistency transactionally and require whole-crew removal before marking UNASSIGNED. Update the progress controls and add regression cases for rollback, mixed offsets, malformed stored windows and atomic removal.

### 2. `feat: adapt dispatcher data to Deshawn’s pinned scheduling engine`

Add explicit ticket, staff, role, work-type, window and commitment conversions for engine commit 6aff648. Preserve upstream source unchanged with a provenance manifest. Configure a private engine instance per request, prefilter exact local eligibility and map all overlapping commitments into engine occupancy. Convert returned groups to locally validated previews without persistence. Reject incompatible rules, duplicate IDs and unsupported data rather than silently falling back. Record engine provenance on committed assignments and exports, and connect app.py to the adapter while retaining human confirmation.

### 3. `test: verify engine adapter, persistence and dispatcher confirmation flows`

Add real pinned-engine contract tests and an integrated preview/commit/progress/export/restart/reset scenario. Extend Streamlit interaction coverage to assert engine provenance, source refresh retaining history and UNASSIGNED exclusion for booked work. Confirm invalid inputs and stale previews cannot mutate state. Record the reproducible local validation results.

### 4. `docs: explain data mappings, local integration boundaries and panel demonstration`

Update the integration contract, learning material, panel script, README and requirements for the local engine connection. Distinguish compatibility from a merged team application and leave shared SQLite adoption pending. Include mapping assumptions, supported window restrictions, source provenance, safety-check order, tests, benchmark scope and remaining acceptance gaps.

## Branch and staging plan for later

The intended personal remote branch previously observed is `codex/racheal`; the observed integration branch is `developer`. Before any commit, use a dedicated checkout of Racheal-Winstead/Elevator-Dispatch and verify its actual top-level directory and remote. The chat working folder currently inherits a home-directory Git repository. Never stage that directory wholesale. Stage reviewed source/tests/docs only; exclude SQLite runtime databases, caches, virtual environments and scratch review downloads.
