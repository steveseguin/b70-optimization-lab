# Qwen3.6 MoE Layer Scratch Rejected

Date: 2026-06-10

## Goal

The accepted Qwen3.6 35B-A3B Quark W8A8 INT8 TP4 32K runtime still spends
nearly all single-request decode time inside compiled model forward. The live
accepted graph cache for rank 0 contains:

| op | count |
| --- | ---: |
| `torch.ops._xpu_C.int8_gemm_w8a8` | 220 |
| `torch.ops.vllm.all_reduce` | 162 |
| `torch.ops._xpu_C.per_token_quant_int8_xpu` | 160 |
| `torch.ops.vllm_ir.rms_norm` | 101 |
| `torch.ops.vllm.gdn_attention_core_xpu` | 60 |
| `torch.ops.vllm.moe_forward_shared` | 40 |
| `torch.ops.vllm.unified_kv_cache_update` | 20 |
| `torch.ops.vllm.unified_attention_with_output` | 20 |

This screen tested whether reusing exact per-layer INT8 MoE scratch buffers
would reduce allocator/workspace overhead for decode-size MoE calls without
changing outputs.

Patch artifact:

- `patches/vllm-qwen36-xpu-moe-layer-scratch-rejected-20260610.patch`

The temporary hook added:

- `VLLM_XPU_INT8_MOE_LAYER_SCRATCH=1`
- `VLLM_XPU_INT8_MOE_LAYER_SCRATCH_MAX_ROWS=64`

It cached per-layer tensors for the current row shape:

- `remapped_hidden_states`
- `gemm1_output`
- `act_output`
- `gemm2_output`
- `rows_per_expert`
- `unpermuted_row_to_permuted_row`

The hook took precedence over the existing opt-in mixed-workspace path, and
was capped to avoid changing large prefill/profile shapes.

## Microbench Diagnostic

Artifact:

- `data/qwen36-quark-int8-moe-stage-diagnostic-20260610.json`

Command:

```bash
PYTHONPATH=/home/steve/src/vllm:/home/steve/src/vllm-xpu-kernels \
LD_LIBRARY_PATH=/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib:/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels \
ONEAPI_DEVICE_SELECTOR=level_zero:0 ZE_AFFINITY_MASK=0 \
/home/steve/.venvs/vllm-xpu/bin/python scripts/bench-qwen36-int8-moe-kernels.py \
  --rows 1,2,4,8,16 --warmup 10 --iterations 40 --tp-size 4 \
  --out data/qwen36-quark-int8-moe-stage-diagnostic-20260610.json
```

`fused_silu_quant_enabled`: `false`

| rows | custom op total us | preallocated staged total us | max abs diff |
| ---: | ---: | ---: | ---: |
| 1 | `263.2162` | `217.6993` | `0.0` |
| 2 | `258.6337` | `211.5230` | `0.0` |
| 4 | `245.6857` | `201.1152` | `0.0` |
| 8 | `264.3901` | `242.9726` | `0.0` |
| 16 | `345.2891` | `324.0588` | `0.0` |

The microbench suggested low-row preallocation could help in isolation, and
the staged path was exact versus the custom op for these shapes.

## Endpoint Speed Gate

Common runtime:

- Qwen3.6 Quark W8A8 INT8
- TP4, 32K context, no prefix caching
- `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone`
- clone-safe custom-op all-reduce
- PIECEWISE XPU graph
- max batched tokens `8192`
- max seqs `48`

Control artifact:

- `data/qwen36-quark-int8-tp4-noprefix-current-control-continue-20260610.json`

Candidate artifact:

- `data/qwen36-quark-int8-tp4-noprefix-moescratch64-single-r8-20260610.json`

| run | corrected after-first tok/s | e2e tok/s | total tok/s | TTFT ms |
| --- | ---: | ---: | ---: | ---: |
| accepted control | `99.6301` | `98.3908` | `196.7815` | `74.774` |
| per-layer scratch max rows 64 | `99.2100` | `97.9832` | `195.9664` | `74.691` |

## Decision

Reject. The isolated MoE microbench win did not survive full endpoint graph
execution. The candidate regressed the single-request speed gate, so no long
quality suite was run.

The temporary source hook was removed after measurement. The accepted service
was restored:

- tmux session: `qwen36-tp4-gdn-reusequant-clone-envclean-32k`
- backend `/health`: pass
- frontdoor `/v1/models`: pass

## Lesson

MoE scratch allocation reuse is not the next useful path for this runtime. The
compiled endpoint is bottlenecked by the full model-forward graph, where MoE,
dense INT8 quant/GEMM, GDN attention, and TP all-reduces interact. A real MoE
win likely needs lower-level kernel fusion or fewer kernel launches inside
`vllm_xpu_kernels`, not Python-side scratch reuse.
