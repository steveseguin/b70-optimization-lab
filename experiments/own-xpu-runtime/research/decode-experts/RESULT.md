# Decode routed experts on rank 1: exact kernel work (2026-10-26)

Lab copy `/dev/shm/ownrt-lab-dexp/engine` (the brief's `/dev/shm/ownrt-lab-experts` was already in use by the
expert-grouped-prefill agent, so this lab used its own directory). Base: canonical `engine/src` as of 07:25 plus the
QSA-select change synced at 07:48 (`select_fast.hpp`, `specialised_submit.cpp`). Every new path is behind
`OWNRT_EXPERTS_V2` (default off). Exactness, timing and the device rules are described below.

## Result

| | Reference | `OWNRT_EXPERTS_V2=1` | Change |
|---|---:|---:|---:|
| Rank-1 half, 4096-row prompt: driver `half_ms` median, clean runs | 16.74 ms (n=3) | 15.53 ms (n=2) | −1.21 ms (−7.2%) |
| Same runs: engine `half_completion_ms` median | 16.68 ms | 15.48 ms | −1.20 ms |
| Rank-1 half, 300-row prompt: driver / engine median | 16.36 / 16.30 ms | 15.05 / 14.99 ms | −1.31 ms (−8.0%) |
| Device span per half (`OWNRT_DECODE_PROFILE=3`, 4096) | 16.19 ms | 14.98 ms | −1.21 ms (−7.4%) |

- Clean runs are those with an enqueue-loop median of at most 3.8 ms.
- Contended runs: reference f2-ref-3 17.47 ms; final f2-new-1 15.99, f2-new-3 15.73 and f2-new-5 15.79 ms.
- Every run, interleaved: `results.json` → `timing`.

Exactness: every run is bitwise identical to the reference: 1032 buffers compared, `differ_count` 0, equal tokens.
That covers the final binary at a 4096-row prompt (×5), at a 300-row prompt, in the profile run and on the
default-off path, plus every intermediate lever on its way in.

## Device incident (2026-10-26 08:50:29)

- Card 27 logged a GPU page fault and a bcs engine reset, and the live service halted itself.
- The faulting process was pid 294276, run `x10-warm` of the expert-grouped-prefill lab (`/dev/shm/ownrt-lab-experts`).
  It was not from this lab. This lab's run `f2-new-4` (pid 292295) had exited at 08:50:26.
- This lab's per-run kernel-log check only scans each run's own window. It therefore did not see the fault, and the
  queued sequence started two more runs after it:
  - `f2-ref-4`, 08:51:22–08:52:06;
  - `f2-new-5`, 08:52:07–08:52:49.

  Both finished with rc 0, held only renderD131, and logged no new fault lines.
- Device work stopped on the coordinator's order at 08:53, with a HALT file set in the lab.
- None of the results depend on those two runs. The clean-run medians use `f2-ref-1/2/4` and `f2-new-2/4`. Dropping
  `f2-ref-4` gives reference medians of 16.74 ms (driver) and 16.68 ms (engine), unchanged.

## Shapes (rank 1, split 24, layers 24–47)

All layers have 512 experts and top-10 routing. Gate and up are 640 rows × 2560 columns per expert; down is
2560 rows × 640 columns. Bytes are counted for the 10 selected experts per site.

| Site | Format | Layers | MB/site | Read floor (537 GB/s) | Kernel (reference) |
|---|---|---:|---:|---:|---|
| expsdown | IQ4_NL | 22 | 9.22 | 17.2 µs | kopt `MultiplyBlockRows<2>` |
| expsdown | Q2_0 | 2 (30, 36) | 4.61 | 8.6 µs | gsqn `PackedRowsOperation<42,4>` |
| expsgate/up | IQ3_XXS | 9 | 6.27 | 11.7 µs | iq3block `BlockRowsOperation<4>` |
| expsgate/up | IQ3_S | 8 | 7.04 | 13.1 µs | kopt `MultiplyBlockRows<4>` |
| expsgate/up | IQ2_S | 6 | 5.25 | 9.8 µs | kopt `MultiplyBlockRows<4>` |
| expsgate/up | IQ4_XS | 1 (47) | 8.70 | 16.2 µs | gsqn `PackedRowsOperation<23,4>` |

Rank 1 reads 518 MB of routed-expert weights per token, which is 0.96 ms at 537 GB/s.

A trivial reader kernel touching the same bytes cold (microbench, `kbench/iq4nl_stream.cpp`, `iq3xxs_stream.cpp`) takes
27.4 µs (IQ4_NL down) and 19.0 µs (IQ3_XXS gate). That is about 335 GB/s, so the practical floor for one ~30 µs
expert launch is about 1.6× the 537 GB/s figure.

## Per-site device time, µs per token (profile runs `refprof-a` → `f2-prof`)

| Site | n | Reference | Final | Per site, before → after |
|---|---:|---:|---:|---|
| routed IQ4_NL down | 22 | 1333 | 826 | 60.6 → 37.6 |
| routed IQ3_XXS gate+up | 18 | 1084 | 1076 | 60.2 → 59.8 (no exact win found) |
| routed IQ3_S gate+up | 16 | 580 | 573 | 36.2 → 35.8 (no exact win found) |
| routed IQ2_S gate+up | 12 | 385 | 379 | 32.1 → 31.6 (no exact win found) |
| routed IQ4_XS gate+up | 2 | 211 | 104 | 105.7 → 52.0 |
| routed Q2_0 down | 2 | 114 | 58 | 56.9 → 28.9 |
| **routed GEMV total** | | **3706** | **3016** | **−691** |
| route | 24 | 361 | 293 | 15.0 → 12.2 |
| expert_gather | 24 | 182 | 101 | 7.6 → 4.2 |
| check_status | 24 | 170 | 57 | 7.1 → 2.4 |
| moe_combine (2 launches) | 24 | 111 | 100 | 4.6 → 4.2 |
| norm (specialised body) | 49 | 395 | 308 | 8.1 → 6.3 |
| hc_combine (CombineFast) | 48 | 298 | 239 | 6.2 → 5.0 |
| silu_div4 / silu_product / hc_mix (ng element-wise) | 49/48/49 | 183/167/375 | 152/135/326 | |
| **Whole half (busy / span)** | | **16033 / 16187** | **14813 / 14982** | **−1220 / −1205** |

The remaining expert gaps against the measured cold read floor are 37.6 vs 27.4 µs (IQ4_NL) and about 60 vs 19 µs
(IQ3_XXS).

## What changed (all exact; switch tokens of `OWNRT_EXPERTS_V2`)

`OWNRT_EXPERTS_V2=1` turns on every token below. Any other value is a comma list of tokens.

### `iq4nl`: IQ4_NL down with packed logical lanes (`packet6-kopt/kernels.cpp`, `MultiplyIQ4NLPacked`)

- Mapping: work-item `t` of a row owns logical lanes 4t..4t+3 of the engine's mapping (lane l takes columns
  8l+256i). That is one IQ4_NL block per 256-column chunk.
  - The block's 18 bytes are read once, as 5 aligned words. The block parity is fixed per item.
  - The scale is converted once per block.
- Each logical lane keeps its exact sequence: the same `scale*float(level)` values, product then add over its 8
  columns, chunks in order.
- The first two adjacent-pair tree levels, `(l0+l1)+(l2+l3)`, run in registers. The other three levels use shuffles,
  with the same operands in the same order.
- Levels come from a 16-float table in kernel-scope work-group memory (`group_local_memory_for_overwrite`). These are
  the same `float(iq4_level(n))` values.
- Shape: SG16, 2 rows per subgroup, 4 subgroups per work-group.
- `OWNRT_EXPERTS_V2_IQ4NL=0` selects the select-chain form instead: 958 µs, against 830 µs for the table.
- Applies only to decode rows: F32 activations, at most 32 slots, K%64==0. Batched prefill (320 slots) keeps the old
  kernel.

### `q20` and `iq4xs`: GSQ packed rows with packed logical lanes (`additive/packed.hpp`, `PackedLanesOperation`)

- Same idea for the column-interleaved mapping (k = lane + 32i).
  - Q2_0: 8 adjacent lanes per item, so their 2-bit codes are one 16-bit load and the block scale is formed once.
  - IQ4_XS: 4 lanes per item, so the codes are one aligned word and the group factor is formed once.
- Both use SG32.

### `guard`: the active/sticky-error guard read once per subgroup or work-group instead of by every item

- Applies to CombineFast (`hc_combine`), GatherFast (`expert_gather`), RouteFast, and the specialised generic body.
  The specialised body (`norm` and the other specialised classes) uses `CachedGuard`.
- This is the same argument as the attention fix: the value differs only while another item is setting the flag in a
  failing launch, and that request aborts.

### `route`: two-level top-ten selection in RouteFast (`RouteFast2<512,10,true>`)

- Each 32-lane subgroup first takes its own ten best by subgroup arg-max rounds.
- Subgroup 0 then runs the ten rounds over the 160 candidates.
- The order is identical: larger probability bits first, then the lower id. Every top-ten entry is in its subgroup's
  ten best.
- The softmax, outputs and normalisation are RouteFast's code.
- Microbench: 9.8 → 8.4 µs.

### `status`: merged expert status check in one subgroup (`StatusFast`)

The generic form is a 128-lane team with three barriers and a float tree of `(status!=0)`. It sets the error exactly
when some status element is nonzero, so `StatusFast` uses an `any_of_group` instead.

### `ew`: the ng element-wise ops as plain per-item kernels (`native.cpp`)

- Covers activation (`silu_*`), `mix` and `moe_combine`.
- Each item computes `group()`'s expression unchanged, with no team scratch and no barriers.
- The guard is read once per subgroup. An out-of-range position fails once, from item 0.

## Exactness gate

- Reference: an unmodified lab build (canonical plus the profiling deferral, which is inert without
  `OWNRT_DECODE_PROFILE`), binary `7abc6e2f`.
- Every candidate was compared with `tp_rank1_driver.py compare` against a reference run with the same prompt and
  steps (4096-row and 300-row batched prompts, 48 decode steps).
- All candidates matched, both for the final binary and for every intermediate lever: `differ_count` 0 of 1032
  buffers, equal tokens.
- The default-off path of the final binary (`f2-off-1`) is also bitwise equal to the reference.
- Microbenchmarks check each variant bitwise against an exact replica of the engine kernel before timing it.

## Measurement notes

- Rank 1's half is sensitive to host CPU load. The enqueue thread competes with other agents' builds and the live
  service.
  - Contended runs show `enqueue_loop_ms` above 4 ms, against 3.3–3.5 when clean, and add 0.3–0.8 ms to the half.
    Examples: ref-d 17.07 ms, the c4 off path 17.40 ms, f2-ref-3 17.31 ms.
  - So timing uses interleaved reference/candidate runs, and runs are classified by their enqueue median (`med.py`).
- On clean runs the device-span reduction converts about 1:1 into the half.
- An early reading, that a local-accessor kernel costs 1.4 ms of host enqueue time, was host noise.
  - A repeat (`c4lut-a`, enqueue 3.54 ms) showed no penalty.
  - A plain SYCL submit costs 2.5 µs with or without a local accessor (`kbench/submit_cost.cpp`).

## Negative results (exact variants; all bitwise-equal in the microbench, slower or neutral)

Microbench numbers are cold-weight µs per launch, 10 slots.

- **IQ3_XXS** (engine 57). The decomposition (`kbench/iq3xxs_decomp.cpp`) bounds what any reformulation can recover:

  | Variant | µs | Note |
  |---|---:|---|
  | engine | 57 / 52 warm | |
  | without the per-lane index load | 47 | wrong values, bound only |
  | without the sign-word load | 51.5 | wrong values, bound only |
  | without the grid gather | 53.6 | wrong values, bound only |
  | without the x load | 56 | wrong values, bound only |
  | without any load but d | 35 | ALU floor of this formulation |
  | trivial reader of the same bytes | 19 | |

  Exact attempts:
  - packed logical lanes, 4 or 8 lanes per item, SG16/SG32, RI 1–2: 61–93;
  - block-hoisted loads, with or without next-block prefetch: 70–96 (spills at SG32);
  - grid table in local memory: 63–66;
  - uniform index loads: 70–80;
  - index and sign bytes distributed by subgroup shuffle: 106–119.

  The packed kernel is in `kbench/negative-iq3xxs-packed.patch`.
- **IQ3_S / IQ2_S** (engine 35.4 / 32.3):
  - packed logical lanes: 57–64 / 44–51;
  - rows per subgroup 1, 2 or 8: 38.8–45 / 35.5–43;
  - work-group size 1 or 8 subgroups: equal.

  `MultiplyBlockRows<4>` is the local optimum.
- **IQ4_NL** variants:
  - loads-first (all blocks of an item read before decoding): 45–49, against 38;
  - the byte-pair level table: 42;
  - SG32 forms: 44–47 in the microbench, 38.5 (table) and 44.2 (select chain) per site in the engine;
  - RI2: same cold time.
- **Route**:
  - an exact rank-count selection (local rank by 32 broadcasts, then 160-candidate counting): 9.8 → 20.8 µs in the
    microbench, and 15.0 → 23.6 µs per site in the engine;
  - the denominator computed once instead of per lane: no change.
  - The softmax alone costs 5.4–6.0 µs (the floor of the single-work-group form), and the lane-0 output and
    normalisation tail costs about 1 µs.

## Files

- `experts.patch`: unified diff against canonical `engine/src`, 6 files, including the new `experts_v2.hpp`.
- `profile-defer-lab.patch`: the lab-only `rank.hpp` profiling deferral (inert unless `OWNRT_DECODE_PROFILE>=2`).
- `results.json`: run ids, medians, per-site table and exactness results.
- `kbench/`: microbenchmarks, the harness, logs and the `run.sh`, `kbrun.sh`, `prof.py`, `med.py` and `table.py`
  scripts.
- The lab binaries are `/dev/shm/engine-build-lab-dexp-final2/sc117-engine` (final) and
  `/dev/shm/engine-build-lab-dexp-ref/sc117-engine` (reference). Runs are under `/dev/shm/ownrt-lab-dexp/runs/`.
