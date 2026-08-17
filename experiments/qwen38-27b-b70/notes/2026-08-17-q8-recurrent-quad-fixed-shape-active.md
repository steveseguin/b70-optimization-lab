# Qwen3.8 27B Q8 TP2 recurrent-quad fixed-shape specialization

Date: 2026-08-17

Status: active; claimed by the ASRock two-B70 reference host

## Hypothesis

The accepted target-only Q8 stack launches the fused recurrent GDN quad 192
times in a `p0/n1` trace, accounting for `19.456 ms` of diagnostic device time.
Every Qwen3.8 recurrent block uses the same global GGUF shapes:

- input columns: `5,120`;
- QKV rows: `10,240`;
- gate rows: `6,144`;
- alpha rows: `48`;
- beta rows: `48`.

Equal TP2 divides every output-row dimension across the two devices, so the
actual per-device quad-kernel shape is input `5,120` and output rows
`5,120 / 3,072 / 24 / 24`. An initial `p64/n1` admission smoke used the global
rows, correctly left the candidate door closed, and is not a benchmark result.
The implementation was corrected to admit only the observed local TP2 shape
before any candidate timing.

The current row body nevertheless selects among four matrices, four output
pointers, four row counts and three cumulative edges dynamically inside every
subgroup. A compile-time specialization for this exact quad may allow Intel's
AOT compiler to remove those branches and constant-fold row addressing. This
is distinct from the closed fixed-shape FFN pair/down experiment and retains
the incumbent DP4A body and FP32 reduction order.

## Contract

- isolated accepted-stack source and build; do not modify the promoted repro;
- default-off runtime door admitting only the exact shape above;
- retain the dynamic kernel as the same-binary control;
- retain equal TP2, F16 KV, target-only execution, FlashAttention and
  `b1024/ub256`;
- mechanism smoke must prove the fixed branch on both devices and report
  `VERIFY_MISMATCH=0`;
- use a run-position-balanced decode screen before endpoint work;
- any fixed-prompt or complete-suite output-hash difference is a hard reject,
  regardless of speed;
- promote only if the speedup repeats and the full cache-zero output oracle,
  semantic canaries and long-context gates all pass.

## Coordination

Other hosts should not duplicate this exact arm while this note is active.
Pull `main`, check this note and the do-not-repeat index, and choose a different
candidate.
