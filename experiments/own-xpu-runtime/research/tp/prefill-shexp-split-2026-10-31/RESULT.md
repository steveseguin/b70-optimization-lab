# Four-card prefill: the shared expert split across each card pair (2026-10-31)

Status: **done; committed to engine/src, default off.**

**Result: four-card long prompt 216.82 -> 213.04 / 213.13 s, exact** (set `tptsxqckhcbgls` = `tptsxqckhcbgl` +
`OWNRT_PREFILL_SHEXP_SPLIT=1`; build r1 `37ee90a428cd`; fresh servers at 131072, all on r1).
- Decode is unchanged: 84.15 -> 84.20 / 84.08 tok/s after the long prompt. The decode-half gate gives -0.02% / +0.00%.
- All 512 outputs equal the 3+1 262K reference, and the 12-prompt suite equals B19.
- In the long request rank 1 (the pacer) drops 7.9 ms per chunk and rank 0 6.6 ms. Rank 1 still sets the pace, about
  4.5 ms ahead of rank 0.

Lane: SC117 four-card TP, set `tptsxqckhcbgl` on build r3 `4128ad66dd3c` (engine/src HEAD, commit f781d6870), long
prompt 216.74 / 216.76 s at 131072. Per 256-row chunk of the long prompt, rank 1 paces at ~454 ms and rank 0's critical
path is ~448 ms (research/tp/prefill-balance-2026-10-31).

Question: in batched prefill, both cards of a pair still run the whole shared expert (gate and up 640 x 2560, down
2560 x 640 per layer). The probe sized that at 11.6 / 10.3 ms per 256-row chunk beyond half (rank 1 / rank 0;
research/tp/prefill-tp-overhead-2026-10-30). Does an exact row split, prefill only, take that off both ranks?

## The change (`OWNRT_PREFILL_SHEXP_SPLIT=1|full|gateup|down`, default off)

Private tree `/dev/shm/pss-engine-20261031` (engine/src HEAD + [engine-prefill-shexp-split.patch](engine-prefill-shexp-split.patch)),
build r1 `37ee90a428cd` ([receipt](../../../engine/receipts/37ee90a428cd.json)). Host code only, in two files:
`rank.hpp` and `prefill_engine.hpp`. No kernel changed.

- **Decode is untouched.** The plan's replicated launches (both cards: shexpgate, shexpup, shexpact, shexpdown) are still
  exactly what decode runs.
- **Prefill gets split sites instead.** `prefill_allocate` replaces those eight sites per layer in `prefill_sites` with
  split sites the engine owns (`prefill_shexp_sites`). They are never in `p.launches`, so no decode structure sees them:
  not the prepared commands, the speculative image or the plan admission.
  - `gateup`: card c computes intermediate rows [c*320, c*320+320) of gate and up into `shexpgate#tp` / `shexpup#tp`,
    then the activation over those rows into `shexpact#tp`. One strided direct exchange (`tp_xgather`, 320 of every
    640) assembles `shexpact` on both cards, and down runs replicated from it.
  - `down`: gate, up and the activation stay replicated. Card c computes output rows [c*1280, c*1280+1280) of down into
    `shexpdown#tp`, and one exchange assembles `shexpdown` before the unchanged `moe_combine`.
  - `full` (= `1`): both, so two exchanges per layer (50 per chunk on rank 1, 46 on rank 0).
- **Whole rows only, never a split along K.**
  - A split GEMV is the replicated site's own dispatch at half the rows: `gsq_linear_matrix` (kopt reuse2 for Q6_K /
    Q8_0), or the dense block kernel with its TP row count (IQ4_XS / Q4_K / Q5_K).
  - It reads rows [row0, row0+rows) of the **whole** replicated weight, so there is no extra memory. A row view on the
    weight allocation, for that one launch only (`Device::row_views`), moves the bound weight pointer by row0 x row
    bytes on the host.
  - Kernel, arguments and per-row arithmetic are unchanged. The offsets are multiples of 256 bytes, so every
    base-pointer alignment check still holds.
- **The activation** is elementwise: `silu_product` over 320 values per row, one native batched launch.
- **New exchanges** take prefill flag slots after every decode slot: rank 1 uses 204-253 and rank 0 uses 197-242, of 256.
- **The TP transform** (`rank.hpp`) plans only the per-card half buffers (`#tp`). In full mode that is 224 KB per card on
  rank 1. Decode never writes them, and the dump and the card compare skip them.

## Gate 1: CPU plan check and smallest device smoke

- [cpu_plan_check.py](cpu_plan_check.py) ([results](results/cpu-plan-check-r1.json)) runs `OWNRT_PLAN_ONLY=1` on both
  ranks at 131072, with the flag off and in each of the three modes:
  - stored weights per card equal flag off (whole weights, no slice);
  - decode exchange sites and slots equal flag off;
  - planned buffers grow by exactly the half buffers: 224,000 / 96,000 / 128,000 bytes per card on rank 1 (25 layers)
    and 206,080 / 88,320 / 117,760 on rank 0 (23 layers);
  - the last prefill slot is 254 on rank 1 and 243 on rank 0, both within 256.
- Device smoke s1: 16-row chunks with an 8-row tail, full mode against A (flag off) on the same binary
  ([logs/s1-compare.txt](logs/s1-compare.txt)):
  - rank 1: 1079/1079 buffers and 44 exports equal; also equal to the archived r3 reference `bs-r1-eb`;
  - rank 0: 1029/1029 and 71/71 draft equal; also equal to the archived r3 reference `bs-r0-lp`;
  - the run record `prefill-shexp-split.json` shows 25 / 23 layers and 50 / 46 exchanges per chunk;
  - 0 kernel-log faults and 0 exchange timeouts.

## Gate 2: rank harness at 131072, 1100 rows (phases g1, g2; build r1)

Rank 1 runs on 23+47, rank 0 on 23+27, with the lane's flags. Timing is the mean of the full 256-row chunks after the
first ([phase_timing.py](phase_timing.py), [results/g1-timing.json](results/g1-timing.json)). Arms ran in the order
A1, full1, gateup1, down1, A2, full2, gateup2, down2.

| ms per chunk | A1 / A2 | full | gateup only | down only |
| --- | ---: | ---: | ---: | ---: |
| rank 1 (pacer) | 444.63 / 442.83 | 437.52 / 437.78 (**−6.1**) | 439.80 / 439.28 (−4.2) | 440.75 / 442.81 (−2.0) |
| rank 0 | 400.76 / 400.32 | 393.54 / 391.49 (**−8.0**) | 396.88 / 395.37 (−4.4) | 397.67 / 397.86 (−2.8) |

- **Full mode is the best.** The two halves add up: gateup + down = −6.2 / −7.2 against −6.1 / −8.0 for full.
- The probe's 11.6 / 10.3 ms beyond half does not all come back: 6.1 / 8.0 ms on the harness. The 50 / 46 added
  exchanges (each with its drain) cost about 0.11 / 0.05 ms per chunk each against that sizing. Probe sizes are upper
  bounds.
- **Exactness, all equal** ([logs/g1-compare.txt](logs/g1-compare.txt), [logs/g2-compare.txt](logs/g2-compare.txt)):
  - every mode against A on both ranks: 1079 buffers + 1116 exports on rank 1, 1029 buffers + 71 draft on rank 0;
  - full against the archived r3 references `b-r1-e1` and `c-r0-p1`;
  - rank 0 pattern m (full) against prefill-balance's `g-r0-m`;
  - TP full against the one-card 65536 references (`xctx_compare.py`): rank 1, rank 0 hmcn, rank 0 m.
- **Two-request cases** (RESET, then a 600-row or 64-row second request; full against A; both ranks):
  - both requests' states, tokens and draft are equal, and so are rank 1's exports (1116 + 616, 1116 + 80);
  - the exact-pattern ones checker passes;
  - rank 0's inventories: 282/282 common allocations equal. The only entries on one side are prefill shadows: the new
    `prefill:blk.*.shexp*#tp` in place of the old `prefill:blk.*.shexpgate/up`;
  - rank 1's inventories: 81 common, and only three shadow-packing slots per card differ (`prefill:pack2/3/7`). That is
    transaction scratch whose packing follows the role set, the same pattern as prefill-balance. No model-state
    allocation differs.
  - The "DIFFER" verdict at the end of the first g2 block in `logs/g2-compare.txt` comes only from those rank-1 packing
    slots, which the driver's `second_ok` counts, as in prefill-balance's g1.
- 0 kernel-log faults in 26 arms.

## Gate 3: decode-half hard gate (phase d1)

The new binary's default path (flag off) against r3 `4128ad66dd3c`, interleaved twice per rank, 64 halves, lane flags
([decode_gate.py](decode_gate.py); [results/decode-gate-r1.json](results/decode-gate-r1.json),
[results/decode-gate-r0.json](results/decode-gate-r0.json)):

| decode-half median (ms) | r3 run 1 / 2 | r1 default run 1 / 2 | change |
| --- | --- | --- | ---: |
| rank 1 | 9.3587 / 9.3531 | 9.3646 / 9.3434 | **−0.02%** |
| rank 0 | 8.4223 / 8.4367 | 8.4286 / 8.4311 | **+0.00%** |

- Both pass the 0.3% limit.
- The default prefill chunk is unchanged too: 444.2 vs 444.4 ms (rank 1) and 401.7 vs 401.7 ms (rank 0).
- r1's default-path state equals r3's: 1079 + 1164 exports, 1029 + 71 draft. 0 kernel-log faults in 8 arms.

## Gate 4: fresh servers at 131072, A/B/B, all on r1 ([results/suite/](results/suite/), [summary.json](results/suite/summary.json))

- A = `tptsxqckhcbgl`; B = A + `OWNRT_PREFILL_SHEXP_SPLIT=1`. Both arms on r1, so the A/B isolates the flag.
- Each server ran with `--wait-seconds 300` and passed the 13/13 startup batched-prefill gate and the F32 self-tests and
  state oracles.
- 15 kernel-log checks, 0 faults.
- Both B rank processes carried the flag ([logs/rank-env-tptsxqckhcbgls-r1.txt](logs/rank-env-tptsxqckhcbgls-r1.txt),
  [-r2](logs/rank-env-tptsxqckhcbgls-r2.txt), from `/proc/<pid>/environ`). Their `prefill-shexp-split.json` records
  show 25 / 23 split layers.
- Long-request timelines: [results/long-trace-*.json](results/).

| server | A r1 `tptsxqckhcbgl` | B r1 `tptsxqckhcbgls` | B r2 `tptsxqckhcbgls` |
| --- | ---: | ---: | ---: |
| **TTFT, 121,854-token prompt** | **216.82 s** | **213.04 s** | **213.13 s** |
| decode after it (all 511) | 84.15 tok/s | 84.20 | 84.08 |
| 512 outputs = 3+1 262K reference (`bf1f0867d1bd`) | yes | yes | yes |
| MTP on the long request (hits / guesses) | 418 / 511 | 418 / 511 | 418 / 511 |
| 3,490-token prompt TTFT | 6.453 s | 6.348 | 6.343 |
| 12-prompt suite median (ids, sha, MTP = B19) | 87.36 (yes) | 87.43 (yes) | 87.14 (yes) |
| rank 1 busy per chunk / idle in the prompt | 454.5 ms / 0.02 s | 446.5 / 0.03 | 446.7 / 0.04 |
| rank 0 prefill per chunk | 433.7 ms | 427.2 | 427.4 |
| rank 0 critical per chunk (prefill + draft) | 448.8 ms | 442.1 | 442.2 |

- A on r1 reproduces the published lane: 216.82 s against 216.74 / 216.76 s on r3. So the default path is clean.
- **The long request gains more than the harness on rank 1:** −7.9 ms per chunk against −6.1. Rank 0 gains −6.6 ms of
  its critical path, against −8.0 ms on the harness.
- −3.7 s TTFT is 476 chunks x the pacing rank's −7.9 ms.
- Rank 1 still paces, now about 4.5 ms ahead of rank 0. So a further cut on rank 1 alone is again capped at about
  4.5 ms per chunk until rank 0 drops too.

## What is left for prompt reading

Per 256-row chunk of the long prompt, rank 1 now paces at 446.5 ms and rank 0's critical path is 442.1 ms.

- **HC split on prefill** (research/tp/hc-split-2026-10-30): the largest remaining item, measured at −5.6 s TTFT on the
  older lane. It still waits on the owner's decision about the fc2 / HC-split patches. Its exchanges would land on top of
  this lever's: the last prefill slot is already 254 of 256 on rank 1, so combining them needs the 512-slot control
  block from that patch.
- **Per-exchange cost.** Rank 1 now runs 125 exchange pairs per chunk and rank 0 runs 115, each with a host drain. This
  lever's 50 / 46 pairs gave back roughly 4-5 ms on rank 1. A cheaper exchange would pay on every split lever, but the
  F4 tail and the drain skip are already closed (DO-NOT-REPEAT).
- Rank-1 input upload / readback overlap: 3-5 ms per chunk.
- The rank-1 expert path that does not halve, sized on long-prompt rows (prefill-balance).

## Builds, patches and files

- Engine change: [engine-prefill-shexp-split.patch](engine-prefill-shexp-split.patch) against engine/src at f781d6870
  (`rank.hpp`, `prefill_engine.hpp`; host code only).
- The committed engine/src files are byte-identical to the private tree `/dev/shm/pss-engine-20261031/src`. All 267
  sources pinned by the receipt match engine/src.
- Build r1 `37ee90a428cd`: `/dev/shm/engine-build-pss-20261031-r1`. Its receipt,
  [engine/receipts/37ee90a428cd.json](../../../engine/receipts/37ee90a428cd.json), pins that tree, so the tree stays in
  `/dev/shm`. The binary reads its rope table from the tree.
- Build and tree copy, sha256-verified: `/mnt/raid-models/ownrt-experiment-archives/2026-10-31/engine-builds/prefill-shexp-split-r1`.
- Harness: a copy of prefill-balance-2026-10-31's, with these changes:
  - extra `ss=V` (`OWNRT_PREFILL_SHEXP_SPLIT=V`; the run must write `prefill-shexp-split.json`);
  - extra `keep` (state bundles are deleted after each arm unless set);
  - the kernel-log check runs through `sudo -S`.
  - New tools: [cpu_plan_check.py](cpu_plan_check.py) and [phase_timing.py](phase_timing.py).
  - Launchers: [logs/launch_g1.sh](logs/launch_g1.sh), [launch_g2.sh](logs/launch_g2.sh), [launch_d1.sh](logs/launch_d1.sh).
- Server tooling: a copy of prefill-balance's [suite.sh](suite.sh) and [run_arm_suite.sh](run_arm_suite.sh), with
  `pss` unit names, arm `tptsxqckhcbgls` in [arm_env.py](arm_env.py), and `OWNRT_PREFILL_SHEXP_SPLIT` in the lab
  adapter's `TP_KEYS`.
- Kept evidence (state hashes, host traces, inventories, split records): [evidence/](evidence/). Kernel-log checks are in
  [logs/](logs/).
- Raw runs, archived and sha256-verified, under `/mnt/raid-models/ownrt-experiment-archives/2026-10-31/`:
  - `prefill-shexp-split-runs-{s1,g1,g2,d1}`;
  - CPU plan check: `prefill-shexp-split-cpu-plan-check`;
  - servers: `prefill-shexp-split-suite-r1`.
- Ledger row (the gateup-only and down-only modes): [service-speed DO-NOT-REPEAT](../../../gsq-rco-iq3s/service-speed/DO-NOT-REPEAT.md).

## Incidents

None. 0 kernel-log faults over 34 harness arms and 3 servers, and no exchange timeouts. One launcher bug did not reach
the cards: `$(... && echo ,keep)` under `set -e` aborted the first g1 launch before any unit started, and was fixed.
