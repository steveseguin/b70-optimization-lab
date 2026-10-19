# Packet150 result: rank 0's out-of-layer time on bundle 8, split by one-load replays

2026-10-19 00:09:47–00:16:55 UTC, lane B (cards 2+3), unit `screen-packet150-split-bracket-B`.
It had been refused at 23:44 on the 25 GB storage floor (5 × 1.1 GB reserved), and was re-queued once root reached 32.16 GB.
Diagnostic only: no speed claim, not submission-eligible.

- **Run:** one model lifetime (target and draft loaded once), five views, one teardown. All views were **13/13 exact**, draft proposals were identical, and control drift was 0.136%.
- **Measured:** host-monotonic scopes on rank 0, median of the controls, in ms per cycle. The replay column is the extra time from re-running the scope a second time (or zeroing the wait), minus the skip view.

| Segment (scopes) | Control ms/cycle | Replay − skip | Verdict |
| --- | ---: | ---: | --- |
| capture_snapshot (snapshot, accept, rollback) | **0.743** | 0.335 | ≥ 0.4 in every control; removal unproven |
| merge_handoff_waits (head waits, import/export, handoff, remote reply) | **1.852** | 0.0005 | ≥ 0.4; mostly rank-1 merge work inside rank 0's reply wait |
| suffix_head | 0.311 | 0.300 | below 0.4 |
| token_prep (+ history) | 0.123 | 0.084 | below 0.4 |
| draft_wait | 0.006 | 0.00002 | below 0.4 |

The analyzer names **no proven-removable segment**. Replays isolate duplicate service only; the required target work and the peer dependencies remain. Snapshot is host capture and submission time; its asynchronous device copy is not timed separately.

**Decision:** `capture_snapshot` is the largest rank-0 host segment above the bar.
- Packet131 rotated 29.6 of 48.6 MB per cycle.
- The remaining 984 extents (19.0 MB) are still re-described by the host and uploaded every cycle.
- **Codex p153** (launched 00:18 UTC) builds `snapshot_host=static`: descriptor tables precomputed once at load and selected per cycle. It runs as a smoke plus a one-load v5 on lane B.
- The merge wait is rank 1's real work, so it is not attacked here.

Evidence:
- `experiments/own-xpu-runtime/stage2/packet150-rank0-split/v5/evidence/device-split-v5-B/` (243 MB, untracked; bracket-summary.json committed);
- analysis: `experiments/own-xpu-runtime/stage2/packet150-rank0-split/v5/evidence/analysis-split-v5-B.json`.
