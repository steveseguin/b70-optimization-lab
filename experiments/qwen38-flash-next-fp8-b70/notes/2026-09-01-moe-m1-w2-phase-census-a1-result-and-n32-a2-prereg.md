# Qwen3.8 Flash-Next FP8 M1 w2 census A1 and N32 confirmation A2

Date: 2026-09-01
Status: A1 screen complete; A2 completed as a performance negative

The A1 modular real-weight screen found three exact w2-only candidates above
its 3% advancement floor. N32/warps8 led at `433.1184 us`, `4.501857%` below
the common-warps8 control bracket. W2 warps4 and N32/warps4 measured `4.13%`
and `3.24%` below the bracket. W2 K64 was similarly fast but changed the exact
output hash and is rejected. N128/warps4 regressed by `20.67%`.

The two A1 control medians differed by roughly 4%, so the screen is not enough
to promote N32. A2 freezes a stronger three-seed confirmation:

- seeds `20260826`, `20260827`, and `20260830`;
- fresh-process common-warps8 / w2-N32-warps8 / common-warps8 brackets;
- modular production path and exact real layer-0 EP-rank-0 weights;
- 10 warmups, 15 timing batches of 200 calls, and 100 repeated output hashes;
- the candidate must be exact in every arm, improve at least two seeds by 3%,
  and have a median improvement of at least 3%.

The candidate changes only w2 `BLOCK_SIZE_N` from 64 to 32. W13 remains at
the already-qualified common warps-8 configuration. This remains a component
gate and cannot change a protected model result. Frozen A2 runner SHA-256:
`051889b9f7eaeb87d7d059b474607c39c75502f4810b3080b626ae3d8b5f0142`.

## A2 result

All three seed brackets were exact, but their reductions were `1.329041%`,
`-0.056631%`, and `0.073138%`; the median was `0.073138%` and zero seeds
cleared `3%`. W2 N32 is therefore closed as performance-neutral. See the
[A2 result](2026-09-01-moe-m1-w2-n32-confirm-a2-result.md).
