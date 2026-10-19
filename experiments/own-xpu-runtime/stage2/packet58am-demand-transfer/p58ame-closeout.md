# Packet58ame report recovery closeout — 2026-10-19

Question: can the completed amd smoke be reported without another GPU run?
Yes. The outer window failed only while reading the omitted 58c fixture manifest.
The driver had already completed both oracle comparisons and written its reports.

Seven files in three fixture directories were copied from packet58aj, checked
against packet58ah, and bound in `lineage/report-fixtures.json`. The real report
path's lineage reference is 58c-supervisor; the two sibling fixtures also remain
available for inherited tests. An open audit of the real path records 227
existing paths in `evidence/p58ame-report-dependencies.json`. No model or device
payload was opened. Peak RSS for this audit was 32,358,400 bytes.

`test_report_recovery.py` calls the actual `summarize_bracket` and
`window.postload_observation`, without patches, on the saved device output.
`evidence/p58ame-old-tree-regression.log` shows its original missing-file failure;
`evidence/p58ame-real-report.log` shows its pass after vendoring.

The recovered summary and demand report live beside the retained smoke:
`screen/evidence/card0-demand-amd-fixed/smoke/`. `report-regeneration.json`
binds all original files, report sources, fixtures, oracle inputs and recovered
reports by hash. All original receipts, including the failed outer window and
queue, remain byte-identical. The native and driver had passed and drained.
S0 and S1 each have **12/12 exact requests** against `iq3-p49-split32-v1`.
This is 64-token screening, not promotion or a full-output quality claim.

The original demand report observed 988,003,883 ns of overlap. Its frozen-parent
cross-session overhead check **failed** and `smoke_passed` remains false there.
The owner's explicit packet58ame instruction accepts recovered exact S0/S1 as
the v5 smoke precondition; `REPORT-RECOVERY-POLICY.md` records this narrowly
scoped admission change. No overhead or speed result is relabeled.

The fresh inert row is `packet58ame-demand-v5-A`; the consumed smoke row is
unchanged and must not be queued again. Its native output path and demand identity
are fresh. Measured native smoke volume is 179,061,955 bytes. Conservatively
scaling two diagnostic views to five and retaining a 1.5 reservation factor
reserves 671,482,332 bytes for v5, plus 16,186,856 bytes for K1. This is storage
planning, not a speed projection. The 25 GB floor and host reserve stay intact.

CPU validation includes 17 Python tests, both real device-binary CPU preparation
paths (236 commands and layer-2 exclusion), both real-parent replay datasets,
real queue-main K1a/K1b/WSCREEN sequencing with synthetic process transport,
executable help, entry/report rehearsal and isolated lanequeue planning.
The report regression uses actual saved output without mocked report functions.
Rehearsal retains the existing generic preparation/identity WARNs; the dedicated
real binary preparation gate supplies its separate evidence.

READY is written last after the final seal. It permits direct v5 coordinator
admission using the recovered exact smoke; no smoke rerun is needed. GPU work,
service starts, live queue edits, sudo and settings changes were not performed.
No native source or binary changed. Revisit only if a bound input changes or a
fresh device run finds a new fault. Original raw device evidence remains local;
the recovered reports and complete input-hash manifest are retained in Git.
