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

Tiles 32 and 128 are specialised for `M=8` only; at `M=12` the binary provides
64 alone. The Python guard was reporting a real binary constraint rather than
an untested combination. **Sweeping the tile at width 12 requires rebuilding
the kernel with M=12 specialisations**, which is the concrete form the MoE work
takes.

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
