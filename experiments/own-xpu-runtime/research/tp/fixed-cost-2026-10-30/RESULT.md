# Four-card fixed-cost campaign (2026-10-30)

**Question.** The [stage-overhead breakdown](../stage-overhead-2026-10-30/RESULT.md) showed that the four-card stage is
held back by fixed per-launch time. Split kernels that do not halve cost about 1 ms per stage, and replicated small
work costs about 4 ms per stage. Taken as one stack of exact, default-off levers with a single end-to-end gate, how much
of that comes back?

**Answer (rank harness).**
- Two levers were kept and both are bitwise exact.
- Together they take **0.60 ms off rank 0's speculative half and 0.64 ms off rank 1's half**:
  - rank 0: 9.20 → 8.60 ms;
  - rank 1: 10.16 → 9.52 ms.
- The cheap form of F3 was measured and closed. F3's full fusion, F4 and F5 were assessed and not built (sections
  below).
- **End gate, fresh four-card lab servers at 65536, A/B/A/B: 78.75 → 84.49 tok/s (1.073×).** It is faster on 12/12
  prompts in all four cross-pairs, every output equals B19, and the hit cycle goes from 10.39–10.44 to 9.68–9.70 ms.

## In plain words

- **F1, paired expert launch (kept).** On four cards each card runs 5 of the 10 expert slots. At 5 slots the expert
  gate and up GEMVs only take about 70% of their 10-slot time, so they sit on a floor. Running gate and up of the
  card's slots in one launch, with the SiLU product in the same launch, refills the GPU.
  - It saves **0.34 ms per half on rank 1 and 0.30 ms on rank 0**.
  - A one-card microbenchmark showed the same floor first: 5 + 5 slots take 87.7 µs in two launches and 65.6 µs in
    one.
  - On one card (10 slots) it saves nothing (+0.02 to +0.05 ms), so it is a four-card flag.
- **F2, deferred event retirement (kept).** After each drain the engine destroyed every finished event of both cards
  before it replied: about 0.3 ms per half on two cards. Now the next half retires exactly that complete prefix after
  its 64th launch on each card, while the cards work. Card 1's prefix is retired on its own submission thread.
  - It saves **0.30 ms per half on rank 1 and 0.29 ms on rank 0** on top of F1.
  - It also saves 0.13–0.14 ms on one card.
- **F3, GDN small kernels (closed).** The existing exact single-launch recurrence (`OWNRT_GDN_PREP=0`) saves 0.02 ms
  on rank 1 and 0.045 ms on rank 0, under the 0.05 ms bar. The full fused GDN kernel was not built (below).
- **F4, exchange stores in the producer's tail (deferred)**, worth at most about 0.1–0.15 ms per stage. **F5, glue
  fusion (not built)**: each chain is worth about 0.05–0.08 ms and earlier fusions gave their savings back.

## Steps (rank harness, ms per decode half)

Each A/B uses the prefill-speed rank drivers with the same inputs: rank 1 on 23:00.0 + 47:00.0, rank 0 on 23:00.0 +
27:00.0, context 65536, F32. The prompt is 128 rows read as halves, then 64 decode halves (rank 0: 64 speculative hits
with drafts). Medians are over halves 3..64 ([summarize.py](summarize.py), [results/steps.json](results/steps.json)).
Each row has two A/B pairs, in A/B/A/B order.

| Step | Flag | Rank 1 off → on | Rank 0 off → on | Saving r1 / r0 | One card r1 / r0 | Kept |
| --- | --- | --- | --- | ---: | ---: | --- |
| F1 paired expert launch | `OWNRT_TP_EXPERT_PAIR=1` | 10.162 → 9.821 | 9.203 → 8.897 | **0.34 / 0.31** | −0.02 / −0.05 | yes |
| F2 deferred retirement (on F1) | `OWNRT_RETIRE_DEFERRED=1` | 9.818 → 9.515 | 8.891 → 8.605 | **0.30 / 0.29** | +0.14 / +0.13 | yes |
| F3a single-launch recurrence (on F1+F2) | `OWNRT_GDN_PREP=0` (existing) | 9.520 → 9.501 | 8.608 → 8.564 | 0.02 / 0.045 | −0.14 / — | no (< 0.05) |

**Gates, all bitwise against one card** ([logs/](logs/) `g*-compare.txt`):
- Rank 1: full state 1079/1079 and all tokens equal for F1, F1+F2 and F1+F2+F3a. This includes the batched
  1,100-row two-request case (`--second-prompt 64`), with both requests' states and tokens equal. The pair is also
  exact on one card (10 slots).
- Rank 0: 1029/1029 target and 71/71 draft buffers equal, with equal draft tokens, for patterns `h`, `hmcn` and `m`,
  and the batched two-request case (both requests).
- Card 1 equals card 0 on every buffer both hold in every TP run. There were 0 exchange timeouts.
- Kernel log clean before every phase and after every arm.

## F1: paired compact expert launch (`OWNRT_TP_EXPERT_PAIR=1`)

- **Why.** On four cards each card computes 5 expert slots. The per-slot GEMVs then sit on a floor: a 5-slot launch
  costs 0.69–0.70 of a 10-slot one (gate/up). The census had already measured 10 → 20 slots at exactly 2×.
  - The lab copy of the expert kbench ([kbench/experts5.cpp](kbench/experts5.cpp),
    [results](results/kbench-experts5.txt)), IQ2_S, cold weights:

    | Layout | µs |
    | --- | ---: |
    | R4, 5 slots | 44.4 |
    | R4, 10 slots | 65.6 |
    | 5 + 5 slots in two launches | 87.7 |
    | **5 + 5 slots in one launch** | **65.6** |
    | R2, 5 + 5 slots in two launches | 76.8 |

    All variants are bitwise equal.
- **What.** One launch per layer and card at the gate site. Each subgroup holds rows of both matrices: RH rows of one
  slot from the gate and the same rows from up. RH is 2 for ≤ 5 slots, which gives the subgroups of a 10-slot R4
  launch, and 4 otherwise. Every row keeps its own kernel body (kopt `MultiplyBlockRows` for IQ2_S/IQ3_S, dn2
  `xxs_packed` for IQ3_XXS), lane mapping, decode, add order and tree. Both outputs and both status words are written
  as the separate launches write them.
- **SiLU.** The product is `ng::silu(gate) * up`, the activation kernel's own expression, on the two stored values.
  It is written under that kernel's guard: no store while the half is inactive or the sticky error is set, and an
  out-of-range position fails the half.
- **Scope.** The up and activation sites issue nothing in decode. Batched prefill and row replays keep the three
  sites. The one IQ4_XS layer (47) stays unpaired, so 48 of 50 layer-card pairs are paired on rank 1 and all on rank 0.
- **Files.** `stage2/packet194-expert-diet-engine/expert_pair.hpp`, `dn2_kernels.hpp`, `expert-iq3xxs-block/.../block.hpp`,
  `packet6-kopt/kernels.cpp|hpp`, `dense-packed-block/.../generic_engine.hpp`, and `main.cpp` (`execute_site`).

## F2: deferred event retirement (`OWNRT_RETIRE_DEFERRED=K`, host only)

- **Why.** `Engine::retire_events` ran at every drain and readback. It queries and destroys every finished event of the
  card: 0.29–0.32 ms per TP half, against 0.13–0.15 ms on one card. The final drain's retirement sits between the
  device finishing and the reply.
- **What.**
  - A retirement point records the card's event count instead of retiring. Every caller waits first, so all of
    those events are complete.
  - The next decode half retires exactly that prefix (`Device::retire_prefix`, backend `clear_events_through`) after
    its K-th launch on that card (default K = 64).
  - Card 1's prefix is retired on its own submission thread.
- **Bounds.** Inside a batched prefill chunk, or past 4,096 recorded events, a retirement point retires on the spot as
  before. The owner's ledger refuses 16,384.
- **First build.** It had no bound inside prefill chunks, and the batched two-request smoke stopped host-side with
  "event ledger full". Fixed in build r4.
- **Exactness.** No device operation changes.
- **Files.** `owner_api.hpp`, `owner_retire.cpp`, `single_device.cpp`, `main.cpp` (`retire_events`,
  `retire_deferred`), `prefill_engine.hpp`, and `rank.hpp` (the two hooks).

## F3, F4, F5: closed or deferred, with reasons

- **F3a** (`OWNRT_GDN_PREP=0`, the existing exact recurrence with its prep inline, one launch per layer): 0.02 ms on
  rank 1 and 0.045 ms on rank 0. Exact (hmcn). Under the 0.05 ms bar; closed.
- **F3, the full fused GDN launch** (conv + both recurrence launches + gated norm + a), not built:
  - The gated norm needs all 128 rows of a head. A work-group per head gives 24 work-groups per card.
  - The conv updates its history in place. Fusing it into the 3,072 recurrence work-groups, which share key-head
    channels, needs double-buffered history or per-channel ownership, a new race surface.
  - Conv + recurrence alone removes one ~5 µs launch per layer, about 0.09 ms per half.
- **F4, exchange stores and flag in the producer's tail**, deferred:
  - What it can save is the exchange kernels' own time, 0.146 / 0.158 ms per half, plus about 1 µs of launch each.
    The flag wait stays.
  - It needs store-and-flag tails in five producer families (gated norm, Q8 attention GEMV, expert down, QSA
    attention, head shard) and a fresh waiting consumer for each.
  - The largest single piece, the expert down exchange, is worth about 60 µs per half.
- **F5, replicated glue fusion**, not built. Per card per half on rank 1, from the stage-overhead probe:

  | Chain | µs | Launches |
  | --- | ---: | ---: |
  | route | 305 | 25 (kernel time, not launch overhead) |
  | HC norms | 308 | 100 |
  | combines | 247 | 50 |
  | mix | 168 | 50 |
  | act | 139 | 50 |
  | qsa.select | 118 | 14 |
  | gather | 104 | 25 |
  | moe_combine | 97 | 50 |

  - Fusing a whole chain into a neighbour removes 25–50 launches of 2–3 µs, about 0.05–0.08 ms per half.
  - The DO-NOT-REPEAT records that the HC gate+mix fusion lost its saving in the slower fused kernel (suite
    0.982× / 1.003×).
  - The shared expert's gate and up formats differ within layers (Q4_K / Q5_K / Q6_K / IQ4_XS), so pairing them needs
    new kernels per format pair.

## End gate

Fresh four-card lab servers at 65536 ([suite/](suite/), copies of the prefill-speed suite tooling):
- Binary `0509ad71a0fd` ([receipt](../../../engine/receipts/0509ad71a0fd.json)), A/B/A/B.
- `tptsxqck` (current) against `tptsxqckf` = `tptsxqck` + `OWNRT_TP_EXPERT_PAIR=1` + `OWNRT_RETIRE_DEFERRED=1`.
- Rank 0 on 23:00.0 + 27:00.0, rank 1 on 43:00.0 + 47:00.0.
- Each server passes its 13-case startup batched-prefill gate and the F32 self-test / state oracles, then serves the
  12-prompt suite (one cold request each, 512 cap, greedy) and the 3,490-token TTFT request.

**Result: the stack passes the +7% target.** The F-flag servers decode **84.49 tok/s against 78.75** (mean of the
server medians), **1.073×**. Each F server is faster on **12/12 prompts** in all four cross-pairs (per-prompt ratio
1.069–1.078).
- All outputs equal B19 on all four servers: ids, sha256, and MTP guesses and hits.
- The 3,490-token TTFT is unchanged.
- The 13-case startup gate passed 13/13 on every server, and the kernel log was clean through the whole chain.
- ([results/endgate-summary.json](results/endgate-summary.json), [suite/results/suite/](suite/results/suite/),
  [results/hitcycle-endgate.json](results/hitcycle-endgate.json))

| Server | Median tok/s | Mean | Range | 12-prompt decode wall (s) | Outputs | TTFT 3,490 (ms) |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| tptsxqck-r1 | 78.90 | 79.23 | 76.31–83.30 | 75.15 | = B19 | 7,365 |
| **tptsxqckf-r1** | **84.47** | 84.87 | 81.72–89.30 | 70.15 | = B19 | 7,375 |
| tptsxqck-r2 | 78.60 | 79.03 | 75.84–83.23 | 75.35 | = B19 | 7,358 |
| **tptsxqckf-r2** | **84.51** | 84.83 | 81.77–89.21 | 70.19 | = B19 | 7,381 |

Hit cycle from the controller traces (the 3,490-token request, 40 hits and 23 misses per server), ms:

| Server | Hit cycle | Miss interval | Rank-1 half | Rank-0 speculative half | Draft | Rank 0 later in |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| tptsxqck-r1 / r2 | 10.389 / 10.440 | 19.79 / 19.88 | 10.32 / 10.36 | 9.29 / 9.31 | 1.07 | 55% / 53% |
| tptsxqckf-r1 / r2 | **9.679 / 9.703** | 18.51 / 18.51 | 9.58 / 9.55 | 8.61 / 8.64 | 1.06–1.07 | 68% / 85% |

- The hit cycle drops by 0.72 ms (−6.9%) and a miss by 1.3 ms.
- Rank 0 (speculative half + draft, 9.69–9.72 ms) is now the slower path in most hit cycles. The next lever should
  take time off rank 0 first: its draft (1.07 ms) or its half.

Raw server directories (1,252 files, sha256-verified): `/mnt/raid-models/ownrt-experiment-archives/2026-10-30/fixed-cost-suite-20261030/`.

## Files

- Engine (commit `7d7fc56f4`, default off): see F1 and F2; receipt `engine/receipts/0509ad71a0fd.json`.
- Harness:
  - [run_phase.sh](run_phase.sh), with extras `ep`, `rd`, `gp0`, `lenv=`, `batched` and `sp=`;
  - [analyze.py](analyze.py), [summarize.py](summarize.py), [archive_runs.sh](archive_runs.sh);
  - [kbench/](kbench/).
- Results: [results/](results/). Logs and comparisons: [logs/](logs/).
- End-gate tooling: [suite/](suite/), with the arms `tptsxqckf` and `tptsxqckg` in `arm_env.py` and the two new keys in
  the lab adapter. Hit cycles: [hitcycle.py](hitcycle.py).
- Raw runs (sha256 lists beside each; state bundles from g4b on are not kept, but their hashes are, and state.json
  keeps every buffer's hash): `/mnt/raid-models/ownrt-experiment-archives/2026-10-30/fixed-cost-runs-*`.
