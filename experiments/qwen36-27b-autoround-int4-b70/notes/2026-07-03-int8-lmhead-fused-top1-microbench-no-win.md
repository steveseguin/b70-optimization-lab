# 2026-07-03 - INT8 LM-head fused top-1 microbench no-win

## Purpose

Test the next plausible verifier-cost reduction after the runtime INT8 LM-head
win: skip materializing full logits and return only exact top-1 from a fused
INT8 LM-head kernel.

This was diagnostic-only. It was not a model-quality or fresh-response
throughput benchmark.

## Patch / artifact

- Prototype patch:
  `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-kernels-int8-lm-head-top1-microbench-no-win-20260703.patch`
- Microbench harness:
  `scripts/bench-int8-lm-head-top1.py`
- Result JSON:
  `data/qwen36-27b-autoround-int4-b70-baselines/int8-lmhead-top1-microbench-smoke-20260703.json`

The prototype added an isolated `_xpu_C::int8_lm_head_top1_out` op in
`vllm-xpu-kernels`. It was built in an isolated CMake directory and was never
installed over the production extension.

## Result

Synthetic real-shape smoke (`rows=1`, hidden `5120`, vocab `248320`, BF16
hidden, INT8 transposed LM-head):

| path | median ms |
| --- | ---: |
| current path: `per_token_quant_int8_xpu + int8_gemm_w8a8 + argmax` | `2.690` |
| prototype fused scalar top-1 scan | `2704.287` |

Top-1 matched the baseline in the smoke (`0` mismatches), but performance was
about **1000x slower**. This design is closed.

## Interpretation

The naive "one workgroup scans vocab and loops hidden serially" design cannot
compete with oneDNN GEMM. Any future exact LM-head top-1 work must use a real
matrix/tile design with a top-1 epilogue or a compact candidate-vs-max verifier;
do not retry scalar full-vocab dot products.

The active source edits were reverted after saving this patch/result.
