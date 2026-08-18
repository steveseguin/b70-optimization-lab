# Qwen3.8 27B Q8 TP2 MMVQ kernel-argument no-alias contract

Date: 2026-08-17

Status: closed; performance-neutral, not promoted.

## Hypothesis

The accepted reordered-Q8 kernels pass distinct weight, activation, and output
allocations, but that no-alias relationship is not visible at the SYCL kernel
entry. Intel documents `[[intel::kernel_args_restrict]]` as an unchecked
kernel-level no-alias promise that can enable more aggressive memory scheduling.
The hot Q8 kernel is bandwidth-bound and its inner helpers already use
`__restrict__`, so exposing the same fact at the generated kernel boundary may
remove conservative dependencies without changing loads, arithmetic, launch
geometry, or output values.

This is materially different from the closed operand preload, weight prefetch,
cache-hint, fixed-shape, GRF, and DP4A experiments: it changes only compiler
alias information at the kernel boundary.

## Contract

- derive an isolated treatment source/build from the checksum-gated accepted
  DP4A2 x SG24 Q8 stack;
- apply the attribute only to the live reordered-Q8 standalone, multi-column,
  fused pair, fused attention triple, and processed recurrent quad launches;
- first verify that IntelLLVM 2026.1.1 accepts the GPU attribute and inspect
  BMG-G31 AOT metadata/disassembly for real code-generation movement;
- keep the accepted binary as the control; do not add a second in-binary
  specialization because that previously perturbed control IGC code generation;
- require a bounded TP2 smoke with the full fusion census and zero verifier
  mismatches, then an accepted-treatment-accepted fresh-process bracket;
- run endpoint and quality gates only for a repeatable positive result outside
  measurement noise;
- stop immediately on a SYCL exception, device loss/reset/hang, or any output
  mismatch.

No model, quantization, tensor split, FP32 accumulation order, KV type,
sampling, or speculative mechanism changes in this experiment.

## Result

IntelLLVM 2026.1.1 accepted the attribute on all five selected entry points.
The bounded TP2 smoke completed with `VERIFY_MISMATCH=0`. Every valid measured
run announced the accepted 24xSG16 recurrent-quad geometry on both B70s and
reported a non-zero recurrent-quad fusion census.

The first nominal accepted-treatment-accepted bracket was discarded. The
copied `llama-bench` executable retained an absolute RUNPATH to the accepted
build directory, so both nominal arms resolved the same treatment
`libggml-sycl.so.0`. Subsequent runs prepended each arm's complete `bin/`
directory to `LD_LIBRARY_PATH`, checked the resolved path with `ldd`, and
checked the library SHA-256 immediately before launch.

At `p64/n256/r3`, the first correctly isolated A-B-A bracket appeared positive:

| Arm | Decode, tok/s |
| --- | ---: |
| Accepted A1 | `36.843730` |
| Restricted B | `37.743147` |
| Accepted A2 | `36.867152` |

The mandatory opposite-order B-A-A-B bracket reversed direction. Restricted
averaged `36.937426 tok/s` versus `37.152018 tok/s` accepted (`-0.578%`). A
longer position-balanced `p64/n512/r3` A-B-B-A gate then removed most of the
load/process-state noise:

| Arm | Decode, tok/s |
| --- | ---: |
| Accepted A1 | `36.915335` |
| Restricted B1 | `36.893359` |
| Restricted B2 | `36.852211` |
| Accepted A2 | `36.842499` |

The long pooled restricted mean was `36.872785 tok/s` versus `36.878917`
accepted, a `-0.0166%` difference. This is performance-neutral and did not earn
an endpoint or semantic gate. All valid runs ended at `VERIFY_MISMATCH=0`; no
current-boot Xe compute fault, reset, timeout, or hang was present.

## Transferred-history check

This exact compiler contract had already been strongly rejected on the older
Qwen3.6 accepted stack (`-2.852%` pooled mean and `-2.950%` median). Retrying
was permissible because Qwen3.8, the DP4A2xSG24 kernel geometry, and oneAPI
2026.1.1 materially changed the generated program. The current neutral result
closes that exception: do not retry unchanged.

Treatment `libggml-sycl.so.0` SHA-256 was
`1966965a7c18477108e4626d5aecf3715e0f6702207eb2ae37258208bf5dae4f`;
accepted control was
`e75b960307fccee661073e67d8288b3893f421617ea83a100cf9b8f9de38b4b5`.
Raw local evidence is under
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-kernel-args-restrict/`.
Structured values and the exact five-hunk source delta are linked from the
do-not-repeat index.
