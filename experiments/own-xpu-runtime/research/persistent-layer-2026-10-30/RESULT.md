# Persistent layer kernel with device-wide barriers on one B70: design study and microbenchmarks (2026-10-30)

**Question.** Decode is dominated by small kernels (one card, rank 0: 863 launches per half, 728 under 20 µs, 5.0 ms).
Would running a layer's chain of small kernels as ONE persistent kernel, with device-side barriers between its phases,
remove that fixed cost? This is a go/no-go with a measured size: idea #7 in [IDEAS.md](../../IDEAS.md). It was a
design study plus two one-card microbenchmarks. There was no engine integration.

**Answer: no-go.** On a B70 a device-wide barrier costs more than the kernel boundary it would replace. On the real
hyper-connection chain, the best persistent kernel is 9.6% slower than separate launches, though it is bitwise exact.
Even a free barrier would cap the gain at about 8.5% of a four-card half, below the 10% bar.

## In plain words

- **A kernel boundary is already cheap.** In an in-order queue with the host ahead, an empty kernel costs 0.63 µs
  from one kernel's end to the next (0.52 µs of event time plus a 0.10 µs gap). This holds for 1 to 256 groups. A
  tiny dependent kernel (each group reads one value another group wrote and writes one value) costs 0.64 µs on 1–8
  groups and 1.06–1.11 µs on 64–256 groups.
  - The census's 2–2.5 µs "minimum duration" of the tiny kernels is therefore mostly the kernels' own dependent memory
    round trips and reductions. A persistent kernel still pays those.
- **A device-wide barrier is not cheaper.** The best variant is one arrival counter in global memory: the group leader
  does an `acq_rel` atomic and polls with bounded spins, and work-group barriers sit on either side. It costs:
  - 0.57 µs with 1 group, then about 10 ns more per arriving group, because every arrival hits the same counter line;
  - 0.95 µs at 32 groups, 1.50 µs at 64, 3.30 µs at 256, 6.67 µs at 512;
  - p99 about 15% above the median;
  - the same at a given group count whatever the group width (64 groups: 1.50 µs at 256, 512 or 1024 work-items).
  - Device-scope work-group fences make it 2–5× dearer (7.9 µs at 64 × 1024). A two-level counter and a
    generation-flag barrier were both slower.
- **A GEMV needs the whole card, and that is where the barrier is most expensive.**
  - At most 65,536 work-items are resident: 2,048 SIMD32 threads, so 512 × 128, 256 × 256, 128 × 512 or 64 × 1024.
    The driver's `max_num_work_groups` query gives exactly these numbers. One group more times out and reports an
    error (bounded, 15–123 ms, no fault).
  - The cheapest barrier that still fills the card is 64 groups × 1024: 1.5 µs. That is more than the 0.6–1.1 µs
    boundary it replaces.
- **The real chain agrees.** SC117's hyper-connection block at its real shapes (norm, BF16 low GEMV plus inject,
  act, BF16 gate GEMV, mix) was run with 8 distinct weight sets, so weights come from memory as in the engine.
  - Six separate launches: **37.45 µs per block**.
  - Best persistent kernel (64 × 1024, 5 barriers per block, 8 blocks per launch): **41.04 µs**. That is 3.6 µs
    (9.6%) slower, a net −0.72 µs per absorbed boundary.
  - Every other layout is slower: 42–256 µs.
  - All 21 versions and layouts are bitwise identical to the separate kernels, and the separate kernels agree with a
    double-precision host reference to 1.3e-7. Exactness is not the obstacle; speed is.
- **Projection (CPU arithmetic over these numbers).**
  - At the measured cost, putting every launch of a decode half into persistent kernels *loses* 0.62–0.67 ms per
    half on one card and 0.67–0.73 ms per half on four cards (−7.6% to −7.8%).
  - With a zero-cost barrier and perfectly efficient phases, the ceiling is +0.69–0.75 ms per half on one card
    (+6.3–6.8%) and +0.74–0.81 ms on four cards (+8.5–8.6%). That is still under the 10% go bar.
- **Decision: no-go.** Do not build a persistent layer kernel on this hardware. The fixed cost per small kernel is
  inside the kernel, not between kernels.
- **A side result from the same chain.**
  - This microbenchmark's plain HC block (37.45 µs) is 7 µs faster than the engine's same block in the census
    (44.4 µs per layer on rank 0).
  - Most of the difference is the two BF16 GEMVs: 13.6 and 12.4 µs here (482 / 529 GB/s) against 16.3 and 16.0 µs in
    the engine (400–415 GB/s). The two-launch norm also differs: 3.2 µs here against 6.3 µs.
  - Caveat: the reduction order here is this bench's own, not the engine's. The engine can only use this if a faster
    kernel keeps its exact order (next steps).

## What was measured, and how

- **Card.** One B70 only, 0000:43:00.0 (renderD128, checked from the process's open files on every run).
  - `/dev/shm/card43.lock` was held with `flock` only while each run executed ([run.sh](run.sh)).
  - Environment: `NEOReadDebugKeys=1 EnableDeferBacking=0`, `FilterBdfPath` to the one card.
  - The kernel log (`journalctl -k` via sudo) was checked for the 10 minutes before every run and for the run window
    after it. All 10 runs: 0 fault, CAT, reset, timeout or coredump lines.
  - No power, clock, memory or service settings were touched.
- **Device facts** ([results/barrier-full2-c43.json](results/barrier-full2-c43.json)):
  - 256 EUs (8 slices × 4 Xe cores × 8 EUs), 8 threads per EU, so 2,048 hardware threads;
  - 128 KiB local memory; maximum work-group 1,024;
  - Level Zero driver 1.15.38308; in-kernel sub-group clock 2.80 ticks/ns.
- **Build** ([build.sh](build.sh)): oneAPI 2026.0 `icpx -O2 -fno-fast-math -ffp-contract=off -fdenormal-fp-math=ieee
  -foffload-fp32-prec-div -foffload-fp32-prec-sqrt`, with the offload precision flags also on the link line. JIT
  device code. Final binaries: barrier `53bccee859bf…`, chain `27818ad3351a…`.
- **Barrier** ([gbar.hpp](gbar.hpp)):
  - Every wait is bounded at 65,536 polls. A leader that exceeds it, or sees another group's error word, sets the
    error word and leaves. The host checks the word after every launch and stops all device work on any error.
  - No reset is needed between launches: the host passes the counter's value at entry.
  - Variants:
    - `counter`: one monotonic counter, which everyone polls;
    - `flag`: the last arriver resets the counter and bumps a generation word;
    - `tree16`: 16 groups per sub-counter, then a top counter;
    - each with `wg-fence` (work-group barriers around the leader's device-scope `acq_rel` atomics) or
      `device-fence` (device-scope work-group barriers on both sides).
- **Barrier bench** ([barrier.cpp](barrier.cpp)):
  - Each phase is "touch" work followed by one barrier: the group's *last* work-item, not the leader, reads a value
    another group wrote in the previous phase and writes its own.
  - µs per barrier = (t(R = 1000) − t(R = 0)) / 1000 from profiling events, median of 7.
  - Per-barrier spread comes from the sub-group clock of group 0 and of the last group.
  - The touch values prove the data hand-off: every value must equal R. 0 bad in every run and variant, including
    `wg-fence`, where the writer and the reader are not the leaders.
- **Boundary bench** (same file):
  - 400 launches of the same touch work (or an empty kernel) are queued behind a 6 ms busy kernel, so the card never
    waits for the host. In every repeat the host finished queueing before the busy kernel ended.
  - Period = (end of the last kernel − end of kernel 8) / 391.
  - Cross-check: wall time without profiling, minus the busy kernel alone. It agrees to within 0.1–0.2 µs.
- **Chain bench** ([chain.cpp](chain.cpp)):
  - Shapes from `recurrent-f32/source/plan.hpp` `hc()`: H = 2560, 4 streams (K = 10240), low rank 320, 4 inject rows,
    BF16 weights, F32 activations. Each block reads 13.19 MB of weights; 8 blocks per pass, 105.5 MB.
  - The same per-unit device functions are used by every version. These are: chunk partial sums (32-element xor
    butterfly), the stream norm (fixed partial order, `detmath::rsqrt`), the low row (4 fixed K-quarters, 8 BF16 per
    lane per step, butterfly, (q0 + q1) + (q2 + q3)), `detmath::silu_div4`, the gate row (2 BF16 per lane per step,
    butterfly) and the mix (h = 0..3, then /4).
  - Versions:
    - A: 6 launches per block, like the engine (norm × 2, low + inject, act, gate, mix);
    - A2: 4 launches (act in the low epilogue, column-grouped gate + mix);
    - A3: 5 launches (act in the low epilogue only);
    - B: persistent, phases of A, 5 barriers per block;
    - C: persistent, phases of A2, 3 barriers per block;
    - B and C at 64–512 groups of 128 and 16–64 groups of 1024.
  - Each persistent launch runs all 8 blocks and reuses the intermediate buffers across blocks, so a stale read would
    show as a mismatch.
  - Timing: 24 passes back to back behind a busy kernel, 6 rounds, versions interleaved; the first 2 passes skipped.

## Results

### Co-residency (one bounded barrier, R = 1)

| work-group | driver `max_num_work_groups` | largest N that passes | N + 1 |
| ---: | ---: | ---: | --- |
| 128 | 512 | 512 | error after 123 ms (bounded) |
| 256 | 256 | 256 | error after 62 ms |
| 512 | 128 | 128 | error after 31 ms |
| 1024 | 64 | 64 | error after 15 ms |

The two persistent chain kernels report the same limits: 512 at 128 and 64 at 1024. The chain kernels did not push
register use into a mode with fewer threads.

### Barrier against kernel boundary (µs; boundary = period between consecutive kernels with the host ahead)

| groups N | barrier `counter/wg-fence` (p50 / p99 per barrier, group 0) | `tree16/wg-fence` | `flag/wg-fence` | `counter/device-fence` | empty-kernel boundary | touch-kernel boundary |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.57 (0.58 / 0.63) | 0.82 | 0.64 | 1.35 | 0.63 | 0.64 |
| 8 | 0.76 (0.81 / 0.84) | 0.90 | 1.02 | 1.54 | 0.63 | 0.64 |
| 32 | 0.95 (0.98 / 1.19) | 1.22 | 1.55 | 1.69 | 0.63 | 0.71 |
| 64 | 1.50 (1.52 / 1.74) | 1.92 | 3.14 | 2.65 | 0.63 | 1.06 |
| 128 | 2.12 (2.14 / 2.30) | 3.35 | 5.37 | 5.26 | 0.63 | 1.10 |
| 256 | 3.30 (3.29 / 3.79) | 5.94 | 9.76 | 11.08 | 0.63 | 1.11 |
| 512 (128-wide) | 6.67 (6.67 / 8.40) | 11.73 | — | — | — | — |

The work-group width does not matter: `counter/wg-fence` at 64 groups costs 1.45 / 1.50 / 1.50 / 1.51 µs at
128 / 256 / 512 / 1024 work-items. The last group sees the same per-barrier period as group 0, within about 10 ns.
Profiled and unprofiled boundary periods agree: 0.62–0.72 µs empty, 0.75–1.25 µs touch.

### The hyper-connection chain ([results/chain-final-c43.json](results/chain-final-c43.json))

| version | launches per block | barriers per block | µs per block (p10–p90) | vs A | bitwise = A |
| --- | ---: | ---: | --- | ---: | --- |
| A, separate kernels | 6 | 0 | **37.45** (37.42–37.49) | — | yes (repeat) |
| A3, act in the low epilogue | 5 | 0 | 36.47 | −0.99 | yes |
| A2, + column-grouped gate+mix | 4 | 0 | 47.52 | +10.07 | yes |
| B, persistent 64 × 1024 | 1/8 | 5 | **41.04** (40.92–41.16) | +3.59 | yes |
| B, persistent 41 / 32 / 16 × 1024 | 1/8 | 5 | 42.24 / 42.53 / 49.49 | +4.8 / +5.1 / +12.0 | yes |
| B, persistent 64 / 128 / 256 / 324 / 512 × 128 | 1/8 | 5 | 80.2 / 64.3 / 92.0 / 86.4 / 113.3 | +27 to +76 | yes |
| C, persistent (phases of A2), best 64 × 1024 | 1/8 | 3 | 55.48 | +18.0 | yes |

- A's kernels (event µs, p50) against the engine's per-launch times for the same block in the census (rank 0, hc.a):

  | kernel | this bench | engine |
  | --- | ---: | ---: |
  | norm partials | 1.46 | 3.1 per launch, 2 launches |
  | norm output | 1.77 | (included above) |
  | low + inject | 13.65 | 16.3 |
  | act | 1.88 | 2.5 |
  | gate | 12.40 | 16.0 |
  | mix | 5.63 | 3.4 |
  | gaps between kernels | 0.10 | 0.14 (average) |

- Why B loses: it saves 5 boundaries (about 0.8 µs each, implied by A − B + 5 × 1.51) but pays 5 barriers of 1.51 µs
  at 64 groups. The 128-wide layouts either leave the GEMVs short of threads (64–128 groups) or pay 3.4–6.7 µs per
  barrier (256–512 groups). Fewer groups lose occupancy in the GEMVs: 16 × 1024 costs 49.5 µs.
- C loses more because its column-grouped gate+mix (one group per output column, then a serial mix) is the slow
  structure that DO-NOT-REPEAT already records for the engine's HC gate+mix fusion.
- A3 confirms that a local-dependency epilogue keeps only part of the saving: the act kernel and its boundary cost
  1.98 µs, and folding it saves 0.99 µs.

### Projection to a decode half ([project.py](project.py), [results/projection.json](results/projection.json))

Assumptions:
- launch counts are the census's (rank 0: 863 per half, 728 under 20 µs; rank 1: 938 / 792);
- each absorbed boundary costs the chain's measured net −0.72 µs, or saves at most +0.80 µs with a free barrier and
  perfect phases (the larger of the chain-implied boundary saving and the 0.63 µs empty-kernel period);
- on four cards each card runs the same number of launches, plus 69 / 76 exchange kernels that only the whole-half case
  can absorb, and only their launch cost;
- four-card halves are 8.60 ms (rank 0) and 9.52 ms (rank 1) after F1 + F2.

| scenario | absorbed launches (rank 0 / rank 1) | one card, measured | one card, free barrier | four cards, measured | four cards, free barrier |
| --- | --- | --- | --- | --- | --- |
| HC blocks only (46 / 51 blocks × 5) | 230 / 255 (27%) | −0.17 / −0.18 ms | +0.18 / +0.20 ms (1.7–1.8%) | −1.9% | +2.1% |
| every run of small kernels between big ones | 592 / 645 (69%) | −0.42 / −0.46 ms | +0.47 / +0.51 ms (4.3–4.7%) | −4.9% | +5.4–5.5% |
| whole half in one persistent kernel | 862 / 937 (100%) | −0.62 / −0.67 ms | +0.69 / +0.75 ms (6.3–6.8%) | −7.6 to −7.8% | **+8.5–8.6%** |

The go bar was a projected ≥ 10% four-card decode gain with a credible exactness path. Exactness is credible: the
per-unit arithmetic is shared and the outputs are bitwise equal. The gain is negative as measured, and below 10% even
with a free barrier.

## What blocks it (each checked or measured here)

- **The GEMVs need every core.** A BF16 GEMV of this size needs the whole card. At 16 × 1024 or 64–128 × 128 groups
  the block takes 49–80 µs instead of 37. Filling the card means 64–512 resident groups, and the barrier costs
  1.5–6.7 µs there, because its cost grows with the number of arrivals (about 10 ns each on one counter line). A tree
  of sub-counters did not help: about 0.8 µs fixed and still serialised at the top.
- **Co-residency limit.** At most 65,536 work-items are resident, measured and matching the driver. A persistent kernel
  is capped at that for the life of the layer.
  - Any phase that would like more parallelism (experts, attention) must loop.
  - A kernel that needs 256 registers per thread (large-GRF mode) halves the limit for the whole persistent kernel, so
    every phase pays for the worst phase's registers. The engine's IQ3_S expert and attention kernels would have to be
    checked.
- **Fence scope.** The cheap barrier relies on work-group barriers plus device-scope `acq_rel` atomics in the leader.
  - It is correct in SYCL's scoped memory model, and it was verified on hardware: the non-leader hand-off and 8
    blocks of reused intermediates per launch, with bitwise-equal outputs.
  - The conservative device-scope fences cost 2–5× more.
- **SYCL forward progress.** A plain `nd_range` launch carries no co-residency guarantee in SYCL 2020. This study
  relies on the driver query matching the hardware, and on bounded spins turning a violation into an error instead of
  a hang (verified at N + 1 for every width).
  - The guaranteed path is the root-group barrier with a cooperative launch (`sycl_ext_oneapi_root_group`). It was
    not measured, because it is an unbounded hardware wait, which the study rules forbid.
- **Peer exchanges (four cards).** An exchange inside a persistent kernel would hold every resident group in a
  bounded spin on the peer's flag. The stage-overhead study saw card stalls of 0.3–1.6 ms (host lag), so the limit
  would have to be generous. Only the exchanges' launch residual (0.06–0.08 ms per half) is recoverable; their stores,
  fences and flag latency stay.
- **Fault risk.** The spin limit must be loose enough that a slow phase (preemption, a peer stall) is not turned into
  a fatal error, and tight enough to bound a broken launch. Every error is fatal to that step's output and has to be
  handled as a fault. That is a new failure mode in the decode path for a negative gain.

## Next steps this points to (decode tok/s, ranked by measured or estimated size)

1. **HC BF16 GEMVs at the speed this bench reaches.** The engine's four HC GEMVs per layer run at 400–415 GB/s. This
   bench's plain kernels reach 482–529 GB/s on the same shapes with cold weights.
   - Estimate: per block, (16.3 − 13.65) + (16.0 − 12.40) ≈ 6.3–6.6 µs. That is about 0.29 ms per half on rank 0
     (46 blocks, 1.51 ms of HC GEMVs) and 0.33 ms on rank 1 (50 blocks, 1.63 ms). They are replicated on both cards of
     a stage, so this is about 3.4% of a four-card half.
   - It is only usable if the faster kernel keeps the engine's exact reduction order. First step: read the engine's
     incumbent BF16 HC kernel order (`k2_incumbents.hpp`, `p28.dense.*`), microbenchmark a faster kernel with that
     order on one card, and gate it bitwise against the engine kernel's output.
2. **The engine's two-launch HC norm.** 6.3 µs per block against 3.2 µs here; about 0.14 ms per half (rank 0, both HC
   norms). Same exactness condition and same first step.
3. **Local epilogues only where they are free.** act into low saves 0.99 µs per block, about 0.05 ms per half
   (0.5%). It is a small lever; record it and close it unless it comes free with item 1.
4. **The persistent layer itself: closed.** Revisit only if the hardware or driver gains a grid barrier that costs
   under about 0.3 µs at 64 groups.

## Files

- [gbar.hpp](gbar.hpp): the bounded device-wide barrier (counter, flag and tree kinds; work-group or device fences).
- [barrier.cpp](barrier.cpp): co-residency, barrier cost and spread, kernel-boundary cost.
- [chain.cpp](chain.cpp): the HC chain as separate kernels (A, A2, A3) and persistent kernels (B, C), with a bitwise
  gate and a host reference.
- [build.sh](build.sh), [run.sh](run.sh): build (CPU only); one-card run under the lock with kernel-log checks.
- [project.py](project.py): the projection.
- `results/`:
  - authoritative: `barrier-full2-c43.json`, `chain-final-c43.json` and `projection.json`;
  - `barrier-full-c43.json` and `chain-full-c43.json` are earlier full runs that agree within 0.1 µs;
  - `*-quick*` are the smallest-first runs. In `barrier-quick-c43` the busy kernel was constant-folded, so the host was
    not ahead, and the boundary touch check read a second, unreset pass. In `barrier-quick2` the tree variant timed
    out (bounded; its sub-counter targets assume one N since the reset). In `chain-quick-c43` the host reference wrongly used
    silu(x)/4 where `silu_div4` is silu(x/4). All of these were fixed before the full runs.
- `logs/`: lock, card, binary hash and kernel-log result of every run.
