# Racheal’s Crew Readiness — Learning and Demo Notes

## What you own

`roster.py` describes ten fictional staff members and demo crew requirements. `app.py` presents their readiness, the queue, scheduling decisions, and handover. A local adapter now calls a pinned copy of Deshawn’s actual engine. Synthetic data remains labeled, and his repository and storage implementation are unchanged.

## What the new screen does

Select a work order and time window. For each person, it checks attendance, active status, shift coverage, configured qualifications, authorized sector/depot, required role, and overlap with assignments on the local board. It shows the reasons someone is excluded. Individual readiness is not the same as a complete assignable crew; ticket-level holds and the joint validator still apply.

## Explain it in plain language

“The screen helps a dispatcher understand who could take the work and why another person cannot. Unknown availability stays unknown. It never fills an incomplete crew merely to make the schedule look complete.”

## Python concepts to learn

- Dataclass: a named structure for one technician, ticket, or proposal.
- Tuple: a fixed collection, such as authorized sectors or required crew roles.
- List comprehension: builds a filtered list of people or tickets.
- Pure validator: returns reasons from inputs rather than changing assignments.
- Session state: keeps UI choices during Streamlit reruns; it is not a replacement for persistent storage.
- Atomic commit: all required crew roles are saved together, or none are.
- HTML escaping: displays imported text as content instead of allowing it to become markup.

## Two-minute readiness demo

1. Identify DEMO SEED, demo-configured policy, and the absence of live staffing/Maximo connections.
2. Select a work order and explain its required roles and New York time window.
3. Point out a present person who passes individual checks and an absent/unknown person who is excluded.
4. Change the work order to another demo borough and explain the changed authorization results.
5. Filter Helpers and identify the demo-authorized float helper.
6. Explain that final assignment still needs a complete crew and shared validation.

## What is and isn’t proven

The current unit suite passed 46 tests, including negative cases for partial crews, overlaps, attendance, qualifications, rollback, determinism, persistence and audit. The Streamlit app loaded without exceptions and the role filter/time-window controls passed an interaction check. This does not prove zero bugs, real-world operating approval, production readiness, or repair-time savings.

## Review before presenting

Confirm the target presentation date with the team. Obtain the actual JD and review the local adapter contract with Deshawn. Do not call the current demo rules NYCHA policy. Use fictional data only. Rehearse with local internet-independent fixtures and capture a backup recording.
