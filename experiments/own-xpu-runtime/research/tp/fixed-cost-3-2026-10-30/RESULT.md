# Four-card fixed cost, round 3 (2026-10-30): status

Base: the round-2 tree (engine/src `979462f7c` + [engine-fixed-cost-2.patch](../fixed-cost-2-2026-10-30/engine-fixed-cost-2.patch),
build m2 `dddf5cf0e067`, private copy `/dev/shm/fc3-2026-10-30/tree`). Four cards on m2 with all round-2 flags: rank 0
half + draft 7.85 + 0.99 ms, rank 1 half 8.67 ms; in service the two paths are 8.85 / 8.81 ms, so every lever is judged
by the hit cycle (both ranks).

## In plain words

- **No cheap item is left among the round-3 candidates.** Every remaining runtime-indexed lookup on the decode path
  is a handful of launches per half. The census below found no other decode kernel with a large private array. None
  reaches 0.05 ms per half.
- **The material levers left are builds of several hours, on both ranks:** splitting the replicated HC GEMVs across each
  card pair (estimated 0.2–0.25 ms per half), and exchange stores in the producer kernels (0.1–0.2 ms per half).

## Kernel census (diagnostic, one card, IGC shader dumps)

- **How.** One-card rank-1 and rank-0 arms on m2 with every round-2 flag, `IGC_ShaderDumpEnable=1` in the engine's
  launch environment and a fresh kernel cache. Phase d1 ([logs/d1.log](logs/d1.log)): both arms rc 0, kernel log clean;
  raw runs in `fixed-cost-3-census` on the RAID. Every JIT-compiled kernel's ISA header gives its private memory size;
  [results/igc-private-memory-census.txt](results/igc-private-memory-census.txt) lists the 78 kernels that have any.
- **Decode kernels.** The kernels that run in decode carry at most 128 B. That is `detmath::rsqrt`'s deliberate volatile
  round trip between `sqrt` and `inv` (one store and load per work-group), kept for exact rounding. It shows in the HC
  norm kernels (`HcNorm`, `HcNormMoe`), the `ngop` per-op kernels, `mtp36::Norm` and the fallback norms.
- **Draft kernels.** The round-2 draft kernels have none: `draft_fast::Norms`, `Segments`, `Gather` and `Merge` (2 spills).
- **The large private arrays (4–86 KB per work-item)** are in stage variants of `specialised::Kernel` (route_gather,
  prepare, norm, combine_norm, attention stages), `p47::combine`, the generic `ng::Kernel` (21.7 KB) and `Glue`'s
  token-row lambda (51 KB). These serve batched prompt reading and token rows. In decode, the generic kernel's ops run
  as `ngop` kernels since round 2, and the QSA select runs its fast path, which has no private array.
- **What the census cannot see.** The flag-off kopt block-rows kernels show no private memory, yet host-resolved
  pointers (`kptr`) saved 2–2.7 µs per launch. So the round-2 "runtime index into a captured array" cost is not scratch
  memory, and private memory size cannot find the remaining cases. The other cases the audit listed are small on four
  cards: begin/commit/PLE glue (about 5 launches per half), the head argmax (a split kernel since `tpt`) and the
  readback copy (2–4 per cycle). They are closed by size (< 0.05 ms per half).

## Other candidates

- **HC low gap (15.1 / 16.9 µs vs 13.75 µs in the bench).** Closed, cause not found: the low launch is already static
  select (`lowsel`) and has no private memory; the same kernel takes 15.1 µs at hc.a and 16.9 µs at hc.f, so the
  remainder depends on what runs around it (the HC agent could not reproduce it with ALU- or memory-heavy neighbours).
- **TP exchange kernel.** It already reads host-resolved pointers (`single_device.cpp` `submit_exchange`). Its cost is
  the protocol: P2P stores, system-scope fences, the counter and the flag, about 3.7–3.9 µs per exchange with launch
  and wait, 69 / 76 exchanges per half. Not changed: a weaker fence is a correctness risk that a bitwise gate can miss.
- **Exchange stores in the producer's tail** (round-1 lever F4). This removes the exchange launch but keeps fences and
  the flag wait. It needs store-and-flag tails in five producer families (gated norm, Q8 attention GEMV, expert down,
  QSA attention, head shard). Upper bound 0.15–0.2 ms per half per rank. Not built.
- **Split the replicated HC GEMVs across each card pair (the largest replicated work: about 1.45 ms per card per half).**
  The four HC GEMVs per layer take 14–17 µs each on every card. A contiguous-row split
  (`row_runs={{c*R/2,R/2}}`, output to `y#tp`, one `tp_xgather` per GEMV, as the Q8 attention split does) would be
  exact, since every row keeps its kernel and order.
  - Estimate: about 6 µs saved per GEMV against 3.9 µs per exchange, so about 10 µs per layer: **0.23 ms per half on
    rank 0, 0.25 ms on rank 1**.
  - Work needed:
    - `split_site` today admits only the p33 row-major paths;
    - the HC low is fused with its inject (kopt `fused_gemv`), and the HC gate runs `bf16_multi<2,4>`. Either the
      row-run descriptor must reach the `dense_v2` paths, or the split sites fall back to the slower generic kopt kernel;
    - the dump layout needs the half-row reassembly.
  - This is the next build.

## Files

- Harness: copies of the round-2 scripts, with the `f3=` extra for `OWNRT_FAST3` (round-3 flags, none built yet).
  Census: [results/igc-private-memory-census.txt](results/igc-private-memory-census.txt).
