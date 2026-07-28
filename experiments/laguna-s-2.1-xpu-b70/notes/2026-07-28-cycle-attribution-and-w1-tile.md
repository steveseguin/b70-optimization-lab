# Laguna cycle attribution, and why the W1 tile cannot be swept at width 12

Date: 2026-07-28 America/Toronto

Status: diagnostic. No throughput result is promoted. The scored baseline is
unchanged at **100.074 tok/s conventional** (median of three matched legs this
boot); the sealed record is `101.94172124017027`.

## Where a verifier forward actually spends its time

First direct per-segment attribution of the decode cycle, from the breakable
graph's replay event profile at width 12, all four ranks agreeing:

| segment kind | n | share | median |
| --- | ---: | ---: | ---: |
| graph | 146 | 69.2% | 628 us |
| collective | 97 | 22.1% | 288 us |
| attention | 48 | 8.7% | 210 us |

**Read the shares, not the absolutes.** Profiled total was 128.99 ms against a
real cycle near 30.5 ms, so per-segment event overhead is comparable to segment
time. What survives that caveat is the ordering, and it survives strongly:
graph segments carry 1.5x the count of collectives but 3.1x the time, so they
are more expensive per segment and not merely more numerous.

This retires a working assumption. The 97 collective boundaries are real but
secondary at roughly a fifth of the cycle, which is consistent with two earlier
results that both lost ground attacking them: local argmax moved 4.82 MB less
data per cycle and made the cycle *slower*, and inline attention retired all 48
attention breaks for -11%. Both were attacks on the smaller share.

The dominant cost sits inside the graph segments, which hold the MoE grouped
GEMM: 24 activated experts per rank per layer across 48 layers, three matrices
each, about **3,456 small GEMMs per rank per cycle at M ~ 1.25 tokens per
expert**. Against 532 GB/s achievable, the 5.6 GB/rank of weight traffic floors
at 11.5 ms versus a 30.5 ms cycle -- roughly **38% of the bandwidth roofline**,
with compute about 1% utilised.

## The W1 N-tile is pinned at every width except eight

`_effective_laguna_m8_w1_n_tile` returned the configured tile only at
`num_rows == 8` and 64 everywhere else, so width 12 -- the width the record
runs -- had never had this swept. The tile is a runtime argument to the grouped
GEMM, so this looked like a one-line Python change plus two legs.

It is not. With the guard removed, both tiles fail closed in the compiled
kernel:

```text
RuntimeError: Laguna fused expert W1 N128 requires M=8 W1-only route interleave
```

Reading the source makes the constraint precise. The fused-expert entry point
accepts `hidden_states` of `[1..8, 3072]`, and the tile check is

```cpp
w1_n_tile == 64 || (w1_only && route_interleave && num_rows == 8)
```

so non-64 tiles require **exactly eight rows**, while the kernel itself serves
one to eight. The tile assertion fired rather than the row-count one, which
means the width-12 batched-exact-MoE path reaches this kernel with row counts
that are not 8. Tile 64 is therefore the only legal choice for every group the
record's width actually produces, and the dispatch selects among
`w4a16_policy_m_8_n_32`, `w4a16_policy_m_8_n_128` and `w4a16_policy_m_8` -- all
M=8 policies.

**Sweeping the tile at width 12 requires new policies and a kernel rebuild**,
not a configuration change. That is the concrete form the MoE work takes, and
the first question it should answer is what row counts the batched path
actually emits, since a batching that produced groups of exactly eight would
make the existing 32/128 policies reachable without writing new ones.

Both arms failed at service startup, so neither produced a rate and neither
touched exactness.

## Provenance

- vLLM: `/home/steve/src/laguna-vllm-replemb-bf16-20260727`
- kernel worktree: `/home/steve/src/laguna-xpu-kernels-tile12-20260728`, branch
  `experiment/laguna-tile12-20260728`, commit `90e905e`
- the record's kernel tree was not modified; the candidate worktree carries the
  same binaries, `_C.abi3.so` verified as
  `126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2`

## Next

1. Rebuild the grouped GEMM with W1 N-tile specialisations at M=12 and sweep
   32/64/128. This is the largest measured inefficiency in the system and the
   only one now supported by direct attribution rather than arithmetic.
2. Whether the per-expert launches are fused into few kernels, and whether INT4
   dequant throughput rather than DRAM is the limiter, are the two questions a
   rebuild should answer alongside the tile.
3. The drafter's prebuilt exact-attention metadata remains worth roughly 25%;
   see the draft-graph-capture note for the root cause and what is left.

A reminder for anyone reading a single leg: run-to-run spread on this host was
**1.63%** across three identical-config legs, so nothing under about 1.5% is
detectable without repeats.

## The generic N-tile knob, swept and closed

At twelve rows the decode falls through every Laguna specialisation into the
generic grouped GEMM: `fused_moe_interface.py` gates the Laguna family on
`1 <= num_rows <= 8`, and in the generic path `A_avg_M = 120 routes / 64
experts = 1`, which collapses the policy ladder so eight- and twelve-row
decodes select the identical `w4a16_policy_m_8` tile of `8x64x32`. The M
dimension is therefore 12-25% occupied at decode.

`VLLM_XPU_MXFP4_SMALL_M_N` is the only tile knob that reaches that path -- it
selects the INT4 policy despite the MXFP4 name -- and it had never been swept.
Both alternatives are exact and both are slower:

| N tile | legacy tok/s | conventional | exact |
| ---: | ---: | ---: | ---: |
| 128 | 99.723654 | 98.726418 | 13/13 |
| 32 | 99.928858 | 98.929570 | 13/13 |
| 64 (default) | 101.085084 (median of 3) | 100.074233 | 13/13 |

Both landed below all three control legs. The margin is inside this host's
1.63% spread, so the correct reading is that neither beat the default rather
than that either is meaningfully worse. **The default 8x64x32 is the best of
the three available tiles and this knob is closed.**

## What the source says is left

Structural, all requiring a kernel rebuild and re-proof of bitwise exactness:

1. The mainloop applies the per-(N, K-group) scale to every B element: about 32
   `apply_scale` instructions per work-item per k-tile feeding 2 DPAS issues, a
   ratio fixed by `SG_N x SG_K` and independent of the M tile. Folding the
   scale into the FP32 accumulator instead would cut that roughly 4x. It moves
   the rounding boundary, so exactness must be re-established.
2. `prefetch_dist` is fixed at 6 for INT4; the W2 GEMM has `k_tile_count = 32`,
   so 19% of its K loop is warm-up.
3. The M-tile selector uses `A_avg_M = A_total_M / num_experts`, which is 1 at
   decode. Selecting on `max(rows_per_expert)` or an explicit row count would
   let a twelve-row decode pick a tile matched to real occupancy.

Measured context for all three: expert-weight streaming alone reaches 350-427
GB/s of a 521 GB/s achievable ceiling on this host, so the memory system is
delivering and the gap is in what the kernel does around the streaming.
