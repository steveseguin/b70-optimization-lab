# Qwen27 TP2/FP16 W4A16 accumulation modes: no win

## Result

This lane is closed as a diagnostic no-win. It did not run an endpoint and is
not eligible for LocalMaxxing.

The first version of the W4A16 row-scaling harness used global TP1/BF16 shapes.
That was not representative of the promoted `93.036242 tok/s` TP2/FP16 record.
The harness now defaults to the real per-rank TP2 projection shapes and FP16
activations/scales, while retaining `--profile tp1-bf16` for historical use.

## Experiment

The default-off patch in
`patches/qwen36-27b-autoround-int4-b70/vllm-xpu-w4a16-accumulation-modes-20260711.patch`
exposed oneDNN accumulation modes `strict`, `f16`, `relaxed`, and `any`. Each
mode ran in a fresh process because the outer vLLM oneDNN primitive cache does
not include accumulation mode in its key. Four rotations assigned every mode
to every B70, with identical inputs and captured output tensors.

Raw artifacts:

`/mnt/usb-models/llm-optimization-artifacts/qwen27-w4a16/accumulation-tp2-fp16-20260711T225146Z`

Compact result:

`data/qwen36-27b-autoround-int4-b70-baselines/qwen27-w4a16-accumulation-tp2-fp16-20260711.json`

Median paired projected-W4 deltas versus strict were `+0.12%` for `f16`,
`-1.67%` for `relaxed`, and `-0.78%` for `any`. Per-card deltas changed sign
and ranged from about `-6.34%` to `+4.56%`. All candidate outputs were exactly
equal to strict across `770,048` compared FP16 elements per mode.

oneDNN verbose output confirmed the same `gpu,gemm,jit:gemm` implementation for
strict and relaxed; relaxed added `attr-acc-mode:relaxed`. Source inspection
showed that the optimized U4 weight-decompression path forces the main
accumulator back to FP32 for `f16` and `any`. Relaxed can affect partial sums in
some strategies, but it had no numerical or stable timing effect here.

## Decision

Do not build or validate an endpoint for this patch. The apparent sub-2%
medians are below observed card/time drift and are contradicted by the paired
sign changes. Restore the production extension and source after preserving the
patch. The next substantive target-forward lane is ReplaySSM Q/K precompute and
reuse across value buckets while retaining `v_dim_per_sg=4`.
