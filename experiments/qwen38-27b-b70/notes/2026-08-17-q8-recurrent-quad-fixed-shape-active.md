# Qwen3.8 27B Q8 TP2 recurrent-quad fixed-shape specialization

Date: 2026-08-17

Status: closed; exact and faster in long `llama-bench`, but service-neutral

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

The direct benchmark gain repeated, so the candidate proceeded through the
complete service and quality gates. It is **not promoted**: a matched
same-binary realistic endpoint control showed no service gain.

## Service and quality result

Both endpoint arms used the candidate binary with only
`GGML_SYCL_MMVQ_Q8_FIXED_QUAD` changing, one 8K slot, equal TP2, F16 KV,
FlashAttention, `b1024/ub256`, no cache RAM, no context checkpoints, fit off,
reasoning off, and no speculation. Each of the 12 fixed prompts ran once with
`cached_tokens=0`.

| Metric | Dynamic control | Fixed quad | Delta |
| --- | ---: | ---: | ---: |
| conventional 99-interval median | `36.323965` | `36.299848` | `-0.0664%` |
| full decode median | `36.371340` | `36.359758` | `-0.0318%` |
| full decode mean | `36.365299` | `36.365946` | `+0.0018%` |
| wall median | `35.920354` | `35.892489` | `-0.0776%` |

The candidate passed every quality condition:

- all 12 complete outputs were exact against the promoted Q8 oracle;
- the fresh-response and final-metric gates passed with zero cached tokens;
- all seven semantic canaries matched the baseline hashes;
- eight identical repeat requests produced one stable hash;
- the long-context needle passed at the established actual prompt length of
  `3,829` tokens, with the exact baseline hash;
- `pass_all=true` and `baseline_match_all=true`.

This is a real `+0.741%` long synthetic decode result but a service-neutral
compiler specialization. Keep it as a reproducible diagnostic; do not add it
to the accepted Q8 repro, model board, or headline result.

Checkpoint identities:

- isolated source/build: `/mnt/fast-ai/src/llama.cpp-q38-q8-fixed-shapes`,
  `build-sycl-aot-bmg-g31-fixed-shapes`;
- `libggml-sycl.so.0.19.0` SHA-256:
  `8335e8d62834e16193e98206502f4f9bf9bd7e59d7a426e9198492496198849d`;
- `llama-bench` SHA-256:
  `5ad7c26b123d41194a72f127052c50414a58a558a120548f17f11d54dba61abb`;
- `llama-cli` SHA-256:
  `0e7350e8483ebae7d281036db052c2c208884948162b182c577d8b7624981d2d`;
- `llama-server` SHA-256:
  `71972859c1f8132efafa5fd722c0f66d7b23feb8f9a1c567578032006cd695e`;
- incremental patch SHA-256:
  `a68ec8aef3cd618c563352be331adb3e6d42b954f7625c985eae17b6854a5e4d`;
- candidate realistic JSON SHA-256:
  `34533a74d216d2bf43174b32828ce79c323b2a34aca496c01ead0c236bd2c0eb`;
- same-binary control realistic JSON SHA-256:
  `e90a8a87ae5cdba35419812f78f33099e09cb206754060913ff14ba333355b2b`;
- 3,829-token semantic JSON SHA-256:
  `8dda8b6ffd9260680f2600e6b7c351677b8a2b8bce1e3e8d6564a6302a4898da`;
- raw local evidence:
  `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-fixed-quad/`.

The post-run gate found both B70s normal with no current-boot Xe/GuC fault,
reset, timeout, or hang signature. The only kernel warning remains the audited
boot-only KMS `dma_buf_vmap` warning.
