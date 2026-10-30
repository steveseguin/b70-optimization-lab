# Four-card fixed cost, round 2: the draft step and runtime-indexed kernel arguments (2026-10-30)

**Question.** After the HC kernels, four-card decode runs at 87.63 / 87.76 tok/s (hit cycle 9.33–9.35 ms). Rank 0 paces
the hit cycle: its half (8.28 ms) plus the MTP draft step (1.07–1.09 ms) against rank 1's 9.12 ms half. Which exact levers
take time off the draft step and off both ranks' halves?

**Answer. Fresh four-card lab servers at 65536, A/B/A/B: 87.77 / 87.64 → 92.51 / 92.75 tok/s (mean of medians 87.71 →
92.63, +5.6%), every output equal to B19, hit cycle 9.37 → 8.84 ms.** B is faster on 12/12 prompts in all four
cross-pairs (1.051–1.060). The binary is the merged build m2 (`dddf5cf0e067`); its engine change is
[engine-fixed-cost-2.patch](engine-fixed-cost-2.patch) against `979462f7c`, not yet applied to `engine/src` (see Merge).
- Two default-off flags, both bitwise exact on every gate run so far:
  - `OWNRT_DRAFT_FAST=1` (`inj,norm,merge,cnorm,gath`): the draft step's small launches, rewritten or merged with the
    per-row arithmetic unchanged. One card: draft device span **1207 → 1120 µs (−87 µs)**, draft wall 1.305 → 1.225 ms.
  - `OWNRT_TARGET_FAST=1` (`ssel,hcg,kptr,bptr,gdnr,ngop,moec`): kernels that read their bindings through a captured
    array at a runtime index (the array then lives in private memory) read them by static index or as host-resolved
    pointers instead (`ssel,hcg,kptr,bptr,gdnr,ngop`), and the layer's two moe launches join the HC combine+norm launch
    (`moec`). One card, device busy per half: the first four **−358 µs** (rank 0) / **−332 µs** (rank 1); the last three
    a further **−171 µs** on each rank. Half wall with the first four: 10.406 → 10.044 ms (rank 0), 11.869 → 11.556 ms
    (rank 1).
- Closed: merging the draft's small weight GEMVs into one launch (the next big weight-streaming kernel gets 14–17 µs
  slower), the HC gate+mix fusion in the draft, and two rows per subgroup for single-input-row GEMVs.

## In plain words

- **Many of the engine's kernels were paying a hidden toll at the start of every launch.** A kernel that picks its
  matrix or its buffer pointers from a small list by a number known only at run time makes the GPU keep that whole list
  in slow per-thread memory and fetch from it before it can start reading weights. The HC agent found this in one kernel
  (0.8 µs per launch). The same pattern was in the split BF16 GEMVs (router, GDN a+b, QSA iq+ik), the HC gate, the
  routed expert kernels, the shared-expert down projection, the route and the merged expert check. Fixing it, with the
  same arithmetic, takes about a third of a millisecond off every half on one card.
- **The draft step lost about 7% of its time** (87 µs of 1.2 ms on one card) from faster norms, two projections in one
  kernel, three fused small launches and a gather that had been running 25,600 work-items through a generic slow path.
- **Fewer launches is not automatically faster.** Merging the draft's four QSA projections into one launch, or the router
  and shared-expert projections, made the next large weight-streaming kernel (attention output, expert gate+up) 14–17 µs
  slower, so the draft got slower overall. Every draft change was therefore judged by the whole draft's device span, not
  by its own site time.

## What was measured, and how

- **Binaries.** Private copy of `engine/src` at `f10c30c4a` (= the HC end-gate sources `3d85cdb20`) under
  `/dev/shm/fc2-2026-10-30`, built with `engine/build.py` (CPU only, niced, cores 8–15/24–31). Lab builds r1–r8; the
  gated binary is **r8 `36a04860f0fe`** ([receipt](../../../engine/receipts/36a04860f0fe.json), sources pinned to the lab
  copy). Every build's receipt was checked against the sources it compiled (268/268 hashes).
- **Rank harness.** The prefill-speed rank drivers through [run_phase.sh](run_phase.sh) (copy of the HC harness: one-card
  arms on 0000:43:00.0 under `/dev/shm/card43.lock`; four-card rank 1 on 23+47, rank 0 on 23+27), context 65536, F32,
  r7 launch environment, prompt 128 rows token by token, 64 decode halves (rank 0 pattern `h`: 64 speculative hits with
  drafts). New extras: `df=` (`OWNRT_DRAFT_FAST`), `tf=` (`OWNRT_TARGET_FAST`), `ht` (draft host-phase trace).
  [launch_phase.sh](launch_phase.sh) holds the needed card locks with bounded waits.
- **Site traces** (`OWNRT_SITE_TRACE=1`, `--timing launch`, one card only, never under TP): [sites.py](sites.py) gives the
  draft step's device span and per-site times (56 head-on draft phases) and the target half's per-site busy time
  (184 / 120 halves). Device time only.
- **Kernel log** checked (sudo journalctl) before every phase (24 h) and after every arm: no xe/GuC/fault/reset lines.

## Draft step (one card, device span of the head-on draft step, µs)

Baseline 1205–1207 µs in 50 launches (logits 328, qsa.qgate 122, attention output 81, expert gate+up 72, merge
projections 37 + 52, expert down 51, argmax 38, hidden norm 23, gather 21 + 2, …). Four-card harness draft wall
1.088 ms; host trace ([h0](logs/h0.log)): inputs 0.037 ms, issue loop 0.27 ms (overlaps the device), engine wall 1.06 ms,
so the draft is device-bound.

| Token | What | Exact because | Measured |
| --- | --- | --- | --- |
| `norm` | p59 draft norms (one 256-lane tree per row): loads up front, levels 1–16 of the tree by subgroup shuffles, levels 32–128 from the eight subgroup sums, one barrier instead of nine; `merge.embedding_norm` + `merge.hidden_norm` in one launch | same operands added in the same association at every tree node; same rsqrt and output expression | −16 µs alone (t2): merge norms 34.3 → 21.5, HC norms −1.0 to −1.5 each |
| `inj` | HC inject rows (4 × 10240) in the HC low launch (320 × 10240 + act tail), both `p59::Dense<10240,…,1,4>` | the same static `chain()`, subgroup tree and 4-part tree per row | hc.a: 17.0 + 7.8 → 17.0; hc.f: 16.7 + 7.4 → 17.6 (t3) |
| `merge` | `merge.embedding_projected` and `merge.projected` (+ merge_add tail) in one launch, two weight rows per subgroup, each chunk of the five input rows loaded once | every output keeps `Dense<2560,…,1,1>`'s lane chunks, adds and tree; the tail adds the stored BF16 values | 37 + 52 → 68 µs (one row per subgroup: 85; four rows: 98) |
| `cnorm` | `ffn.combine` (generic hc_combine, BF16 streams, guarded) fused into `final.norm`'s launch (head-on steps only) | per element the combine's expression and guard; the norm reads the stored BF16 values; the draft's streams have no host readback | combine 11.3 + final norm 7.6 → 13.2 (−6.7 µs span) |
| `gath` | `expert_gather` (SimpleNew: 25,600 items through the typed-view body, then one check item) as one launch, 8 elements per item; group 0 runs the check after a barrier | same guard, descriptors, validity flags, element expression `bf16(widen(x))` and fail condition | 23.9 → 5.2 µs |
| **all five** (r8) | | | **1207 → 1120 µs (−87)**; 50 → 44 launches |

Closed (measured, exact, slower; code kept in [patches/lab-all-tokens-r6.patch](patches/lab-all-tokens-r6.patch)):

| Token | What | Result |
| --- | --- | --- |
| `qkv` | qsa.k/v/iq/ik (same input) in one launch | the fused launch 25.6 vs 29.6 µs, but the attention output GEMV 81 → 98 µs: span **+15 µs** |
| `shx` | router + shared-expert gate/up (paired, product tail) + shared router gate in one launch | fused 27.6 vs 33.1 µs, expert gate+up 72 → 86 µs: span **+8.7 µs** |
| `gmix` | HC gate (10240 × 320) with the HC mix in its epilogue, four stream rows per subgroup | gate+mix 32 µs vs 25 + 6.4: span **+3.8 µs** (as the DO-NOT-REPEAT HC gate+mix row) |
| `rows` | two rows per subgroup for qsa.qgate and the HC gates, FP8 experts 2 (gate+up) / 4 (down) rows | qgate +3, HC gates +7 each, down +4.5 µs |
| `att` | attention output + combine tail, two rows per work-group | 81 → 97 µs |
| `inj` with two rows per group | | +4 µs per HC low |

## Target halves: runtime-indexed kernel arguments (`OWNRT_TARGET_FAST`)

The HC agent found that `dense_v2::bf16_multi` picking its matrix by a runtime index into the captured descriptor array
keeps the array in private memory (0.8 µs per launch). A read-only audit (Explore agent) listed the other decode kernels
with the same pattern. Each fix below changes only how a kernel finds its pointers; every row's arithmetic and every
store are the same.

| Token | Kernel | Sites per half (r0 / r1) | One card, rank 0 site busy per half |
| --- | --- | --- | --- |
| `ssel` | `bf16_split_static`: static select in the `bf16split` GEMV | router + shared gate, GDN a+b, QSA iq+ik, ple.key (47 / 51) | router −17.5, gdn.a −8.1, qsa.iq −4.3, ple.key −2.8 µs (−49 total, t5) |
| `hcg` | `bf16_multi_static<2,4>` for the HC gate (`hcgate`) | hc.a/f.gate (46 / 50) | hc.a.gate −28, hc.f.gate −25 µs (the HC bench saw no change; the engine does) |
| `kptr` | kopt routed block-rows, paired block-rows, IQ4_NL packed, Q8 packed: binding pointers resolved on the host | routed experts, shared-expert down | expsgate −46, expsup −63, shexpdown −21 µs; **non-routed** block-rows launches (shared-expert gate/up, QSA k/v) got 30–100 µs slower with host pointers, so they keep the array |
| `bptr` | packet18 `RouteFast2` (route + gather descriptors) and the merged expert `StatusFast` read host-resolved views (`BoundIO`) | route, expsdown.check (23 / 25 each) | route −25, expsdown.check −13 µs |
| **all four** (r8, t6) | | | **rank 0 −358 µs, rank 1 −332 µs** device busy per half |
| `gdnr` | round2 GDN recurrence: the state slot chosen by a uniform branch between two static slots instead of `a.b(r?7:5,…)` | gdn.recurrence (36 / 36) | recurrence −21.7, total −19 µs (t7, on top of the four) |
| `ngop` | the generic ng kernel launched per op with `Shape.op` fixed at compile time (conv, gated norm, QSA prepare, append/pool), so `group()`'s op branches and slot selects fold to constants | 48 / 50 | gdn.gated −44, gdn.conv −25, QSA prepare/pool −8, neighbours −18: **−108 µs** |
| `moec` | a cnorm pair whose combine reads the moe_combine launched just before it also absorbs that site's mixture epilogue (unguarded, WG 0 writes it) and moe_combine (its guard and position check, then `(0 + mix·one) + shexp·σ(gate)`, WG 0 writes it) | 21 / 24 pairs (42 / 48 launches) | moe −80, the fused norm +40: −37 µs |
| **all seven** (r9, t7) | | | rank 0 −171 µs, rank 1 −171 µs device busy per half on top of the four |

Sites the fixes do not touch also got 8–26 µs faster per half (gdn.qkv, attention output, gdn.z): the opposite of the
draft's launch-merge effect.

## Gates

**G1, one card (0000:43:00.0), flags on (`df=1,tf=1` on rank 0, `tf=1` on rank 1) against flags off** (r8,
[logs/g1-compare.txt](logs/g1-compare.txt), [results/g1-halves.json](results/g1-halves.json)): all equal.
- Rank 0: 1029/1029 target buffers, 71/71 draft buffers and all 64 draft tokens, in patterns `h`, `hmcn` and `m`, and
  both requests of the batched two-request case (`sp=64`) with their reset inventories.
- Rank 1: 1079/1079 buffers, 64 tokens and the exported draft-input rows (192, the layer-47 `streams` export), token by
  token and batched + second request (192 + 128 exported rows), with and without the tptsxqckh prefill flags.
- The `prefill:moe-ones` inventory check uses the exact-pattern checker of `prefill-draft-batch-2026-10-30`
  ([compare_driver.py](compare_driver.py)); with the older all-ones form the second request under the prefill flags
  failed identically with flags off and on.

| one card (A/B/A/B) | flags off | flags on | change |
| --- | --- | --- | --- |
| rank 0 half (h) | 10.406 / 10.405 ms | 10.043 / 10.045 ms | **−0.362 ms (−3.5%)** |
| rank 0 draft | 1.305 / 1.306 ms | 1.222 / 1.229 ms | −0.080 ms |
| rank 1 half | 11.859 / 11.878 ms | 11.562 / 11.549 ms | **−0.313 ms (−2.6%)** |

**Merge onto `979462f7c`** (the prompt-reading agent's batched KV-only draft prompt rows, which also touch mtp.hpp and
adapter.cpp): 3-way per file (`git merge-file`, base `f10c30c4a`), no conflicts, in the private tree
`/dev/shm/fc2-2026-10-30/merged-979462f7c`. Their draft-batch path runs its own kernels over the KV-only prompt sites;
`OWNRT_DRAFT_FAST` acts only in `DraftRuntime::compute()`. Merged build **m2 `dddf5cf0e067`**
([receipt](results/engine-receipt-dddf5cf0e067.json), [build receipt](results/build-m2-build-receipt.json), 269 compiled
sources). The complete change is [engine-fixed-cost-2.patch](engine-fixed-cost-2.patch) against `979462f7c` (13 files,
[list](engine-fixed-cost-2.files); `git apply --check` clean). Writing it into the shared `engine/src` was refused by the
session's permission system, so it is not applied; [verify_receipt.py](verify_receipt.py) checks that a tree reproduces all
269 compiled-source hashes of m2 (the private tree: 0 differ).

**G3, one card (0000:43:00.0), on m2, flags on against flags off** ([logs/g3-compare.txt](logs/g3-compare.txt),
[results/g3-halves.json](results/g3-halves.json)): all equal, 16 arms rc 0, kernel log clean.
- Rank 0: 1029/1029 target + 71/71 draft buffers + draft tokens in `h`, `hmcn`, `m`; the batched two-request case both
  plain (`sp=64`) and with the tptsxqckh prompt flags + `OWNRT_DRAFT_CHUNK_BATCH=1` + `--draft-chunk` (both requests,
  reset inventories, exact ones checks). The rank's recorded environment shows `OWNRT_DRAFT_CHUNK_BATCH`,
  `OWNRT_DRAFT_FAST` and `OWNRT_TARGET_FAST` set.
- Rank 1: 1079/1079 + tokens + exported draft-input rows (192 + 128), token by token and batched + second request, with
  and without the prompt flags + draft batch.

| one card, m2 | flags off | flags on | change |
| --- | --- | --- | --- |
| rank 0 half (h) | 10.420 / 10.394 / 10.422 / 10.430 / 10.421 ms | 9.885 / 9.844 / 9.883 / 9.899 / 9.870 ms | **−0.54 ms (−5.2%)** |
| rank 0 draft | 1.317 ms | 1.227 ms | −0.09 ms |
| rank 1 half | 11.868 / 11.875 / 11.871 ms | 11.341 / 11.339 / 11.340 ms | **−0.53 ms (−4.5%)** |

**G2, four cards, on m2** (decode set `full` + `ep,rd,hk=1`; rank 1 on 23+47, rank 0 on 23+27; [logs/g4-compare.txt](logs/g4-compare.txt),
[results/g4-halves.json](results/g4-halves.json)): all equal. TP flags-on vs flags-off in both A/B pairs; TP vs one card
(G3 arms) with flags off and with flags on; card 1 equals card 0 in every TP run (728 / 670 buffers); no exchange
timeouts.

| four cards, m2 (A/B/A/B) | flags off | flags on | change |
| --- | --- | --- | --- |
| rank 1 half | 9.114 / 9.099 ms | 8.654 / 8.688 ms | **−0.44 ms (−4.8%)** |
| rank 0 speculative half | 8.273 / 8.271 ms | 7.852 / 7.848 ms | **−0.42 ms (−5.1%)** |
| rank 0 draft | 1.082 / 1.085 ms | 0.989 / 0.982 ms | −0.10 ms |
| rank 0 half + draft | 9.36 ms | 8.84 ms | −0.52 ms |

Rank 0 (half + draft) still paces the hit cycle: 8.84 against rank 1's 8.67 ms.

**End gate** on m2: fresh four-card lab servers at 65536 ([suite/](suite/), copies of the HC / draft-batch suite tooling),
A = `tptsxqckhcb` (tptsxqckh + `OWNRT_HC_KERNELS=1` + `OWNRT_DRAFT_CHUNK_BATCH=1`, the prompt-reading agent's arm, identical
environment), B = `fc2` = A + `OWNRT_DRAFT_FAST=1` + `OWNRT_TARGET_FAST=1`, order A/B/A/B, rank 0 on 23:00.0 + 27:00.0,
rank 1 on 43:00.0 + 47:00.0, engine receipt [dddf5cf0e067](results/engine-receipt-dddf5cf0e067.json).
- The lab adapter's `TP_KEYS` forwards `OWNRT_DRAFT_FAST`, `OWNRT_TARGET_FAST` and `OWNRT_DRAFT_CHUNK_BATCH`; both rank
  processes of B r1 carried all of them ([logs/rank-env-fc2-r1.txt](suite/logs/rank-env-fc2-r1.txt), from
  `/proc/<pid>/environ`), and the unit environments are in `suite/logs/arm-*-unit-env.txt`.
- Every server passed its 13-case startup batched-prefill gate (13/13), the F32 self-test and state oracles, then served
  the 12-prompt suite (one cold request each, 512 cap, greedy) and the 3,490-token TTFT request. Kernel log clean through
  the chain.

| server | median tok/s | mean | range | outputs | TTFT 3,490 | hit cycle | miss interval | rank 0 half + draft | rank 1 half |
| --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| A r1 | 87.77 | 88.06 | 84.89–92.52 | = B19 | 6.60 s | 9.374 ms | 17.83 ms | 8.293 + 1.069 | 9.189 |
| **B r1** | **92.51** | 92.96 | 89.20–97.72 | = B19 | 6.57 s | **8.838 ms** | 16.89 ms | 7.875 + 0.967 | 8.740 |
| A r2 | 87.64 | 88.01 | 84.87–92.58 | = B19 | 6.59 s | 9.369 ms | 17.80 ms | 8.294 + 1.069 | 9.181 |
| **B r2** | **92.75** | 93.11 | 89.50–97.98 | = B19 | 6.55 s | **8.849 ms** | 16.89 ms | 7.868 + 0.965 | 8.741 |

- Mean of medians 87.705 → 92.627 tok/s (**+5.61%**); per prompt B/A 1.051–1.060 in every cross-pair, 12/12 faster
  ([results/pairs-endgate.json](suite/results/pairs-endgate.json), [results/suite/summary.json](suite/results/suite/summary.json)).
- Outputs: ids, sha256, MTP guesses (5,954) and hits (4,533, pooled acceptance 0.7613) identical on all four servers and
  equal to B19.
- Hit cycle ([results/hitcycle-endgate.json](suite/results/hitcycle-endgate.json), the 3,490-token request, 40 hits and
  23 misses per server): −0.53 ms (−5.7%); a miss −0.93 ms. Rank 0's path 9.37 → 8.85 ms, rank 1's 9.25 → 8.81 ms: the
  two stages are now within 0.05 ms, so the next cut must come off both.
- Raw server directories (1,270 files, sha256-verified):
  `/mnt/raid-models/ownrt-experiment-archives/2026-10-30/fixed-cost-2-endgate`.

## Incidents

None on the device. Kernel log clean before every phase, after every arm and through the end-gate chain. Host-side:
- build r8's first attempt failed to compile (a new struct inserted inside another);
- the r1 smoke's gmix/cnorm admissions were refused by plan-arity checks (the planner appends `active`/`error` to every
  launch's inputs), fixed in r3;
- `run_phase.sh` was edited while phase t7 was running it: all seven arms had been parsed and ran, the lines after the arm
  loop then misparsed (a syntax error instead of the "phase done" line). No effect on the arms;
- `archive_runs.sh` first version would have removed the /dev/shm copies even after a failed verification (`set -e`
  does not stop on an `&&` list); the archive verified (re-checked: 1,636/1,636), and the script now stops before removal;
- writing the merged engine files into the shared `engine/src` was refused by the session's permission system; the
  change is kept as a patch with a hash checker (Merge section).

## Files

- Engine change: [engine-fixed-cost-2.patch](engine-fixed-cost-2.patch) (against `979462f7c`). Default off:
  `stage2/packet194-expert-diet-engine/draft_fast.hpp` (new), `target_fast.hpp` (new),
  `gsq-rco-iq3s/.../native-src/mtp.hpp` (fast override commands, `prepare_fast()`), `stage2/packet6-kopt/dense_v2.hpp`
  (`bf16_split_static`), `stage2/packet6-kopt/kernels.cpp` (`ssel`, `hcg`, `kptr`), `stage2/packet194-expert-diet-engine/
  adapter.cpp` (`RouteFast2B`, `StatusFastB`, `BoundIO`), `round2_submit.cpp` (`gdnr`), `native.cpp` (`ngop`),
  `hc_kernels.hpp` / `specialised_submit.*` / `generic_engine.hpp` / `main.cpp` (`moec`).
- Harness: [run_phase.sh](run_phase.sh), [launch_phase.sh](launch_phase.sh), [compare.sh](compare.sh),
  [compare_driver.py](compare_driver.py), [halves.py](halves.py), [sites.py](sites.py), [klog.py](klog.py),
  [archive_runs.sh](archive_runs.sh), [drivers/](drivers/); end gate tooling [suite/](suite/) (arm `fc2`).
- Results: [results/](results/) (`t*-sites.json` per trace comparison, `g1-halves.json`); logs: [logs/](logs/).
- Raw runs (sha256 lists beside them): `/mnt/raid-models/ownrt-experiment-archives/2026-10-30/fixed-cost-2-traces`
  (h0, s1, t1–t6; 1,636 files), `.../fixed-cost-2-gates` (G1, G3, G2 = g4, t7, x1, x3; 2,596 files), `.../fixed-cost-2-endgate`
  (1,270 files), `.../engine-builds/fixed-cost-2-r8`.
