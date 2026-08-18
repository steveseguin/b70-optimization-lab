# Qwen3.8 27B Q8 TP2 direct IGC DP4A builtin

Date: 2026-08-17

Status: closed; correctness-exact and performance-neutral/slightly negative.

## Hypothesis

The accepted reordered-Q8 hot row body expresses its four signed-byte dot
products through `dpct::dp4a`. `common.hpp` also exposes
`ggml_sycl_dp4a`, a thin wrapper over Intel's `__builtin_IB_dp4a_ss`.
Matthew Dodd's SYCL fork uses that builtin at compile-time-folded sites, and
its accompanying commit notes that IGC normally recognizes non-literal DP4A
patterns. Replacing only the four live calls tests whether spelling the native
instruction explicitly improves scheduling in the accepted DP4A2 x SG24
kernel.

The candidate retained the accepted `0->2` / `1->3` two-chain pairing, integer
addition order, FP32 scale and accumulation boundaries, launch geometry,
model, tensor split, and all runtime settings. No speculation, MTP, DFlash, or
quality-changing option was used.

## Build and correctness gates

An isolated oneAPI 2026.1.1 Release/AOT BMG-G31 build completed under an 8 GiB
memory limit. The compiler did emit a distinct hot MMVQ object and SYCL
library, so the experiment was not dismissed as canonicalized code:

- accepted `mmvq.cpp.o`: `b791488df254d024652f25c45f67612591bbb62d738a9b572ab2eb1d1dbe6225`
- builtin `mmvq.cpp.o`: `ca6235d1a71235380b215e92aac53467fb72e504b6f67630d741abb6f9d0dbbc`
- accepted `libggml-sycl.so.0`: `e75b960307fccee661073e67d8288b3893f421617ea83a100cf9b8f9de38b4b5`
- builtin `libggml-sycl.so.0`: `70e4d187b32652d04dd5945848654c2c02dc29f3ca43ac717b086f521d9aa0ee`

The strict `p0/n1` smoke used `GGML_SYCL_Q8_QUANT_DEDUP=2` and reported
`verified=1980` and `VERIFY_MISMATCH=0`. This establishes exact live-model
reordered-Q8 inputs; performance runs returned to door `1`.

## Position-balanced result

Four fresh processes ran `p64/n512/r3` in A-B-B-A order. The same candidate
executable was used for both arms; the control prepended a checksum-verified
directory containing the accepted SYCL library to `LD_LIBRARY_PATH`.

| Position | Arm | Decode, tok/s |
| ---: | --- | ---: |
| 1 | Accepted | `36.715497` |
| 2 | IGC builtin | `36.722718` |
| 3 | IGC builtin | `36.707602` |
| 4 | Accepted | `36.734615` |

The accepted mean was `36.725056 tok/s`; the builtin mean was
`36.715160 tok/s`, a `-0.026946%` delta. This is measurement noise with a
slightly negative point estimate. It did not earn endpoint or semantic gates
and is not promoted.

The exact source delta is
[`q8-dp4a-builtin-neutral-20260817.diff`](../patches/q8-dp4a-builtin-neutral-20260817.diff).
Structured values are in
[`2026-08-17-q8-dp4a-builtin-neutral.json`](../data/2026-08-17-q8-dp4a-builtin-neutral.json).
Raw local logs are under
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-dp4a-builtin/`.

Do not retry this spelling-only substitution unchanged. A future retry needs a
different compiler/IGC or a materially different DP4A kernel schedule.
