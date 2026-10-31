# Four-card prefill balance (2026-10-31): rank-0 lookup prefetch and balanced expert ownership on rank 1

Status: **done.** Both levers are committed to engine/src, default off.

**Result: four-card long prompt 219.51 → 216.74 / 216.76 s, exact** (set `tptsxqckhcbgl` = tptsxqckhcbg +
`OWNRT_PREFILL_LOOKUP_PREFETCH=1` + `OWNRT_PREFILL_EXPERT_BALANCE=rank1`; build r3 `4128ad66dd3c`; fresh servers at
131072, both arms on r3).
- Decode is unchanged (84.30 → 84.29 / 84.49 tok/s), and outputs equal the 3+1 262K reference and B19.
- In the long request, rank 1 dropped only 5.8 ms per chunk, against 14.7 on the harness. The 43+47 check shows this
  comes from the real prompt's routing, not from the cards.
- Rank 1 still sets the pace, now 6 ms ahead of rank 0.

Starting point: the lane published at 219.3 s (tptsxqckhcbg, commit 5cf6f085e). Per 256-row chunk of the long prompt:
- rank 1 is busy 459.8 ms, and it sets the pace;
- rank 0's critical path is 453.7 ms (prefill 440 + draft 13.7).

So a lever on rank 1 alone is worth at most about 6 ms until rank 0 also drops (research/tp/prefill-tp-overhead-2026-10-30).

## Lever A: rank-0 lookup prefetch (`OWNRT_PREFILL_LOOKUP_PREFETCH=1`), exact, kept

Rank 0 starts every chunk on the host: it computes the chunk's embedding and PLE lookup rows (ids from the token history,
then 4-thread dequantization), uploads them, and only then issues the chunk. The cards sit idle for that 5.3–5.8 ms.

**Change.**
- Each rank-0 prefill command also announces the next chunk. The service controller (`native_controller.hpp`) and the
  harness driver write that chunk's tokens into the prefill header page's free tail (`next_tokens_offset` 3072), then a
  hint with position and rows, magic written last (`prefill_wire.hpp`).
- Rank 0 consumes the hint at the prefill command. Once the current chunk's lookups are done, a helper thread computes the
  next chunk's rows, using the history this chunk leaves, while the chunk runs on the device. The host mostly waits in
  drains then.
- The next command uses those rows only if position, rows, tokens and starting history all match. The rows are a pure
  function of these and the resident tables (`lookup_input_at` is `lookup_input` with an explicit history). It then
  applies what the threaded path leaves: row-extent checks, `lookup_ids`, history and `read()` counters. Otherwise it
  computes the rows as before.

**Version 1, rejected** (build r1 `f4a6b759ae06`).
- It computed the rows on a helper thread during the draft command that precedes the next chunk.
- Exact; inputs 5.7 → 1.26 ms; chunk 403.7 → 400.1 ms.
- But the threads slowed the draft-chunk replay from 12.8 to 14.3 ms, so the net was only −2.1 ms.

**Version 2** (build r3 `4128ad66dd3c`), 1100-row harness, A/B/A/B:

| ms per chunk | A1 | B1 | A2 | B2 |
| --- | ---: | ---: | ---: | ---: |
| rank-0 chunk | 405.26 | 399.93 | 404.95 | 401.41 |
| inputs phase | 5.45 | 1.35 | 5.24 | 1.34 |
| draft chunk (median of full chunks) | 12.7 | 12.7 | 12.7 | 12.8 |

Result: **−4.5 ms per chunk** on rank 0. Every prefetch matched; states and all 71 drafts are equal.

## Lever B: balanced expert ownership on rank 1 (`OWNRT_PREFILL_EXPERT_BALANCE=rank1`), exact, kept

It reuses expert parity's owned-slot path (research/tp/prefill-tp-overhead-2026-10-30, lever 1): each card computes whole
experts, and the expert exchange (mode 2) stores only the owned expsdown rows.

Parity lost because it made the cards uneven. Here the owners are chosen per layer and chunk by a new kernel,
`iq3::kopt::route_balance` (one work-group per card):
1. a local histogram of slots per expert;
2. a cost per expert of 1 + ceil(slots/4);
3. a bitonic sort by (cost descending, id ascending);
4. snake order (sorted positions 4j and 4j+3 to card 0, 4j+1 and 4j+2 to card 1);
5. each slot kept or turned into the skip route.

The algorithm is integer-only and order-independent, so both cards derive the same owners. Exchange mode 2 now keys on
the card's filtered routes (owned = not the skip route), which gives the same rows as before for parity.

| 1100-row harness, ms per chunk | A1 | B1 | A2 | B2 |
| --- | ---: | ---: | ---: | ---: |
| rank 1, `rank1` | 457.21 | 442.83 | 459.15 | 444.06 |
| rank 0, `both` (on top of lever A) | 401.51 | 406.94 | 399.78 | 407.74 |

- Rank 1: **−14.7 ms per chunk**. States and 1116 exports are equal.
- Rank 0: +6.7 ms, **closed**, the same pattern as parity on rank 0. Hence the `rank1` mode.

## Gates (build r3, all on the 1100-row harness, 0 kernel-log faults)

- **Smokes:** 16-row chunks with an 8-row tail; rank 0 with lever A (and with `both`), rank 1 with lever B.
- **Exact, on vs off:** states, drafts and rank-1 exports for each lever.
- **Pattern m** with lever A equals the g1 reference.
- **sp=600 and sp=64 two-request**, on both ranks:
  - Equal: model state of requests A and B, the ones invariant, and rank-1 exports (1116 + 616 / 80).
  - Rank 0's allocation inventories are equal.
  - Rank 1's inventories differ only in `prefill:*` transaction scratch: packed shadow slots, `slot-x`, the expert
    grouping buffers and the new `prefill:parity-*` buffers. That scratch differs by construction on the owned-slot
    path. No model-state allocation differs.
- **One card, rank 0, lever A:** equal.
- **Decode-half hard gate, r3 default vs r6 `9885e8ad63fd`:** +0.04% (rank 1) and +0.16% (rank 0), inside the 0.3%
  limit. r3's default state also equals r6's.

## Servers at 131072, A/B/B on r3 ([results/suite/](results/suite/), [summary-r3.json](results/suite/summary-r3.json))

Every server passed its startup gate. 15 kernel-log checks, 0 faults. Long-request timelines:
[results/long-trace-*.json](results/).

| server | A r1 `tptsxqckhcbg` | B r1 `tptsxqckhcbgl` | B r2 `tptsxqckhcbgl` |
| --- | ---: | ---: | ---: |
| **TTFT, 121,854-token prompt** | **219.51 s** | **216.74 s** | **216.76 s** |
| decode after it (all 511) | 84.30 tok/s | 84.29 | 84.49 |
| 512 outputs = 3+1 262K reference | yes | yes | yes |
| MTP on the long request (hits / guesses) | 418 / 511 | 418 / 511 | 418 / 511 |
| 3,490-token prompt TTFT | 6.511 s | 6.444 | 6.448 |
| 12-prompt suite median (ids, sha, MTP = B19) | 87.26 (yes) | 87.14 (yes) | 87.41 (yes) |
| rank 0 prefill per chunk (median) | 440.6 ms | 434.0 | 434.3 |
| rank 0 critical per chunk (prefill + draft) | 454.6 ms | 448.2 | 448.1 |
| rank 1 busy per chunk / idle in the prompt | 460.1 ms / 0.03 s | 454.3 / 0.01 | 454.4 / 0.01 |

**Per lever.**
- **Lever B (rank 1, the pacing rank): −5.8 ms per chunk in the long request.** That is uniform across the prompt:
  −5.6, −5.5, −6.3, −6.7 and −4.8 ms for chunks 1–60, 60–120, 120–240, 240–360 and 360–475.
- **Lever A (rank 0): −6.4 ms of rank 0's critical path.** Alone it would barely move the TTFT: without it, rank 0's
  454.6 ms would just exceed rank 1's new 454.3. Rank 0 is now the next pacer, only 6 ms behind rank 1, so lever A is the
  headroom any further rank-1 cut needs.

**Why lever B gives −14.7 ms on the harness but −5.8 ms in the service: the routing, not the cards.**
- Same harness, same 1,100-row prompt, rank 1 moved to the service's cards 43+47 (pair 2.3), A/B/A/B:
  457.62 / 457.74 → 443.95 / 444.20 ms per chunk, **−13.6 ms**. Exact (states and 1116 exports equal), 0 faults
  (phase x1).
- On 23+47 the same comparison gave −14.7 ms. So the cards do not explain the gap.
- What remains is the input: the 121,854-token real prompt routes its 256-row chunks so that whole-expert ownership saves
  less weight traffic than on the 1,100-row evidence prompt.
- The service number (−5.8 ms per chunk on the pacing rank) is the one that counts. Future expert-path levers should be
  sized on a chunk of the long prompt's rows, not on the evidence prompt alone.

## What is left for prompt reading

Per 256-row chunk of the long prompt, rank 1 sets the pace at 454.3 ms and rank 0's critical path is 448.2 ms.

- **HC split on prefill: the largest remaining item, about −5.6 s TTFT** (HC-split agent's measurement). It waits on the
  owner's decision about the unmerged fc2 / HC-split patches. Not built around here.
- **Rank-1 input upload and readback overlap:** 3–5 ms per chunk on rank 1. The cards idle about 5.9 ms per chunk in rank
  1's host phases.
- **Expert path on rank 1:** what remains of the 22 ms of split work that does not halve. The real prompt's routing
  limits whole-expert ownership; finer per-tile balancing or a better cost model would need sizing on long-prompt rows.
- **Rank 0** must drop too before rank 1 gains count fully: it is only 6 ms behind. Its draft chunk is 13.7 ms, and its
  card 27 runs about 9 ms per chunk behind card 23 at the drains.
- **Closed:** the per-pair drain handshake (≤ 1.6 ms) and the copy-engine overlap (BCS fault history). Also closed: expert
  parity, row-parallel conv, balanced experts on rank 0, and prefetch during the draft (all in DO-NOT-REPEAT).

## Builds and patches

- r1 `f4a6b759ae06`: lever A version 1. Private tree `/dev/shm/pbal-engine-20261031`.
- r3 `4128ad66dd3c`: lever A version 2 + lever B (with parity's machinery). Private tree
  `/dev/shm/pbal-engine-20261031-b`; receipt `engine/receipts/4128ad66dd3c.json` pins it.
  [engine-prefill-balance.patch](engine-prefill-balance.patch) applies to engine/src HEAD (5c4fe964b).
- Harness: copied from prefill-tp-overhead-2026-10-30, plus extras `lp` and `eb=V`. The rank-0 driver writes the
  prefetch announcement. The lab adapter passes both flags to TP ranks. Arm `tptsxqckhcbgl` in [arm_env.py](arm_env.py).
- Runs: archived and sha256-verified under
  `/mnt/raid-models/ownrt-experiment-archives/2026-10-31/prefill-balance-runs-{l1,b1,b2,g1,x1}`; servers at
  `.../2026-10-31/prefill-balance-suite-r3`.
