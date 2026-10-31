# Four-card prefill overhead (2026-10-30): where the ~120 ms per chunk over a perfect split goes

Status: **in progress.** Measurements M1/M4 are done. The first lever, expert-parity assignment, is exact but slower, so it
is closed. A diagnostic build is prepared for the parts not yet attributed (shape probe under batched prefill, drain
trace) and runs in the next device window.

Lane: SC117 four-card TP (`tptsxqckhcb` on build `e6daa268a3a8`, commit 979462f7c, TTFT 222.5 s at 131072). Rank 0 runs
on 23:00.0+27:00.0 (layers 0-22, lookups, MTP draft) and rank 1 on 43:00.0+47:00.0 (layers 23-47, head). The rank
harness puts rank 1 on 23+47. A 131072-token prompt is 476 chunks of 256 rows, and TTFT ≈ 476 × the slower rank's chunk.
In the long runs that is rank 1 at 466 ms and rank 0 at 446 ms (target chunk 414 ms plus the draft command).

## Breakdown per 256-row chunk ([results/breakdown.json](results/breakdown.json))

| ms per chunk | rank 1 | rank 0 | source |
| --- | ---: | ---: | --- |
| one card, device (target only) | 674.5 | 589.4 | M1: `--timing class` + `OWNRT_SITE_TRACE=1`, every site its own class ([classes](results/m-r1-one256-classes.json)) |
| of which replicated under TP / split | 105.8 / 568.7 | 103.9 / 485.5 | rank.hpp transform (tptsxqckh flags) |
| perfect split (one card / 2) | 337.3 | 294.7 | |
| **TP wall (prefill_chunk, host trace)** | **462.8–464.1** | **412.7–414.3** | g1/u1/u2 A arms |
| over the perfect split | 125.5 | 118.0 | |
| replicated work, excess over half | 52.9 | 51.9 | of which HC 34.0 / 30.7 and shared expert 12.1 / 10.6 |
| experts not halving (M=256 vs M=128 one-card proxy) | 24.5 | 6.6 | M1 `one128` arms |
| exchange kernels, own time | 18.9 | 17.5 | M4: `OWNRT_TP_EXCHANGE_STATS=0`, experts 14.0 / 12.9 ([r1](results/m-r1-xs-exchange.json), [r0](results/m-r0-xs-exchange.json)) |
| exchange wait | 0.6 | 0.6 | M4 |
| remainder | 28.6 | 41.4 | |
| of which host time a one-card chunk pays too (one-card wall − device) | 8.2 | 13.1 | one-card wall 682.7 / 602.5 |
| **TP-specific, not yet attributed** | **≈ 20** | **≈ 28** | the probe build below |

Each TP card runs 75 (rank 1) / 69 (rank 0) exchanges per chunk, moving 439 / 404 MB per card: gated GDN heads at
12.3 KB per row, attention out-proj rows at 5.1 KB, QSA attention at 12.3 KB, and compact expert slots at 51.2 KB
([CPU work model](tp_work_model.py), [results/tp-work-model.json](results/tp-work-model.json)).

**Correction (card balance).** A wait of 0.6 ms does NOT show the cards are balanced. `prefill_exchange` drains both
cards before every pair, so the two exchange kernels start together, and a card that finished early sits idle inside
the drain where the exchange statistics cannot see it. In prefill, card balance has not been measured yet; the drain
trace below measures it. (In decode there is no drain before an exchange, and stage-overhead-2026-10-30 measured
imbalance at 0.04–0.06 ms per half.)

## Lever 1: expert-parity assignment (`OWNRT_PREFILL_EXPERT_PARITY=1`), exact, closed

Each TP card computes the slots whose expert id has its parity, instead of compact slots c, c+2, …. Each expert's
weights are then read by one card, and its tiles are about twice as full. The route split is a new RouteParity kernel;
other cards' slots get a skip route that the expert-grouped bucket drops. The expert exchange gets a new mode 2, which
stores only the owned rows of the canonical expsdown into the peer at the same offset. Patch:
[engine-expert-parity-r2.patch](engine-expert-parity-r2.patch). The patch also switches on the tile-config sweep list
(`#if 1`, build r2 only); indices 0 and 1 are unchanged.

- **Exact everywhere.** s2 smoke, g1 at 1100 rows, u1, u2: rank 1 matched 1079/1079 buffers and 1116 exported rows;
  rank 0 matched 1029/1029 buffers and 71/71 draft buffers. The parity arm was also checked against token-by-token and
  against one card (patterns hmcn and m). 0 kernel-log faults.
- **Speed per chunk (host-trace means, 4 full chunks; A = the same build's default path):**

| arm | rank 1 | rank 0 |
| --- | ---: | ---: |
| A (g1 / u1 / u2) | 464.1 / 465.1 / 463.1 | 414.3 / 413.7 / 412.9 |
| parity, T=4 tiles (g1) | 457.0 | 430.3 |
| parity, launch divisor 1 / 16 (u1) | 459.1 / 461.7 | 432.9 / — |
| parity, T=8 tiles, configs 6 / 4 (u2, build r2) | 482.8 / 502.4 | 442.6 / 464.2 |

- Exchange own and wait times did not change (d1, parity arms). The one-card M=128 proxy over-predicted the gain.
  The cause is open; one candidate is per-layer card imbalance hidden in the drain (even vs odd expert ids). The drain
  trace can measure this on the parity arm too. Ledger row:
  [service-speed DO-NOT-REPEAT](../../../gsq-rco-iq3s/service-speed/DO-NOT-REPEAT.md).

## Other candidates (sized before M1; CPU work model and M1)

| lever | rank 1 | rank 0 | note |
| --- | ---: | ---: | --- |
| HC low/gate row split | ≤ 34 | ≤ 31 | owned by the separate HC-split agent; not pursued here |
| shared-expert split (gate/up by mid rows, down by h rows; exact) | ≈ 10 | ≈ 8.5 | +1 act exchange per layer, outputs merged into the expert exchange; touches the TP plan |
| copy-engine overlap of the expert exchange | ≤ 13–14 | ≤ 13 | risky (a second queue on single-CCS cards) |
| the TP-specific remainder | ≈ 20 | ≈ 28 | attribute first (below) |

Outside the HC split, no single lever reaches about 40 ms per chunk on both ranks.

## Next: probe build (prepared, CPU only; runs after the HC-split end gate)

The private source tree is `/dev/shm/pto-engine-20261030` (engine/src stays at HEAD). Everything is default off:
- `OWNRT_TP_SHAPE_PROBE=c` under batched prefill. One card runs card c's launches of the TP plan, with compact extents,
  route compaction and slot rows for card c. Combined with `--timing class` and the site trace, this times every split
  site at its TP shape, plus the TP-only sites. It is timing only and the outputs are not exact.
- `OWNRT_PREFILL_DRAIN_TRACE=1` (TP). At every pair drain and the final drain it records when each card is seen
  complete, when the drain returns, and when each exchange is issued, giving card balance and host turnaround per
  segment ([analyze_drain_trace.py](analyze_drain_trace.py)).
- The parity patch above (gated), so the parity arm can be drain-traced.

Harness: modes `probe0|probe1` and extra `dt` in [run_phase.sh](run_phase.sh); analyzer [analyze_probe.py](analyze_probe.py).

## Files and archives

- Harness and drivers: copies from prefill-draft-batch-2026-10-30. Extras added: `st1`, `xs=N`, `xp`, `gd=N`, `ex=N`,
  `dt`, probe modes.
- Runs, raw (sha256-verified):
  `/mnt/raid-models/ownrt-experiment-archives/2026-10-30/prefill-tp-overhead-runs-{s1m1,s2,g1,d1,u1,u2}`.
- Builds r1 `09328de33c90` (parity) and r2 `62119fe983ad` (parity + tile sweep list), archived under
  `/mnt/raid-models/ownrt-experiment-archives/2026-10-30/engine-builds/prefill-tp-overhead-20261030-r{1,2}`. Their
  receipts are in `engine/receipts/`.
- Kept evidence (state hashes, logs, host traces): [evidence/](evidence/); kernel-log checks: [logs/](logs/).
