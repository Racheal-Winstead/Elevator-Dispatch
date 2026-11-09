# Local validation record — November 8, 2026

46 automated tests pass: the original 24, six local safety-regression cases and 16 pinned-engine adapter cases. The initial targeted run reproduced the timezone collision, UNASSIGNED-with-booked-crew and naive-time failures before fixes. The regression cases now pass. TEST_RESULTS.txt contains the current suite output.

The adapter tests execute the real unmodified engine snapshot from upstream commit 6aff648. They cover role/field conversions, protected eligibility, deterministic ordering, actual commitment overlap, overlapping named slots, malformed and unsupported inputs, incompatible rules, duplicate IDs, invalid output, stale previews, source/checksum identity, missing snapshot handling and isolated engine configuration. Preview/commit/progress/export/restart/reset is tested with a temporary SQLite database.

Streamlit AppTest verifies review acknowledgement before assignment, complete-crew commitment, engine provenance, refresh retaining assignments/history, rejection of an invalid manual assignment, consistent progress choices and complete-crew removal.

The actual updated browser was inspected at http://127.0.0.1:8502. Engine disclosure and the Dispatch plan proposal/confirmation flow rendered without exceptions, including a narrow responsive view. adapter-preview.png records the new proposal view. This is a visual smoke check, not a full accessibility audit.

The 50-ticket / 10-resource benchmark ran ten times on macOS arm64 with Python 3.14.7. Pinned-engine adapter computation had a median of about 0.646 seconds and a maximum of about 0.672 seconds, excluding fetch and UI rendering. Eight recommendations and 42 exceptions reflect the bounded synthetic roster/capacity and holds. These counts do not demonstrate an 80% assignment rate. See BENCHMARK.json for exact values. This replaces the historical fixture-scheduler benchmark.

Streamlit 1.61.1 and Pandas 3.0.5 were installed and used. No app dependencies were installed during the update. Python 3.11 compatibility was not separately verified.

This establishes local scheduler compatibility with synthetic data, not a team branch merge, partner approval of shared SQLite, authoritative eligibility, live Maximo/REMS access, emergency dispatch or the full PRD release gate. The historical merge report remains relevant to the unchanged upstream app; its two local defects are corrected here.
