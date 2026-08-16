# Official Qwen3.8 FP8 vLLM/XPU TP2 baseline

## Decision

Promote the newer official vLLM/XPU image as a working, quality-gated FP8 TP2
baseline, but not as the fastest Qwen3.8 route. The stable graph result is
`21.708532 tok/s`, well below the accepted GGUF Q8_0 TP2 result. Its purpose is
to give future vLLM GDN and collective work a reproducible control.

## What changed from the failed bring-up

The older `intel/llm-scaler-vllm:0.21.0-b3.1` image recognized and loaded the
model but failed bounded TP2 initialization. The successful runtime is
`vllm/vllm-openai-xpu` digest
`f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f`,
with vLLM `0.27.2rc1.dev77+gac7509e2b` and Torch `2.13.0+xpu`.

The newer image selected the native `XPUFp8BlockScaledMMKernel`. Eager mode
reached `17.097358 tok/s`. PIECEWISE capture of the size-one decode graph
reached `21.708532 tok/s`, a `26.97%` gain. The graph occupied 0.12 GiB/card.

## Exact result and quality

The final measurement used five deterministic unique prompts, each completing
128 tokens after a separate warmup. The median after-TTFT rate was
`21.708532114979 tok/s`, wall rate `19.624649424876 tok/s`, and TTFT
`0.626227378001 s`. Every request reported `cached_tokens=0`; decode CV was
`0.0738%`.

The graph endpoint passed seven exact semantic canaries, eight-run repeat
stability, and a 3,829-token needle test. All checked hashes matched the Q8_0
oracle. Longer free-form continuations were not universally byte-identical
between eager and graph execution, so the result is quality-gated rather than
advertised as arbitrary-prompt token exactness.

## Closed side arms and safety

- `CCL_TOPO_P2P_ACCESS=1` measured `21.706164 tok/s`, `-0.011%` versus the
  default-off graph control; keep it off.
- `FULL_DECODE_ONLY` measured `21.357193 tok/s`, `-1.618%` versus PIECEWISE.
  It passed the same semantic/repeat/needle oracle; retain PIECEWISE.
- Reloading 515 MB of cached AOT artifacts briefly exceeded an 8 GiB host
  cgroup and OOM-killed one worker. A 9 GiB RAM / 12 GiB RAM-plus-swap retry
  passed. The host stayed responsive and the cards recorded no reset/fault.
- Prefix caching is disabled. The final image exposes prompt token details,
  and all measured rows reported zero cached tokens.
- vLLM warns XPU Graph is officially single-GPU-only. Keep this TP2 path
  experimental and preserve the fail-closed quality gate.

## Next optimization target

The image still warms Qwen Triton kernels for `qwen3_5_text`; the native fused
GDN decode path used in older lab work is absent. Porting direct recurrent-state
I/O and reducing TP2 synchronization around Qwen3.8's GDN blocks is the most
credible source-level vLLM arm. Simple oneCCL P2P topology toggling is closed.

Reproduction is in
[`repro/qwen38-27b-fp8-vllm-tp2-asrock-b70`](../../../repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md),
and the concise machine-readable record is
[`data/2026-08-16-official-fp8-vllm-graph-tp2.json`](../data/2026-08-16-official-fp8-vllm-graph-tp2.json).
