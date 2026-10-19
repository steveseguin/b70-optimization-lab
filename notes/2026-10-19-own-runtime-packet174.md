# Packet174: the one-card fill never overlaps compute; next lever is a fill kick

CPU-only preparation for the one-card IQ3 own runtime (Qwen3.8 Flash-Next 125B-A6B UD-IQ3_XXS, one B70). Record line: packet58as bounded spin, 34.573 tok/s, 28.80 ms/token. No GPU, service or setting was touched. Nothing was queued.

- Packet: `experiments/own-xpu-runtime/stage2/packet174-onecard-fillkick/`
- Proposal: `experiments/own-xpu-runtime/ops/lane-queue/proposed-p174-v5-A.txt`, job `packet174-v5-A` (not in any live queue)
- Pricing: `pricing/candidates.json`, replay `pricing/replay-admission.json`

## Measured: the slow readback is the whole fill, serialized at the token tail

I joined `cache.jsonl` to the timing rows **by position**: one cache row per position, written at its end; fill bytes in a row were submitted at that position's start. Row counts match exactly (11,930 per run). Then I regressed on the packet58as v5 streams and repeated on the independent packet171b v5 streams.

| Quantity (spin views, decode tokens) | Value | Label |
| --- | --- | --- |
| P(slow readback \| fills submitted at this token's start) | 0.81 | measured |
| P(slow readback \| no fills this token) | **0.000** | measured |
| Readback excess per same-token fill MB | **0.0350 ms/MB** (0.0348–0.0352 across 7 views, 2 runs) | measured |
| Intercept vs neighbouring tokens | 0.01 ms | measured |
| Next-token readback slope | 0.0000 | measured |
| Fill MB per generated token | 30.63 (identical in every view of both runs) | measured |
| Fill-token wall excess vs neighbours | 0.28 ms + 0.041 ms/MB | measured (wait part partly miss-rate confounded) |
| Readback cost | **1.07 ms/token (3.7%)** | measured |

- A slope of 1/28.6 GB/s with zero intercept means the entire fill drains **after** compute and before the readback completes. The fill was submitted about 27 ms earlier, before the first kernel.
- Even the CCS-idle put/prepare window right after submission absorbs nothing. "Asynchronous" maintenance therefore never overlapped anything: the overlap mode won in packet58v only by dropping the serial path's per-copy barriers.
- **Correction to packet171b's readout.** Its "fill token" (other > 1.8 ms) is the publication/plan token. The slow token is the fill-submission token itself, not the one after it. The 535/488 "fill tokens" per view were heuristic counts; true fill bytes are identical in all views.
- Packet171b's B arm still used a `queue_->memcpy`. With UR v2 copy offload on by default (`UR_L0_V2_FORCE_DISABLE_COPY_OFFLOAD` is not set in the launch env; assumed), that likely remained copy-engine work. So 171b did not test a copy-engine-free readback.

## Priced candidates (per token, base 28.80 ms)

| Candidate | Price | Label | Packaged |
| --- | --- | --- | --- |
| (a) pacing: bounded chunks over N tokens / bytes-in-flight cap | 0 to −0.1 ms | measured-derived (linear law, zero absorption, same total bytes) + assumed admission delay | no |
| (b) timing: submit after the tail readbacks / after the last zero-copy expert | 0 to +0.2 ms | assumed 0.2–0.4 ms host gap per fill token; measured zero absorption argues for ~0 | no |
| (c) second-touch admission, W = 256 positions (fixed before the replay) | **≈ 0** (−0.54 fill + 0.53 miss) | replay transferred (packet55 two-card target routes, parent cadence, 21.55 GB LRU: fills −43%, misses +21%, scaled ×2.12 to the measured one-card fill rate); fill cost measured (0.041 ms/MB); miss cost 0.077 ms transferred from packet58x (1.55 ms/token for −13.5 misses, −12.4 MB fills) | no |
| **(d1) fill kick**: one non-blocking `zeCommandListHostSynchronize(maintenance list, 0)` after each fill batch | **0 to +1.07 ms**; +0.57 to +1.07 if the fill is held until a host synchronization | ceiling measured; mechanism assumed (supported by zero absorption even while the CCS is idle); 0–0.5 ms/token overlap contention assumed | **yes** |
| (d2) kernel-store tail readback (CCS writes token/error and route logs to pinned host memory; no copy engine) | 0 to +1.07 ms | ceiling measured; assumed that the fill remainder then hits the next copy-engine user; packet171b DNR family | no (second choice) |

**Why admission cannot win now.** A serialized 2 MB fill costs about 0.07 ms. The zero-copy miss it prevents costs about 0.077 ms. Admission tuning can only trade one for the other until fills overlap compute. Once they do, the same replay says to admit *more*, not less.

## Chosen: (d1) fill kick, packet174

- **Delta.** `apply_fillkick_delta.py` touches `main.cpp`, `single_device.cpp`, `bracket_table.hpp` and the new `fill_kick.hpp` (55 added lines).
- **Process-wide option.** `--fill-kick off|on`, default `off` (the parent), listed in `--help`. It is accepted with every engine chain-window argv (KD, W2m, WS, WS128x, WS128). K1a/K1b run the unchanged fixture binary. The bracket sets the same thread-local per view at the drained view boundary (A = `spin`, B = `spin-kick`). `--fill-kick` together with a bracket table is refused.
- **Exactness.** The cache content schedule is unchanged: the same plans, fills, evictions and publication boundaries. Publication still needs a completed fill at a later drained boundary. So the published table per position is identical in A and B. The hit and miss paths are already bit-identical: every parent v5 view is 60/60 exact with different residency, as were 58x's 18 GB vs max views.
- **Readout.** It is kept on every outcome. It reports the slow-readback fraction, readback ms per same-token fill MB, fill MB/token, decode hit rate (new host counters in `cache.jsonl`) and kicks. Collapse rule, fixed now: max B slow fraction ≤ 0.5 × min warm A, **and** every B slope ≤ 0.5 × every warm A slope.
- **Decision.**
  - B wins and the slope collapses: port `--fill-kick on` into the record chain. Then reprice admission, since more fills become affordable.
  - Neutral and the slope persists: fill execution is gated below the host flush. Next are (d2), or the fill volume with a re-measured miss cost.

## State

READY for the one-load lane-A kill test (`packet174-v5-A`). Nothing was queued or launched. All CPU gates passed in one compile turn: GNU/Intel byte gates, the `--fill-kick` parser in five engine windows with the parent binary refusing it, the source-delta test, the real preparation run, the analyzer, flags, imports, temporary `lanequeue plan`, `rehearse_entry --report` (one documented WARN) and the pin guard. The packet tree and READY are committed together.
