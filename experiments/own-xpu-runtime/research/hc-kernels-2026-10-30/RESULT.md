# Faster exact HC kernels: norm in one launch, combine fused into it, low GEMV codegen (2026-10-30)

**Question.** The [persistent-layer study](../persistent-layer-2026-10-30/RESULT.md) suggested a side finding: plain
BF16 hyper-connection (HC) GEMVs looked faster than the engine's. Could kernels that keep the engine's per-element
arithmetic and reduction order bit for bit win back that bandwidth, and could the two-launch HC norm become one launch?

**Answer: yes, exactly. +3.7% decode tok/s on fresh four-card servers, every output equal to B19.**

Three default-off tokens, `OWNRT_HC_KERNELS=1` = `norm1,lowsel,cnorm`, merged in `c1c3012e9` and `3d85cdb20`.

**End gate.** Fresh four-card lab servers at 65536, run in the order A/B/A/B (receipt `17f5f49ff010`):
- A = `tptsxqckh`; B = `tptsxqckh` + `OWNRT_HC_KERNELS=1`.
- Every server passed its 13/13 startup gate.
- On every server, all 12 suite outputs equal B19: token ids, SHA-256, and MTP guesses and hits.

| server | median tok/s | controller hit cycle | miss interval |
| --- | ---: | ---: | ---: |
| A r3 | 84.61 | 9.678 ms | 18.55 ms |
| B r3 | **87.76** | **9.331 ms** | 17.86 ms |
| A r4 | 84.58 | 9.690 ms | 18.50 ms |
| B r4 | **87.63** | **9.354 ms** | 17.86 ms |

- Mean of medians: 84.59 → 87.69 tok/s (**+3.66%**).
- B is faster on 12 of 12 prompts in all four cross-pairs, by 1.034–1.044 (median 1.037).
- The hit cycle drops by 0.34 ms (−3.5%) and a miss by 0.67 ms.
- In the service, B's ranks admit every HC norm (rank 0: 92/92, rank 1: 102/102, two cards each), with 88 and 98
  combine→norm pairs.

**Rank harness, half medians (A/B/A/B).**

| layout | rank | flags off | flags on | change |
| --- | --- | --- | --- | --- |
| one card | rank 1 | 12.31 / 12.36 ms | 12.01 / 11.95 ms | −2.8% |
| one card | rank 0 | 10.80 / 10.80 ms | 10.465 / 10.46 ms | −3.1% |
| four cards | rank 1 | 9.505 ms | 9.121 ms | −4.0% |
| four cards | rank 0 | 8.599 ms | 8.282 ms | −3.7% |

**The first end-gate attempt halted, and was fixed.** Receipt `63c4a26a22d6`; no fault.
- B's startup gate failed 11/13: tokens and state were equal, but the draft guesses differed.
- `cnorm` had paired `blk.47.ffn.combine` with `final.norm`. Rank 1's controller reads `streams` back right after
  that combine and sends it to rank 0 as the draft's input, so the draft received pre-combine rows.
- The rank harness missed it because rank 0 ran on fixture rows.
- Fix (`3d85cdb20`): never pair across a controller read. The combine before `final.norm` is never paired, and there
  are no pairs at all with pipeline exports or `--retain-steps`.
- The harness now records rank 1's exported draft-input rows and requires them equal
  ([drivers/tp_rank1_driver.py](drivers/tp_rank1_driver.py)). The old binary fails that check from row 0; the fixed
  one passes it token by token and batched (section "Export check").

## In plain words

- **The GEMVs were not the problem.** Measured side by side on the same card and the same real data:
  - the engine's HC low+inject GEMV takes 14.5 µs and its gate GEMV 13.2 µs;
  - this is not the census's production 16.3 / 16.0 µs. Most of the earlier "gap" was context, not the kernel.
    Putting an ALU-bound kernel or a 96 MB weight stream between blocks did not reproduce 16 µs, so the production
    figure stays unexplained.
  - Every exact rescheduling was equal or slower: rows per subgroup, chunks in flight, work-group shapes, SIMD16
    pairs, software prefetch to L1/L2/L3.
- **One codegen fix in the low GEMV.**
  - `dense_v2::bf16_multi` picks its matrix with a runtime index into the captured descriptor array. That keeps the
    descriptors in private memory: one dependent load before the first weight load.
  - Selecting by static indices runs the identical `bf16_rows` call 0.8 µs faster (`lowsel`).
  - The gate GEMV gains nothing (13.0–13.2 µs either way). Closed.
- **The HC norm in one launch instead of two (`norm1`).** 6.0–6.3 µs becomes 4.5–4.6 µs.
  - The engine's second stage makes every one of its 2,560 items re-read all 80 partial sums and re-run the
    80-element tree in a 512-float private array.
  - The new kernel gives each stream row one 640-item work-group with the same partials (also written to the
    engine's scratch), the engine's own `upper()` order evaluated by one subgroup, and the same `rsqrt` and output
    expression. Every load is issued up front.
- **The combine fused into the norm (`cnorm`).** The combine that writes `streams` (CombineFast:
  `streams += branch · 2·sigmoid(inject/4)`) immediately precedes almost every HC norm, and it is per-element within a
  stream row. So the norm's work-group combines its own row first, writes it back, and normalizes the values it
  already holds: one launch instead of three.
  - Bench: 9.4 µs becomes 5.4 µs.
  - Pairs per half: 44 on rank 0 (layer 1's pair is split by the PLE) and 49 on rank 1 (`blk.23.hc.a.norm` follows
    the handoff, and the combine before `final.norm` stays unpaired because the controller exports `streams` there).
    The rank-harness gates below ran with 50 pairs on rank 1; the end gate ran with 49.
- **Why this succeeds where `OWNRT_GSQ_FUSE_NORM` did not** (DO-NOT-REPEAT: rank 1 differed from layer 23's KV on).
  - That attempt rewrote the plan: the combine site absorbed the norm's outputs, weights and parameter and the norm
    site was deleted. Every path that walks the plan saw the merged site, including batched prefill (whose multi-row
    combine writes only the combine) and row replays.
  - Here the plan is untouched. Only decode (`view_row < 0`) skips the combine site and launches the fused kernel at
    the norm site. Batched prefill, row replays and non-adjacent pairs run both sites as before.
  - The gates include exactly the failure class that attempt hit: rank 1's full state, layers 23–47, after a 128-row
    prompt read token by token and through batched prefill, plus a second request.

## What the engine computes (pinned from the sources at `83abad01a`)

- **HC low + inject.** Path: `gsq_linear` → `kopt::fused_gemv` (HC low 320 × 10240 and inject 4 × 10240 in one
  launch) → `Multiply::run<BF16,32>` → `dense_v2::bf16_multi<1,8>` under `OWNRT_DENSE_DECODE_V2=1`. This is the
  `bf16_rows<1,8>` kernel.
  - Per output row: 32 logical lanes. Lane l owns the 8-element chunks at 8l + 256i (i = 0..39).
  - From 0.f, chunk by chunk and element by element: `acc = acc + bf16(w)*x`. BF16 → F32 is `u << 16` with no NaN
    quieting. The product is rounded, then added (`-ffp-contract=off`).
  - Then an adjacent-pair tree over the 32 lanes: xor strides 1..16, each node lower block + upper block.
  - Lane 0 stores.
  - Layout: one row per 32-lane subgroup, 4 rows per 128-item group, 81 groups. The final HC low is the same with
    320 rows.
- **HC gate.** 10240 × 320, `bf16_multi<2,4>` (`OWNRT_DECODE_NEXT2` `hcgate`): the same per-row arithmetic.
  - Lanes 0–7 hold two chunks (8l, 256+8l); lanes 8–31 hold one.
  - Two rows per subgroup, reduced by a transposing butterfly whose values equal the one-row tree.
- **HC norm.** `specialised::body<norm,0/1,2560,4>`, two launches (`OWNRT_EXPERTS_V2` guard form).
  - Stage 0: 320 items. `partial[row][c]` = the 32-leaf adjacent subtree of x² over elements c·32..c·32+31.
  - Stage 1: 2,560 items of 4 elements. Each item computes `inv = detmath::rsqrt(upper(partial[row], 80)/2560 + 1e-6f)`.
    `upper()` is an adjacent tree with odd-tail `+ 0.f` nodes. Then `y = (x·inv)·(gain[k] + unit)`.
  - The guard is the same in both stages: inactive or error → nothing written; position out of range → item 0 sets
    the error.
- **HC combine.** `CombineFast`, F32: 2,560 items of 4 elements. `gate = 2·sigmoid(inject[h]/4)`;
  `streams[h][k] = streams[h][k] + branch[k]·gate`, in place. The guard is inactive or error only; there is no
  position check.

## Kernel bench (one card, 0000:43:00.0)

- **Data.**
  - Real weights: every HC block of both ranks from the GGUF (97 blocks: blk.0–47 hc.a / hc.f and the final HC).
  - Real activations, and the engine's own outputs for the same step: the stage-overhead finish dumps (`d2-r0-full`,
    `d1-r1-full`). The norm vectors, act vectors, streams, and each norm's actual combine inputs (`attention` or
    `moe`, and `inject`).
  - [extract.py](extract.py) builds a 1.29 GB pack.
- **Exactness** ([results/bench-shipped-c43.json](results/bench-shipped-c43.json)).
  - The engine kernels run in the bench reproduce the dumped engine outputs bit for bit: low, inject and gate, on all
    97 blocks.
  - Every candidate equals the engine kernel bit for bit on every block: norm outputs and scratch partials on two real
    inputs per block, and streams, norm output and partials for the fused combine.
  - The guard cases match: inactive, error set, and position out of range.
  - The shipped engine kernels (`hc_kernels::norm_row`, `dense_v2::bf16_multi_static`) are themselves in the bench.
- **Timing.** Per block, the chain [combine →] norm → low(+inject) → act → gate in layer order with that block's own
  weights (13.2 MB per block, cold), queued behind a busy kernel. Configurations interleaved, 4 rounds × 2 passes.
  Device event µs, medians:

  | site | engine | best exact candidate | shipped |
  | --- | ---: | ---: | ---: |
  | HC norm (2 launches → 1) | 6.04–6.35 | 4.48–4.58 | `norm1` 4.58–4.69 |
  | combine + norm (3 launches → 1) | 9.38 | 5.42 | `cnorm` 5.52 |
  | HC low + inject | 14.48–14.58 | 13.65–13.75 | `lowsel` 13.75 |
  | final HC low | 13.65–15.9 (noisy, one sample per pass) | 13.1–13.2 | 13.12 |
  | HC gate | 13.12–13.23 | 12.92–13.02 (noise) | not changed |

  - Closed, equal or slower than the engine (same table, [results/bench-full4-c43.json](results/bench-full4-c43.json)):
    - low: `bf16_multi<1,4>` / `<1,10>` / `<1,20>`, 32- and 64-item groups, two rows per subgroup, SIMD16 pairs
      (`bf16_split`), prefetch of the next batches or the whole row to L1/L2/L3 (whole-row prefetch: 17 µs);
    - gate: 1, 2, 4, 8 or 16 rows per subgroup with every load first, 64/128/256-item groups, static select.
  - Under production-like context between blocks (a 100 µs ALU-bound kernel, or a 96 MB weight read) the engine and
    candidate times move by at most 0.7 µs and keep their order.

## Engine change (default off)

`OWNRT_HC_KERNELS` (`1` = `norm1,lowsel,cnorm`, or a comma list). Seven files in `engine/src`
([engine-hc-kernels.patch](engine-hc-kernels.patch), 366 lines):
- **`stage2/packet194-expert-diet-engine/hc_kernels.hpp` (new):** the flag, `upper80` (the engine's `upper(p, 80)` by
  one subgroup), and `norm_row<COMBINE>` (norm, or combine + norm, one work-group per stream row).
- **`specialised_submit.cpp` / `.hpp`:** `norm1` in `submit` for admitted shapes (4 × 2560 rows, F32 gain, F32
  activations, one token row); `submit_combine_norm`; `hc_norm_admitted`.
- **`stage2/packet6-kopt/dense_v2.hpp`, `kernels.cpp`:** `bf16_multi_static`; `lowsel` takes it at the
  `bf16_multi<1,8>` sites (`<1,10>`, the same per-row arithmetic).
- **`dense-packed-block/.../generic_engine.hpp`:** the `cnorm` pairing.
  - Admitted: an HC norm site and the launch directly before it on the same card, which must be the `hc_combine`
    writing the norm's input in place.
  - Both prepared specs must be the paths the kernel reproduces: CombineFast (F32, implementation 1,
    `OWNRT_SIMPLE_FAST` on) and the `specialised` norm.
  - Also here: `gsq_combine_norm`, and the record `hc-kernels.json` (norm sites, admitted, pairs).
- **`main.cpp`:** two includes and two `execute_site` hooks, the same pattern as `gsq_mix_follower`. Merged on top of
  the prefill agent's commit in `c1c3012e9`.
- **Controller-read rule** (`3d85cdb20`, `generic_engine.hpp`): no pair may move the combine's write past a host read
  of `streams`. Rank 1 exports `streams` to the draft after layer 47; pipeline stages and `--retain-steps` read at
  layer ends. So the combine before `final.norm` is never paired, and pipeline or retained steps admit no pairs.

## Gates (rank harness: the prefill-speed rank drivers; [run_phase.sh](run_phase.sh), [compare.sh](compare.sh))

Binary r2 `59d29a4a362e` ([receipt](results/engine-build-r2-receipt.json)), built from the private copy of
`engine/src` at `83abad01a` plus the patch. Context 65536, F32, r7 launch environment. Prompt 128 rows, then 64
decode halves. Kernel log clean before every phase and after every arm (26 arms); no exchange timeouts.

- **G1, one card (0000:43:00.0), flags-on against flags-off**
  ([logs/g1-compare.txt](logs/g1-compare.txt), [results/g1-halves.json](results/g1-halves.json)):
  - rank 1, prompt token by token: full state 1079/1079 and 64 tokens, in two A/B pairs and across pairs;
  - rank 1, batched prefill (256-row chunks) + second request (`sp=64`): both requests 1079/1079, reset inventories
    28/28 each, tokens equal;
  - rank 0, patterns `h`, `hmcn`, `m`: 1029/1029 target, 71/71 draft, 64 draft tokens;
  - rank 0, batched + `sp=64`: both requests equal, inventories 116/116 each.
- **G2, four cards (tptsxqckf decode set: `full` + `ep,rd`; rank 1 on 23+47, rank 0 on 23+27)**
  ([logs/g2-compare.txt](logs/g2-compare.txt), [results/g2-halves.json](results/g2-halves.json)):
  - TP against one card, flags on and flags off: rank 1 1079/1079 + tokens; rank 0 1029/1029 + 71/71 draft + draft
    tokens;
  - TP flags-on against flags-off: equal in both pairs;
  - card 1 equals card 0 in every TP run (728 / 670 buffers).
- **Half medians.**

  | arm | flags off (ms) | flags on (ms) | change |
  | --- | ---: | ---: | ---: |
  | one card, rank 1 | 12.31 / 12.36 | 12.01 / 11.95 | −0.35 |
  | one card, rank 1, batched + sp | 12.34 | 12.01 | −0.33 |
  | one card, rank 0 h | 10.80 / 10.80 | 10.465 / 10.46 | −0.34 |
  | one card, rank 0 hmcn / m / sp | 10.80 / 10.80 / 10.84 | 10.44 / 10.47 / 10.49 | −0.36 / −0.34 / −0.34 |
  | four cards, rank 1 | 9.507 / 9.503 | 9.120 / 9.121 | **−0.385 (−4.0%)** |
  | four cards, rank 0 | 8.604 / 8.594 | 8.283 / 8.281 | **−0.317 (−3.7%)** |

  The p10–p90 spread is about ±0.04 ms per arm.

## End gate (fresh four-card lab servers, [suite/](suite/))

- **Tooling.** A copy of `research/tp/prefill-host-2026-10-30`'s suite. Port 18173, `sc117-tp-svc-hk-*` units.
  - `arm_env.py` adds `tptsxqckhhc` = `tptsxqckh` + `OWNRT_HC_KERNELS=1`.
  - The lab adapter's `TP_KEYS` also forwards `OWNRT_HC_KERNELS`; without it B would silently equal A.
  - Verified three ways: B's unit environment (`logs/arm-*-unit-env.txt`), both rank processes' `/proc` environment,
    and the ranks' `hc-kernels.json` admission counts.
- **Attempt 1** (receipt `63c4a26a22d6`, [results/attempt1-63c4a26a22d6/](suite/results/attempt1-63c4a26a22d6/)):
  - A r1: 13/13, suite complete.
  - B r1: halted at the startup gate, 11/13. code-review-258 and code-review-259 had equal tokens and equal persistent
    state, but the draft guesses differed.
  - Cause: the `final.norm` pair, described above.
- **Attempt 2** (receipt `17f5f49ff010`; [results/suite/summary.json](suite/results/suite/summary.json),
  [results/pairs-endgate.json](suite/results/pairs-endgate.json),
  [results/hitcycle-endgate.json](suite/results/hitcycle-endgate.json)): the table at the top.
  - The 3,490-token TTFT probe is the same in A and B (7.05–7.08 s).
  - The kernel log stayed clean on every server.
- **Raw evidence:** `/mnt/raid-models/ownrt-experiment-archives/2026-10-30/hc-kernels-endgate` (servers and
  export-check runs, `.sha256` verified). Engine builds: `.../engine-builds/hc-kernels-engine-build-merged{,2}`.

## Export check (rank 1's draft-input rows; [logs/x1-compare.txt](logs/x1-compare.txt), [logs/x0-compare.txt](logs/x0-compare.txt))

The lab driver copy records two sets of rows as SHA-256 per row:
- the shared reverse region after every half (the layer-47 `streams` export);
- each batched chunk's reverse rows in the prefill file.

Its `compare` requires them equal. One card (43), with the ten tptsxqckh prefill flags (extra `ph`), 128 prompt rows,
then 64 halves:

| check | binary | result |
| --- | --- | --- |
| fixed, flags on vs off, token by token | `17f5f49ff010` | 1079/1079 state, 64 tokens, 192/192 exported rows equal |
| fixed, flags on vs off, batched + second request | `17f5f49ff010` | both requests equal; exported rows 192 + 128 equal |
| negative control, flags on vs fixed flags off | `63c4a26a22d6` | state and tokens equal; exported rows differ from row 0 (check fails as it should) |

The batched compare's `ones` invariant (`prefill:moe-ones` all 1.0) fails in the second request's inventory with flags
**off and on alike**, under the `ph` prefill flags. It is pre-existing, outside the HC kernels, and was passed to the
coordinator.

## Files

- **Bench:** [hc_kernels.hpp](hc_kernels.hpp) (candidates), [hc_bench.cpp](hc_bench.cpp), [build.sh](build.sh),
  [run.sh](run.sh), [extract.py](extract.py).
- **Results:** `results/bench-*-c43.json`.
  - Final: `bench-shipped-c43.json` (shipped kernels) and `bench-full4-c43.json` (all candidates).
  - `bench-full*`: successive candidate sets. In `bench-full3` the engine-combine replica loaded the error word on
    every lane, so its time was too high; fixed in `bench-full4`.
- **Harness:** [run_phase.sh](run_phase.sh) (copy of fixed-cost: one-card arms on 43, the `hk=` extra, bundle
  cleanup), [compare.sh](compare.sh), [halves.py](halves.py), [klog.py](klog.py); `logs/` (phases s1, s2, g1, g2).
- **Raw runs** (state bundles removed after each arm; `state.json` hashes kept):
  `/mnt/raid-models/ownrt-experiment-archives/2026-10-30/hc-kernels-runs` (+ `.sha256`).
- **End gate:** [suite/](suite/); export check: [drivers/](drivers/); logs x0, x1.
- **Engine change:** merged in `c1c3012e9` and `3d85cdb20`. [engine-hc-kernels.patch](engine-hc-kernels.patch) is the
  original patch against `83abad01a`, without the controller-read fix. Smoke s1 (r1 binary) showed 0 combine pairs
  because the admission counted inputs without the control buffers; r2 fixed the indices before any gate ran.
