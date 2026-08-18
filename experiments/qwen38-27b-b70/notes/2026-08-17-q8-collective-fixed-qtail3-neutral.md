# Qwen3.8 27B Q8 TP2 fixed three-slot collective Q8 tail

Date: 2026-08-17

Status: closed; correctness-exact and performance-neutral.

## Hypothesis

The accepted register-direct collective tail runs 128 times per generated
token. For Qwen3.8-27B its live shape is always 5,120 FP32 elements in one
1,024-work-item group: 64 SIMD16 subgroups quantizing exactly 160 Q8_1 blocks.
The source nevertheless expresses the quantization walk as a runtime-strided
loop.

The candidate replaced that loop on both devices with three compile-time
unrolled, ordered slots. Slots zero and one are active for every subgroup; slot
two is active for subgroup 0 through 31. A caller guard admits the
specialization only for `nelem=5120` and WG1024. The per-subgroup block order,
FP32 values, subgroup sum/amax reductions, Q8 rounding and stores are
unchanged. No model, tensor split, quantization, KV type, sampling, speculation,
MTP, or DFlash setting changed.

## Build and correctness

A separate oneAPI 2026.1.1 Release/AOT BMG-G31 build completed under an 8 GiB
memory limit. The treatment announced:

```text
SYCL experiment | direct-Q8 fixed qtail3 active: nelem=5120 wg=1024 qblocks=160
```

The strict `p0/n1` smoke used `GGML_SYCL_Q8_QUANT_DEDUP=2` and reported
`verified=1980` with `VERIFY_MISMATCH=0`.

Artifact SHA-256 values:

- accepted `libggml-sycl.so.0`: `e75b960307fccee661073e67d8288b3893f421617ea83a100cf9b8f9de38b4b5`
- treatment `libggml-sycl.so.0`: `b9201e9bd2ee787f2d8c261906036f84454192b89d32836fbac18bce88913958`
- treatment `ggml-sycl.cpp.o`: `72ba422f26f2dc33ba1ed22a520ee9483b4ce212dfa1c2f9916ae286e60be27f`
- treatment `llama-bench`: `8c9dfa5852305819778f26cb49262d01d60011c31c12f63c4e50b0664aaf4dca`

## Result

The first A-B-B-A run was excluded from the decision because a shell logging
bug collapsed all four raw filenames into one path. Its terminal-captured
pooled delta was only `+0.0206%`, consistent with the final classification,
but it is not used below.

A fresh, explicitly named `p64/n512/r3` A-B-B-A confirmation retained every
raw arm. The same treatment executable and non-SYCL libraries were used for
both arms; the control prepended the checksum-pinned accepted SYCL library to
`LD_LIBRARY_PATH`. Candidate logs contained the activation marker and control
logs did not.

| Position | Arm | Decode, tok/s |
| ---: | --- | ---: |
| 1 | Accepted | `37.755393` |
| 2 | Fixed qtail3 | `37.770944` |
| 3 | Fixed qtail3 | `37.759903` |
| 4 | Accepted | `37.736075` |

The accepted mean was `37.745734 tok/s`; treatment was
`37.7654235 tok/s`, only `+0.052164%`. This is performance-neutral and did not
earn endpoint or semantic gates. Retain the accepted dynamic loop.

The exact delta is
[`q8-collective-fixed-qtail3-neutral-20260817.diff`](../patches/q8-collective-fixed-qtail3-neutral-20260817.diff).
Structured values are in
[`2026-08-17-q8-collective-fixed-qtail3-neutral.json`](../data/2026-08-17-q8-collective-fixed-qtail3-neutral.json).
Raw local evidence is under
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-qtail3/`.

Do not retry this fixed three-slot specialization unchanged. A future retry
needs a different tail geometry or compiler/IGC.
