# Qwen3.6 INT8 MoE Mixed Workspace Rejected

Date: 2026-06-10

## Context

The accepted Qwen3.6 INT8 runtime spends almost all steady decode time inside
the compiled model forward graph. The compiled graph contains many XPU INT8 MoE
calls, so I screened the existing XPU INT8 MoE scratch-allocation switch:

- `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1`

This flag changes how XPU INT8 MoE scratch tensors are acquired from the shared
workspace manager. It should not change weights, quantization, activation dtype,
sampling, context length, or model math.

Everything else stayed aligned with the accepted runtime:

- model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- TP4, 32K context
- Quark W8A8 INT8, BF16 runtime
- XPU PIECEWISE graph capture
- clone-safe custom-op all-reduce
- prefix caching disabled
- `--max-num-batched-tokens 8192`
- `--max-num-seqs 48`

## Candidate Runtime

Runtime:

- tmux session: `qwen36-tp4-noprefix-moe-mixedws-32k`
- cache root:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-customar-clone-32k-noprefix`
- log:
  `/tmp/qwen36-quark-int8-tp4-moe-mixedws-32k-noprefix-20260610.log`

Startup succeeded and loaded the accepted AOT graph directly:

- `Using XPU Int8 MoE backend`
- `Using MoEPrepareAndFinalizeNoDPEPModular`
- AOT graph loaded for all four ranks
- `torch.compile` total: `3.73 s`
- available KV cache memory: `20.42 GiB`
- GPU KV cache size: `2,028,339 tokens`
- reported maximum concurrency for 32K requests: `61.90x`
- graph capture: `12 s`

For comparison, the restored accepted backend after this screen reports:

- available KV cache memory: `20.67 GiB`
- GPU KV cache size: `2,052,915 tokens`
- reported maximum concurrency for 32K requests: `62.65x`

The workspace route therefore costs about `0.25 GiB` of KV headroom on this
launch.

## Single-Request Speed

Artifact:

- `data/qwen36-quark-int8-tp4-noprefix-moe-mixedws-single-20260610.json`

p512/n512, stream mode, eight measured repeats:

| metric | accepted control | MoE mixed workspace |
| --- | ---: | ---: |
| corrected output tok/s after first chunk | `98.7741` | `98.3645` |
| output tok/s end-to-end | `97.5295` | `97.1736` |
| mean client TTFT | `76.28 ms` | `73.96 ms` |

TTFT improved, but the decode speed gate is lower than the accepted control.

## Decision

Reject `VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1` for the current Qwen3.6 production
candidate.

I did not run full quality or concurrency gates because the single-request speed
condition failed. This remains a useful diagnostic: the workspace path is
startup-safe and likely math-preserving, but it gives up KV headroom and does
not improve steady single-request decode throughput.

## Restore

After rejection, I restored the accepted backend:

- tmux session: `qwen36-tp4-noprefix-32k`
- `/health`: pass
- `/v1/completions` smoke: pass, returned `qwen36 smoke ok` after the raw
  thinking wrapper

Keep the accepted runtime on the no-prefix TP4 32K profile.
