# Qwen3.8 27B Q8 TP2 recurrent-quad fixed-shape specialization

Date: 2026-08-17

Status: active; repeatable performance gain, quality promotion gate in progress

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

## Mechanism and performance checkpoint

The corrected candidate announced the exact local shape on both B70s in a
`p64/n1` smoke. Normal execution completed with `VERIFY_MISMATCH=0`; a
separate poison process announced `poison=1` on both devices, proving the new
instantiation was reached. Both GPUs remained normal after the smokes and
performance runs.

The first position-balanced `p64/n256/r3` screen pooled `37.047833` candidate
versus `36.926158 tok/s` control (`+0.330%`), but its two balanced halves
disagreed (`+0.773%`, `-0.112%`). It was therefore treated as inconclusive.

A longer confirmation used fresh-process order `A-B-B-A, B-A-A-B`, with
`A=control`, `B=fixed`, and `p64/n512/r3`. Both balanced halves agreed:

| Block | Control (tok/s) | Fixed (tok/s) | Delta |
| ---: | ---: | ---: | ---: |
| 1 | `37.135767` | `37.397200` | `+0.704%` |
| 2 | `37.006383` | `37.294350` | `+0.778%` |
| pooled | `37.071075` | `37.345775` | **`+0.741%`** |

This clears the performance gate but is not promoted until the complete
cache-zero output oracle, semantic canaries, repeat stability and long-context
needle all pass.

Checkpoint identities:

- isolated source/build: `/mnt/fast-ai/src/llama.cpp-q38-q8-fixed-shapes`,
  `build-sycl-aot-bmg-g31-fixed-shapes`;
- `libggml-sycl.so.0.19.0` SHA-256:
  `8335e8d62834e16193e98206502f4f9bf9bd7e59d7a426e9198492496198849d`;
- `llama-bench` SHA-256:
  `5ad7c26b123d41194a72f127052c50414a58a558a120548f17f11d54dba61abb`;
- raw local evidence:
  `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-fixed-quad/`.
