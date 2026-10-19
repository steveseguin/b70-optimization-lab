# Packet171: one-card host-runtime parity audit; under spin, the remaining host gap is the foreground copy path, not publication

This was a CPU-only audit. No GPU, service or setting was touched. It compares the host-runtime mechanisms of two-card bundle 8 (`stage2/packet136-record-bundle`) with the one-card spin line (`stage2/packet58as-onecard-spinwait`, committed HEAD). Its prices come from the packet58as v5 per-token streams, which `measure_58as_host.py` recomputes into `measured.json`.

- Audit: `experiments/own-xpu-runtime/stage2/packet171-onecard-host-parity/AUDIT.md`
- Machine-readable copy: `audit.json` in the same directory
- Brief for the top item: `BUILD-BRIEF.md` in the same directory

## Findings

| Rank | Missing on one card | One-card price on the spin line (28.80 ms/token) | Label |
| --- | --- | ---: | --- |
| 1 | Foreground copies on the single in-order compute queue. Bundle 8 does this; one card uses a BCS list, a barrier per copy and a two-queue sync, and shares the copy ordinal with cache fills. | **0.99 ms/token** readback excess, up to 1.94 ms with the slow-token wait | measured; cause assumed |
| 2 | Non-blocking token input (p137 / MTP `queue_half_inputs`) | 0.05–0.3 | assumed |
| 3 | Reply-first. It lost **−0.004%** on two cards. | ≤ 0.3 | assumed; transfers 0 |
| 4 | Pure spin (`sleep20=0`). One card spins 250 µs, then sleeps 20 µs, which works out to about 75 µs per cycle (275 switches/token). | 0.05–0.08 | assumed, from measured counts |
| 5 | Ordered cache publication (the packet58ar design) | **≤ 0.018** drain. Total publication is 0.200 ms/position. | measured-derived; **dead under spin** |

Ordered retirement and prepared submission are present on both lines. Profiling queues are off in one-card record runs. The controller/mailbox and the p105 head split are two-card-specific. Graph replay is missing on both lines.

## The key measurement

- Under spin, the 8-byte token/error readback is bimodal:
  - 0.20 ms on 59.5% of tokens;
  - **2.63 ms on 40.5%** of tokens, which also wait 2.33 ms longer.
- A slow readback follows a fill-submission token (72.9 MB of fills, 49.4% of positions) with **P = 0.94**. It lands on that same token with P = 0.04.
- Packet58v's poll-era serial-vs-overlap bracket shows the same coupling independently. Mean readback was 0.46 ms/token with serial maintenance and 2.13–2.18 ms/token with overlap fills. The readback penalty arrived with asynchronous fills on the second BCS list.
- The packet58aq publication drain of 1.108 ms/token was a 1 ms poll artifact. Under spin, the whole publication costs 0.200 ms, almost all of it host construction and submission.
- **Codex picked ordered publication first. Do not package it on the spin line.**

## State and next step

- The kill test was **not** packaged to READY within the 60-minute box. `BUILD-BRIEF.md` specifies:
  - a private copy of packet58as HEAD;
  - a per-view drained switch to compute-queue foreground copies, with fills unchanged;
  - a CPU queue-placement test that fails on the old code;
  - a one-load lane-A v5 bracket with A = spin parent and B = compute-queue copies, ≥ +0.5% over every warm control, drift ≤ 3% and 60/60 exact;
  - the bimodality readout retained even on a loss.
- `stage2/packet171-onecard-ordered-publication/` is an untracked Codex partial: a path-rewritten copy of packet58as HEAD with no mechanism change. It is superseded. Do not queue it.
