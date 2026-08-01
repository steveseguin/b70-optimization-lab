# Laguna expert-indexed exact MoE scheduler

Date: 2026-07-31 America/Toronto

Status: **preregistered after the flattened-grid result and before this source
change or build.**

## Distinct mechanism

The flattened deterministic scheduler was 6/6 raw-BF16 exact but only
`0.916350x` the current W13+W2 component.  It removed every task-acquisition
atomic/barrier, but its conservative `total_m * N_tiles` grid launched 3,840
W13 and 5,760 W2 workgroups.  More than half scanned metadata and returned.

The measured deterministic route corpora contain 51--57 nonzero experts and
at most six rows per expert, below the M tile of eight.  The next mapping
launches exactly `num_experts * N_tiles` workgroups: 2,048 for W13 and 3,072
for W2.  A workgroup directly derives `expert_id` and `N tile` from its ID,
scans only preceding expert row counts to recover the unchanged packed-row
offset, and loops that one expert's M tiles.  Zero-row experts return.

This still handles any legal distribution, including an expert with more than
eight rows.  It retains expert grouping and invokes the unchanged
`xe_gemm_4bits` tile body once for every incumbent `(expert,M tile,N tile)`.
It changes neither route order nor arithmetic.

## Gates

1. Preserve the rejected flattened scheduler at commit `ceaedbae9`; implement
   this mapping as a new commit in the same experiment branch.
2. Retain the exact current route predicate, separately named GRF128 kernel,
   transposed scales, and selector-off persistent control.
3. Build only the grouped-GEMM DSO with pinned oneAPI 2025.3.  Require
   `libsycl.so.8`, successful BMG device code, and no build swap.
4. Use the same DSO for selector-off/on with the same changed-input physical
   transposed-scale W13/W2 corpus and stabilized 200-warmup/15x40 protocol.
   Require raw-BF16 exactness 6/6, no shape regression over 1%, and at least
   `1.05x` summed speedup.
5. A pass authorizes only an integration smoke.  Endpoint and promotion gates
   remain exactly those in the preceding scheduler preregistration.

No precision, model, BF16 KV, width/depth, verification, acceptance, prompt,
teacher, cache, metric, retry, or scoring change is allowed.  No reset, driver
reload, FLR, reboot, or privileged recovery is authorized.

## Result

Status: **rejected at the component performance gate; no endpoint run.**

- Source commit: `6baa9606700523680b342b2f5fe8b414cbbaa19d`.
- DSO SHA-256:
  `d9871bffd255654ecc442e4c435d5ed95844d3540b8f95ad8d7a93c19c2e3805`.
- Build: oneAPI 2025.3, `libsycl.so.8`, 16:39.15 elapsed,
  106,782,392 KiB peak RSS, zero build swaps.
- Component artifact:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/components/laguna-expert-indexed-scheduler-6baa960-20260801T083438Z`.
- Exactness: 6/6 changed-input raw-BF16 comparisons.
- W13: 0.320588 ms control versus 0.331354725 ms candidate,
  `0.967506952x`.
- W2: 0.1837208 ms control versus 0.18607245 ms candidate,
  `0.987361643x`.
- Summed: 0.5043088 ms control versus 0.517427175 ms candidate,
  `0.974646915x`.

The expert-indexed mapping removed most of the flattened mapping's empty-grid
waste and improved it from `0.916350x` to `0.974647x`, but did not beat the
persistent atomic/barrier scheduler.  At this M=120 distribution, replacing
task acquisition with a per-workgroup prefix scan is still a net loss.  The
result closes this scheduler family unless a future design can provide the
packed expert row offsets directly without adding a launch, host sync, or
arithmetic change.
