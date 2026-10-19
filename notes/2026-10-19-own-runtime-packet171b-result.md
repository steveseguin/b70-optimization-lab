# Packet171b result: compute-queue foreground copies are neutral, and the slow readback is fill contention

The one-card kill test for packet171 AUDIT row 1 is **closed**.

| Item | Value |
| --- | --- |
| Job | `packet171b-v5-A`, lane A, whole host, one load |
| Time | 2026-10-19 10:07–10:21 UTC |
| Arms | A = packet58as spin parent (BCS foreground copies plus a barrier per copy). B = spin plus in-order compute-queue foreground copies. |
| Evidence | `experiments/own-xpu-runtime/stage2/packet171b-onecard-cqcopy/evidence/v5-result.json`. Full summary: `screen/evidence/card0-171b-v5-a/resident/WSCREEN/summary.json`. |

## Bracket

| View | A0 (warm-up) | B0 | A1 | B1 | A2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| tok/s (class-balanced median) | 34.548 | **34.740** | 34.563 | **34.761** | 34.602 |
| ms/token (decode mean) | 28.82 | 28.66 | 28.81 | 28.64 | 28.79 |

- All 60 requests were exact vs `iq3-p49-split32-v1`, and warm drift was 0.11%.
- Minimum gain was **+0.40%**, below the +0.5% gate; maximum was +0.57%. `candidate_beats_all_controls` is false.
- B saves about 0.15 ms/token. Most of that comes from the fast readback path: the median readback fell from 0.17 to 0.13–0.14 ms once the barrier was removed. The saving is below the gate.

## Mechanism readout (kept on a loss, as pre-registered)

| View | Slow readback fraction (> 1 ms) | Slow / fast readback (ms) | P(slow after fill token) | P(slow on fill token) | Slow-token wait excess (ms) | Fill tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A0 | 0.4016 | 2.636 / 0.208 | 0.92 | 0.04 | 2.32 | 535 / 1524 |
| B0 | 0.4029 | 2.616 / 0.193 | 0.95 | 0.03 | 2.34 | 488 / 1524 |
| A1 | 0.4009 | 2.639 / 0.207 | 0.93 | 0.04 | 2.38 | 543 / 1524 |
| B1 | 0.4035 | 2.619 / 0.188 | 0.96 | 0.03 | 2.33 | 478 / 1524 |
| A2 | 0.4042 | 2.629 / 0.199 | 0.94 | 0.04 | 2.29 | 523 / 1524 |

The readout's verdict is "close row 1: slow mode persists". Moving the 8-byte token/error readback off the BCS list, with no barrier, left everything in place: the bimodal split, its 2.6 ms slow mode and its coupling to fills. So the slow mode is not the readback queueing behind fills on the shared copy ordinal.

## What the remaining slow-token cost points to

- **Size:** the slow tokens cost about 0.40 × (2.63 − 0.20) ≈ 0.98 ms/token in readback, plus 0.40 × 2.3 ≈ 0.93 ms/token in wait. That is **~1.9 ms/token**, about 6.6% of the 28.8 ms token.
- **Timing:** it appears on the token **after** a fill-submission token (P ≈ 0.92–0.96) and almost never on that token itself (P ≈ 0.03–0.04).
  - About a third of tokens submit fills (478–543 of 1524 per view), at 72.9 MB per filling position.
  - The asynchronous fill DMA is therefore still streaming during the next token's compute and at its boundary.
- **Shape:** both the compute wait (+2.3 ms) and the readback (+2.4 ms) stretch on that token. This looks like **bandwidth contention**: the fill DMA (H2D over PCIe, on the maintenance BCS list) runs concurrently with the next token's zero-copy expert-miss reads, which also cross PCIe from pinned host memory, and/or with its device-memory-bound kernels. Queue ordering is ruled out.

## Next measurable hypothesis

> The slow-token excess scales with the fill bytes still in flight at the token boundary, because fills and zero-copy expert-miss reads share PCIe (and device-memory) bandwidth.

1. **CPU only, on existing streams; no device run.** Use packet58as and packet171b `cache.jsonl` (per-position `fill_bytes`, fills) with `timings.jsonl`. Regress the next token's (wait excess + readback excess) on the previous position's fill bytes, and on the count of zero-copy misses in the slow token.
   - If the excess is proportional to fill bytes (at roughly 72.9 MB divided by measured H2D bandwidth), this is bandwidth contention.
   - If it is constant regardless of bytes, it is a completion or notification latency instead.
2. **Device follow-up, only if step 1 shows proportionality.** One-load bracket, A = spin parent, B = the same fills split into smaller chunks spread across the next positions (rate-limited), with unchanged cache content.
   - Prediction: the slow fraction falls and the per-token excess spreads out.
   - Gate: the usual ≥ +0.5% over every warm control, 60/60 exact.
   - Alternative B: delay fill submission until after the next token's zero-copy-heavy layers.

## Do not repeat

Do not move foreground copies to the compute queue for this slow mode. The DO-NOT-REPEAT row is in `packet171b-onecard-cqcopy/DO-NOT-REPEAT.md`; the AUDIT row 1 outcome is in `packet171-onecard-host-parity/AUDIT.md`. The process-wide `--foreground-copies` chain variant (packet171c) was cancelled before any tree or build existed.
