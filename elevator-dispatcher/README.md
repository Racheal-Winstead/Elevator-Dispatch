# Combined branch

The current candidate is `codex/combined-demo`; see [COMBINED_BUILD.md](docs/COMBINED_BUILD.md). It adds shared simulated messaging and advice to the existing console. The setup notes below describe the earlier personal implementation. Current validation: **60 tests pass**. Use port 8504 to keep the earlier previews separate.

# Elevator Dispatcher — Racheal’s demonstration

A separate local project for Racheal Winstead’s roster, dispatcher console and QA assignment. Vendor Performance Manager is outside this project and was not modified by this work.

## Start here

From this folder, run:

```sh
python3 -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

Open http://127.0.0.1:8501. Stop the terminal server with Control-C. The available environment already contains Streamlit, Pandas and Altair; no package installation was needed. Tested here on Python 3.14; Python 3.11+ is the intended baseline, not a separately verified compatibility matrix. SQLite is included with Python and substitutes for the proposed DuckDB dependency, which was unavailable.

```sh
python3 -m unittest discover -s tests -v
```

Read [the detailed update and proposed commit descriptions](docs/IMPLEMENTATION_UPDATE_2026-11-08.md), [the learning guide](docs/LEARNING_GUIDE.md), [five-minute script](docs/PANEL_DEMO.md), [acceptance mapping](docs/ACCEPTANCE.md), and [integration contract](docs/INTEGRATION_CONTRACT.md).

## Working scope

- Ten fictional staff, five demo borough authorizations, four two-hour windows, attendance and configurable required roles.
- Readiness explanations; searchable work queue; review holds; recommendations from a pinned copy of Deshawn’s engine; validated complete-crew commits, replacement and removal.
- Local progress, owner and next action; activity history; CSV assignment, open-work, exception and handover reports; confirmed schedule reset.
- Clear DEMO SEED disclosure, unknown external commitments and no live system access.

`demo_adapter/fixtures.py` still supplies synthetic tickets. The app now calls `integrations/deshawn_adapter.py`, which translates local data for an unmodified, checksum-verified copy of Deshawn’s `engine.py` at commit `6aff648`. The previous fixture scheduler remains available for historical comparison but is not the app backend. This is local engine compatibility, not a merged team application or agreement to share SQLite. The original expired NYCHA posting text (Job ID 647208) was supplied on November 9, 2026 and is preserved in docs/sources/. Its original URL remains unavailable. The repository is Racheal-Winstead/Elevator-Dispatch. PRD research claims were read as supplied context and have not been independently verified.

## Local state and limits

`workbench.sqlite3` stores assignments, progress and audit events. Attendance edits live in the browser session and return to seed defaults in a new session; their activity is recorded. Refresh updates the synthetic refresh record, not an external system. Reset removes local crew assignments while retaining ticket fixtures and history. The audit is append-only through the application API, not tamper-proof storage. This is a single-user local demo without production authentication.

Fixture dates are generated from the current UTC demo day. Do not carry a multi-day demo board into a new day's rehearsal without reviewing/resetting it. No tenant data or production credentials belong here. Empty CSV subsets currently produce empty downloads.

The Monday milestone needs team confirmation of date and time. No earlier showcase date was substituted.

## Current local update

46 tests pass, including real pinned-engine adapter tests and the timezone/status regression tests. No Git commit, push or branch change was made for this update. The eventual personal branch is `codex/racheal`; the remote integration branch observed in review is `developer`. Confirm a dedicated repository checkout before staging; this chat folder currently inherits a home-directory Git root.

## JD alignment and assumptions

Read [the original posting text](docs/sources/NYCHA_ELEVATOR_DISPATCHER_647208.txt) and [the six-duty feature mapping](docs/JD_ALIGNMENT.md). The [repository README assumption log](../README.md#assumption-log) records Gap, Assumption, Why and Check for demo policies and design inferences. Structured local records and CSV exports do not implement Maximo data entry or official Maximo reports; hardware maintenance is outside this slice.
