# Qwen3.8 Q8 Level Zero weight-compression hint

Date: 2026-08-17

Status: closed performance-neutral; do not repeat unchanged

## Hypothesis and isolation

The installed B70 Level Zero driver advertises
`ZE_extension_memory_compression_hints` version 1.0. A default-off candidate
passed `ZE_MEMORY_COMPRESSION_HINTS_EXT_FLAG_COMPRESSED` only for GiB-scale
model-rank allocations owned by the custom meta-TP backend. This is a lossless
allocation property: tensor bytes, Q8 decoding, FP32 accumulation order, KV
type, kernels, collectives, sampling, and outputs are unchanged. Allocations
below 1 GiB—including the writable KV/cache and normal scratch paths—retained
the accepted allocator.

The first implementation incorrectly targeted upstream split buffers, which
the meta backend does not use for this model. Two early runs therefore lacked
the required liveness message and are invalid mechanism probes. The corrected
candidate announced the compression hint on both devices and reported
`VERIFY_MISMATCH=0` before timing.

## Result

A same-binary `p64/n512/r3` bracket used order
control-compressed-compressed-control. Both arms used equal target-only TP2,
Q8_0, F16 KV, FlashAttention, `b1024/ub256`, eight host threads, poll 50, and
no speculation.

| Process | Arm | Samples (tok/s) | Mean |
| ---: | --- | --- | ---: |
| 1 | control | `34.2400, 36.8508, 36.8193` | 35.970043 |
| 2 | compressed | `34.2442, 36.8543, 36.8326` | 35.977058 |
| 3 | compressed | `34.3241, 36.8444, 36.8316` | 36.000038 |
| 4 | control | `34.2502, 36.8290, 36.7938` | 35.957673 |

All twelve observations give `35.988533` compressed versus `35.963850`
control (`+0.068634%`). Excluding the deliberately retained cold first
repetition from each process gives `36.840725` versus `36.823225 tok/s`
(`+0.047524%`). Steady medians differ by only `+0.038969%`. This is below
resolution and is not promoted.

The likely explanation is that Q8 values are too high-entropy for the B70's
block compression to save useful HBM traffic. This agrees with the earlier
measured 7.684765-bit/value Q8 entropy audit. Both GPUs remained normal and no
new Xe/GuC fault, reset, timeout, or hang appeared.

## Provenance

- candidate SYCL library SHA-256:
  `c53bef9106061531143918b54a551b397eb30dbdecc269cedf181fdefbaee916`;
- accepted library restored after the test:
  `e75b960307fccee661073e67d8288b3893f421617ea83a100cf9b8f9de38b4b5`;
- raw evidence:
  `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-l0-weight-compression/`;
- local candidate artifact:
  `/mnt/fast-ai/artifacts/qwen38-q8-l0-weight-compression-20260817/`;
- incremental source:
  [`../patches/q8-l0-weight-compression-neutral-20260817.diff`](../patches/q8-l0-weight-compression-neutral-20260817.diff).
