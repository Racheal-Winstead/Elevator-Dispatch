# Elevator Dispatcher (NYCHA demo MVP)

A dispatcher workbench demo: loads a sample work-order queue, checks data quality, suggests
mechanic + helper crews with hard rules (no double-booking, no half crews), explains anything it
can't staff, tracks status, and exports a shift handover.

**DEMO ONLY.** Synthetic data. Not connected to Maximo, REMS, staffing systems or emergency dispatch.
All rules (crews, slots, certifications) are demo settings, not NYCHA policy.

## Run it
    pip install -r requirements.txt
    streamlit run app.py          # opens http://localhost:8501

## Deploy (free link)
1. Push this folder to a GitHub repo.
2. Go to share.streamlit.io, sign in with GitHub, pick the repo, main file `app.py`, click Deploy.

## Files
- `app.py`      screens (6 tabs)                -- Racheal's side
- `engine.py`   rules, scheduler, reason codes  -- Deshawn's side
- `tickets.csv` sample work orders (edit freely)
- `staff.csv`   sample 10-person roster (edit freely)
- `messaging.py` simulated on-duty messaging, schedule-conflict blocks, 15-minute NO_ACK  -- Deshawn
- `agents.py`   availability + conflict-check + notification-draft agents (advise only; validator decides)
- `maximo_mock.py` local MOCK Maximo-shaped feed (`{"member": [...]}`) built from `tickets.csv`; `engine.load_tickets_from_maximo` maps it back
- `tests/`      `python -m pytest -q`

## Change the demo story
Edit the CSVs and refresh. Built in on purpose: a bad-data row, a repeated ticket ID, two calls on the
same elevator, a "stuck" ticket that isn't confirmed, an unstaffed confirmed emergency (Staten Island),
an absent / unknown-attendance / expired-certification person, and a float helper.
Slots, crew needs by work type, and the demo clock are at the top of `engine.py`.

## 5-minute demo path
1. Queue tab: red DEMO banner, review queue (bad row, duplicate, "stuck" not auto-declared an emergency).
2. Crew tab: absent / unknown / expired people are marked not schedulable.
3. Schedule tab: Run auto-schedule -> 11 of 19 assigned, 0 rule violations, reason codes for the rest.
4. Manual assign: pick Mechanic A + Helper A in S1 for T-1005 -> rejected (double-booked), nothing changes.
5. Progress tab: acknowledge the Staten Island escalation; set a ticket BLOCKED with a note.
6. Reports tab: handover CSV + activity log. Sidebar: reset (log is kept).


## Messaging and agents (PRD v2.1)
Tab 6: pick a work order, see who is available (availability agent), edit the drafted message, send to someone on duty.
Off-duty people are always blocked. A busy person is blocked too, unless the message is urgent and the dispatcher confirms after seeing the conflict (their assignment never changes). 'Simulate 15 minutes passing' shows NO_ACK. Messages are SIMULATED: no SMS, no phone numbers.
Agents are deterministic code that call the shared validator; they cannot assign, send, or change status.


## Maximo alignment (PRD 4.13) -- mock only
`maximo_mock.py` makes Maximo-shaped JSON from `tickets.csv` (wonum, siteid, description, wopriority, assetnum, location, status, plus reportdate/worktype). `engine.load_tickets_from_maximo(payload)` maps it back to the ticket columns and runs the same checks; a missing field becomes INVALID_TICKET_DATA (held in review, never dropped).
**Field names are UNVERIFIED for NYCHA**; `x_` fields are invented demo carriers. Maximo `status` is read-only source data kept in `maximo_status`, separate from dispatcher statuses. The sidebar "Ticket source" switches between `tickets.csv` and the mock feed (switching reloads and clears the schedule and log). There is no live Maximo connection.

## P1 agents (advisory only)
In tab 6, below the conflict check: **intake** (missing fields, possible duplicates, hazard-review cases; never declares an emergency from keywords), **exception explainer** (reason code -> plain language + next human action), **handover** (draft shift summary from the activity log). Pure functions in `agents.py` with no access to the schedule, messages or statuses. Deterministic, no LLM calls.
