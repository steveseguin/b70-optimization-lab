# Qwen3.8 GDN INT4 prefill pad D37 preregistration

Date: 2026-08-31

Status: **preregistered before the D37 image build or model requests**

D36 made the complete layer-0 GDN call-2 boundary byte-identical in four fresh
processes by running the loaded quantized BA and output projections at M=512
from Python-ordered padded inputs. D37 packages that exact mechanism in
`QwenGatedDeltaNetAttention.forward_xpu` for all GDN layers whenever
`32 < num_tokens < 512` and the explicit environment gate
`VLLM_XPU_QWEN_GDN_INT4_PREFILL_PAD512=1` is enabled. Existing FP16/BF16 BA
handling, QKVZ, M<=32 decode/batched-decode, M>=512, and unrelated linears are
unchanged.

The patch and image must be hash-bound after this preregistration. First gate:
the same four-fresh-process layer-0 call-2 trace on the packaged image, using
the ordinary stage tracer without a repair hook. All stages and 64 generated
token IDs must match. Only then may the strict varied-prompt cross-process
determinism and independent quality suites run. Cold performance A/B is last;
no one-prompt or warm-cache number may be promoted.
