# Combined console candidate

Branch: `codex/combined-demo`, based on the reviewed personal console at `afa9012`.

## What is connected

Racheal’s console design and five existing workflow tabs remain, with a sixth Messages & advice tab. Deshawn’s pinned engine, messaging and deterministic advisory functions use adapters around the console’s ticket and worker models. Upstream source snapshots remain unmodified; provenance and checksums are in `integrations/vendor/SOURCE.json` and `FEATURE_SOURCES.json`.

One local SQLite Store saves assignments, attendance overrides, messages, simulated replies, progress, activity and the demo clock. The seed day persists so reopening the app does not silently move assignment dates. Refreshing the synthetic source preserves saved history. Resetting assignments preserves the audit and message history.

Messages use the same work-order identifiers and saved crew. Eligibility checks use current saved attendance, actual shift boundaries and overlapping bookings. An urgent booking-conflict override requires explicit review and never moves an assignment. Absent, inactive, unknown-attendance or off-shift recipients remain blocked.

A simulated reply is recorded in history. Only when the dispatcher explicitly selects Apply this reply does an acknowledged reply update work to ACKNOWLEDGED, or a refusal update it to BLOCKED. The message must still belong to the current assignment and crew; old replies cannot overwrite a reassigned case. Message and progress updates are atomic. Duplicate replies are rejected.

Advancing the persisted demo clock by 15 minutes records overdue acknowledgement follow-up once per message. A later reply clears the current follow-up flag. This creates no automatic reassignment or external escalation. Availability, intake and exception advice use the same records and cannot change assignments. Handover combines current open work with separately labelled historical activity counts; its CSV includes message counts, latest replies and follow-up flags.

## Run and demonstrate

From `elevator-dispatcher/`:

```sh
python3 -m streamlit run app.py --server.address 127.0.0.1 --server.port 8504
python3 -m unittest discover -s tests -v
```

1. Review a complete crew on Dispatch plan and confirm it.
2. Open Messages & advice for the same ED ticket, review its saved crew and save a simulated message.
3. Record a reply; explicitly select Apply this reply to update progress.
4. Check Progress & exceptions and Shift handover for the same status and history.
5. Reopen or refresh the source to verify the records persist.

## Validation and boundaries

60 tests pass, including a Streamlit console test covering assignment, message, reviewed reply, progress, reporting, refresh and reopening. Regression tests cover stale crew replies, atomic rollback, attendance, off-shift sends, booking conflicts, duplicate replies, the 15-minute threshold and current follow-up clearing. Captured output: `COMBINED_TEST_RESULTS.txt`.

This is a synthetic, single-user local candidate. Messages have no SMS/email/field delivery. No live Maximo, REMS, staffing or emergency connection is included. Source switching and external ingestion are outside this change. The partner’s separate app and audit backend are not replaced. Local SQLite adoption by the team and operational policy validation remain pending. This branch does not merge or alter main, developer or the existing personal PR.
