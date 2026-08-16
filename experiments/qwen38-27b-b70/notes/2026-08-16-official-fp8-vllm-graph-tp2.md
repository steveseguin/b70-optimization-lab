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
- `enable_qk_norm_rope_fusion=true` produced the fused XPU custom op in both
  rank artifacts and passed the full oracle. Its two medians were
  `21.740997` and `21.690559 tok/s`, bracketing control at `+0.150%` and
  `-0.083%`; do not promote this endpoint-neutral pass.
- Reloading 515 MB of cached AOT artifacts briefly exceeded an 8 GiB host
  cgroup and OOM-killed one worker. A 9 GiB RAM / 12 GiB RAM-plus-swap retry
  passed. The host stayed responsive and the cards recorded no reset/fault.
- Prefix caching is disabled. The final image exposes prompt token details,
  and all measured rows reported zero cached tokens.
- vLLM warns XPU Graph is officially single-GPU-only. Keep this TP2 path
  experimental and preserve the fail-closed quality gate.

## Next optimization target

The generic log says the CUDA-only fused GDN kernel falls back to Triton, but
source inspection found that XPU's `forward_xpu()` independently calls the
fused SYCL `_xpu_C.gdn_attention` custom op. Do not port a duplicate fused GDN
wrapper based on the misleading generic log. The remaining credible targets
are inside that SYCL kernel and around TP2 synchronization.

The official 2026-08-16 nightly at vLLM `8efa13b70` bumped
`vllm-xpu-kernels` from `0.1.12.3` to `0.1.13.2`. A same-config PIECEWISE run
measured `21.723631 tok/s`, only `+0.070%` over the pinned baseline, and passed
the full oracle. Upstream kernel history contains no post-baseline GDN change;
the package bump mainly brings oneDNN and unrelated attention/MoE fixes. Do
not promote the nightly for this noise-level delta. Simple oneCCL P2P topology
toggling is likewise closed.

Reproduction is in
[`repro/qwen38-27b-fp8-vllm-tp2-asrock-b70`](../../../repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/README.md),
and the concise machine-readable record is
[`data/2026-08-16-official-fp8-vllm-graph-tp2.json`](../data/2026-08-16-official-fp8-vllm-graph-tp2.json).
