# Qwen3.6 Quark INT8: Generic GDN Decode Screen

Date: 2026-06-10

## Goal

Screen an existing vLLM generic packed GatedDeltaNet decode path as a possible
quality-preserving single-request speed improvement for:

- Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- Runtime: TP4, 32K context, Quark W8A8 INT8 weights, BF16 runtime dtype
- Baseline service: no prefix cache, PIECEWISE XPU graph, custom-op all-reduce

The prior forward-timing/profiler pass showed decode time dominated by the model
forward path, with visible attribution pointing at linear-attention/GDN work and
high kernel-launch count. This candidate tested whether routing decode through
vLLM's existing generic packed recurrent GDN decode helper would reduce overhead
without changing model weights or precision.

## Candidate

Patch artifact:

- `patches/vllm-qwen36-gdn-generic-decode-env-20260610.patch`

Runtime flag:

```bash
export VLLM_XPU_GDN_FORCE_GENERIC_DECODE=1
```

The guard only applies to non-spec decode metadata:

- `spec_sequence_masks is None`
- `num_prefills == 0`
- `num_decodes > 0`

Prefill remains on the existing XPU custom GDN path.

## Result

Direct backend p512/n512, streamed, 8 measured repeats, 64-token warmup excluded:

| Run | Corrected decode tok/s | E2E tok/s | TTFT ms |
| --- | ---: | ---: | ---: |
| Accepted control | 98.7741 | 97.5295 | 76.2834 |
| Generic GDN decode | 98.5636 | 97.3264 | 76.1818 |

The candidate is functionally viable but does not improve single-request speed.
It is slightly below the accepted control within this screen:

- Corrected decode: -0.21 tok/s
- E2E: -0.20 tok/s
- TTFT: effectively unchanged

## Decision

Rejected for production. Do not enable `VLLM_XPU_GDN_FORCE_GENERIC_DECODE` in the
accepted runtime.

The result is still useful because it rules out a simple Python-level route to
the existing packed decode helper. The remaining promising path is lower-level:
reduce launches or fuse work in the XPU GDN custom op path rather than replacing
it with the generic helper.

## Reproduce

Start from the accepted TP4/32K/no-prefix service config and use a fresh graph
cache:

```bash
export VLLM_CACHE_ROOT=/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-gdn-generic-decode-32k-noprefix
export VLLM_ENABLE_PREFIX_CACHING=0
export VLLM_XPU_GDN_FORCE_GENERIC_DECODE=1
```

Benchmark:

```bash
/home/steve/.venvs/vllm-xpu/bin/python scripts/measure-openai-endpoint-metrics.py \
  --base-url http://127.0.0.1:18080 \
  --out data/qwen36-quark-int8-tp4-noprefix-gdn-generic-decode-single-20260610.json \
  --prompt-tokens 512 \
  --output-tokens 512 \
  --repeats 8 \
  --warmup-output-tokens 64 \
  --mode stream \
  --skip-vram
```

