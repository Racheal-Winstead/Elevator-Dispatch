# Elevator-Dispatch

Elevator dispatcher-assistance demo, built by Racheal Winstead and Deshawn Jeter.

A dispatcher workbench for NYCHA elevator work orders: it loads a work-order queue, checks data quality,
suggests mechanic and helper crews under hard scheduling rules, explains anything it cannot staff, tracks
status, and exports a shift handover.

**DEMO ONLY.** Synthetic data. Not connected to Maximo, REMS, staffing systems or emergency dispatch.
Crew rules and certifications are demo settings, not NYCHA policy.

## Repository layout
| Branch / path | Contents |
|---|---|
| `main` | Project overview (this README). |
| `deshawn` | Full application: `elevator-dispatcher/` (Streamlit app, rules engine, agents, sample data, tests) and `docs/PRD_v2.1.docx`. |

## Running the application
From the `deshawn` branch:

    cd elevator-dispatcher
    pip install -r requirements.txt
    streamlit run app.py          # http://localhost:8501
    python -m pytest -q           # run the test suite

See `elevator-dispatcher/README.md` for the demo walkthrough.
