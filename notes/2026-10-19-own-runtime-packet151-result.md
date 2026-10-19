# Packet151 result: the second-candidate sibling row costs ~18 ms per half (upper bound), so packet132 stays closed

Run on lane B (cards 2+3): smoke `packet151d-sibling-smoke-B` 01:57–02:01 UTC, one-load v5 `packet151e-sibling-bracket-B` 02:31–02:43 UTC. All views 13/13 exact, draft proposals identical, control drift 0.06%, no GPU faults (count 2).

The build is diagnostic and instrumented, so its controls run at 45.3 tok/s, not the 58.8 record line. The comparison is within one process.

| View | Choice | tok/s | interval ms | half A device ms | half A wall ms |
| --- | --- | ---: | ---: | ---: | ---: |
| 0 | control | 45.312 | 22.141 | 11.437 | 16.100 |
| 1 | sibling | 24.815 | 40.438 | 20.652 | 34.051 |
| 2 | control | 45.341 | 22.141 | 11.441 | 16.104 |
| 3 | sibling | 24.802 | 40.455 | 20.653 | 34.072 |
| 4 | control | 45.327 | 22.123 | 11.440 | 16.092 |

- **Measured extra sibling cost (upper bound): 17.96 ms per half**, of which **+9.21 ms is on the device**. Packet132's preregistered reopen bar is ≤ 1.952 ms.
- The analyzer's label is "inconclusive upper bound; full M=2 needed". The coordinator decision is not to build the full M=2 version: even the device extra is 4.7× the bar, and the second token's routed experts and attention are real extra traffic that batching does not remove. **packet132 stays closed.** A DO-NOT-REPEAT row is in `experiments/own-xpu-runtime/stage2/packet151-sibling-cost/DO-NOT-REPEAT.md`.
- Two packaging bugs were fixed on the way:
  - **p151d:** the `blk.0.gdn.qkv` sibling op had bypassed native preparation;
  - **p151e:** the bracket loaded the old smoke path.

  Both are now caught by `ops/rehearse_entry.py`'s new checks or are recorded in memory.

Evidence: `experiments/own-xpu-runtime/stage2/packet151-sibling-cost/v5/evidence/device151e-sibling-v5-B/bracket-summary.json`.
