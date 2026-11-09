# Elevator-Dispatch

Elevator dispatcher-assistance demo — Racheal Winstead and Deshawn Jeter.

## Racheal’s reviewed local implementation

This checkout is on `codex/racheal`, tracking `origin/codex/racheal` in
[Racheal-Winstead/Elevator-Dispatch](https://github.com/Racheal-Winstead/Elevator-Dispatch).
The application lives in `elevator-dispatcher/`, matching the directory layout on Deshawn’s branch.

The console uses synthetic work orders and personnel, a data adapter for Deshawn’s pinned engine,
review-before-commit crew assignment, and local SQLite-backed activity history. It does not connect
to Maximo, REMS, live staffing or emergency dispatch. Demo eligibility and crew policies are not
verified NYCHA operational rules. Shared storage adoption and merging into `developer` are pending.

```sh
cd elevator-dispatcher
python3 -m streamlit run app.py --server.address 127.0.0.1 --server.port 8502
python3 -m unittest discover -s tests -v
```

Dependencies and their tested versions are in `elevator-dispatcher/requirements.txt`.
The checked-in upstream engine source and its exact commit/checksums are documented in
`elevator-dispatcher/integrations/vendor/SOURCE.json`.

- [Application setup and scope](elevator-dispatcher/README.md)
- [Implemented changes and proposed commit descriptions](elevator-dispatcher/docs/IMPLEMENTATION_UPDATE_2026-11-08.md)
- [Data adapter contract](elevator-dispatcher/docs/INTEGRATION_CONTRACT.md)
- [Learning guide](elevator-dispatcher/docs/LEARNING_GUIDE.md)
- [Panel demonstration](elevator-dispatcher/docs/PANEL_DEMO.md)

## Checkout and history notes

The files were copied byte-for-byte from the reviewed local project into this dedicated repository;
the original demonstration folder remains available. The branch retains the existing remote history
starting at `7271c01`. Placement made no commit or push and did not merge another branch.

Some application documents describe the earlier chat-folder setup and its inherited home-directory
Git root. Those are historical notes: this dedicated checkout now has its own `.git` directory and
verified GitHub remote. Run Git commands here, not from the original chat folder.

Runtime databases, local secrets, Python caches and virtual environments are excluded. The original
SQLite database and scratch review downloads were not copied into this checkout.
