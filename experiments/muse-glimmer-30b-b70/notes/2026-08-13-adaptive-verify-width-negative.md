# Confidence-adaptive DFlash verification width: negative

Date: 2026-08-13

## Decision

Do not implement a confidence-adaptive DFlash verification width. A
target-aware dynamic-programming oracle, which knows the future mismatch
position before selecting every batch width, reaches only `77.134 tok/s` on
the honest three-class mean using measured TP4 target costs. A real confidence
policy cannot outperform this oracle. No drafter training was performed.

## Measured TP4 target cost curve

The current retained kernel environment and BF16 target were measured with
seven `llama-bench` repetitions per width:

| target rows | mean time | standard deviation |
| ---: | ---: | ---: |
| 1 | `37.525488 ms` | `0.129880 ms` |
| 2 | `36.132474 ms` | `0.105967 ms` |
| 4 | `37.874940 ms` | `0.110234 ms` |
| 8 | `39.682851 ms` | `0.149193 ms` |
| 16 | `44.407115 ms` | `0.075477 ms` |
| 22 | `49.180973 ms` | `0.046374 ms` |
| 30 | `53.809124 ms` | `0.089315 ms` |
| 32 | `54.753613 ms` | `0.088527 ms` |
| 44 | `66.765885 ms` | `0.087003 ms` |
| 48 | `68.496066 ms` | `0.062141 ms` |
| 64 | `76.517261 ms` | `0.066417 ms` |

The width-2 minimum is only `8.275 ms` below width 16. Weight streaming is
therefore still the floor; shortening a weak round cannot recover the roughly
20 ms needed by the century target.

## Oracle method and result

At each canonical prefix, the oracle tries every draft width from zero to 15,
knows the true length of the coming DFlash top-1 match, and selects the width
that minimizes total completion time. Unmeasured widths are linearly
interpolated between measured points. The non-target portion of each round is
inferred *optimistically* as incumbent round time minus the full width-16
target cost, even though not every real round is full width. This minimizes the
overhead charged to the candidate.

| class | oracle rounds | oracle tok/s |
| --- | ---: | ---: |
| prose | 83 | `55.630` |
| code | 57 | `81.625` |
| JSON | 49 | `94.147` |
| arithmetic mean |  | **`77.134`** |

Even combining perfect future knowledge with additional kernel savings does
not make this a plausible route. The model must remove `72.145%` of the
already-optimistic fixed per-round overhead before the oracle mean reaches
100. Removing half of that overhead reaches only `91.658 tok/s`; every
remaining measured kernel micro-lane is far smaller than half.

## Evidence

- batch-cost JSON:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/target-pp1-64-cost-20260813.json`,
  SHA256 `24495f87c1e6d5838d37763b7f75f07e8534296f95ddf5c25026aa4f03214372`;
- oracle analyzer: `scripts/analyze-muse-adaptive-verify-width.py`, SHA256
  `cb15c2d1adc719dd8065ed68637ff616f379ef8a1022caaa883fba5b3411d4d8`;
- focused tests: `scripts/tests/test_analyze_muse_adaptive_verify_width.py`,
  SHA256 `20b25c5b8b5880c6dd4ed7ebed1a5f7a0e9c8f4df528b42a1c0edf299c7712d4`;
- structured result: `data/muse-adaptive-verify-width-oracle-20260813.json`,
  SHA256 `a65a717f5a06b53e3bd296ffbf6a489a9fa41e7759073515c03b9f6c95af1b1d`.

The adaptive-width and existing DDTree analyzer tests passed `4/4`. Production
was restored without reboot and passed the full model, cache-zero/code, and
vision gate in `data/muse-health-20260813-adaptive-width-cost-restore.json`.
