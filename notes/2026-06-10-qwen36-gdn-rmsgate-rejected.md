# Qwen3.6 GDN RMS-Gate Custom Op Rejection

Date: 2026-06-10

Target runtime:

- Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- Backend: vLLM/XPU, TP4, 32K context, Quark W8A8 INT8
- Accepted base flags: no prefix caching, XPU PIECEWISE graph, `max_num_batched_tokens=8192`, `max_num_seqs=48`
- Accepted local optimization retained: `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone`

## Candidate

I tested a native XPU `_C.rms_norm_gated_silu` op for the GDN post-core path:

```text
core_attn_out = RMSNorm(core_attn_out) * silu(z)
```

The goal was to replace the compiler-emitted RMSNorm plus SiLU gate sequence after `gdn_attention_core_xpu`.

The first implementation only handled same-dtype norm weights, so the guard fell back to the existing path. I then added FP32 weight support because the real `RMSNormGated.weight` path is FP32 with BF16 activations. The active FP32-weight graph did contain `_C.rms_norm_gated_silu`.

Saved patches:

- `patches/vllm-qwen36-gdn-rmsgate-fp32w-rejected-20260610.patch`
- `patches/vllm-xpu-kernels-qwen36-gdn-rmsgate-fp32w-rejected-20260610.patch`

## Results

Accepted controls:

| Artifact | Corrected decode tok/s | E2E output tok/s | TTFT ms |
| --- | ---: | ---: | ---: |
| `data/qwen36-quark-int8-tp4-noprefix-current-control-cclipc-20260610.json` | 99.6577 | 98.4025 | 75.6044 |
| `data/qwen36-quark-int8-tp4-noprefix-current-control-continue-20260610.json` | 99.6301 | 98.3908 | 74.7738 |
| `data/qwen36-quark-int8-tp4-noprefix-restore-after-xpushared-reject-r4-20260610.json` | 99.7816 | 98.5507 | 74.1077 |

Candidate screens:

| Artifact | Path | Corrected decode tok/s | E2E output tok/s | TTFT ms |
| --- | --- | ---: | ---: | ---: |
| `data/qwen36-quark-int8-tp4-noprefix-gdn-rmsgate-single-r8-20260610.json` | inactive guard fallback | 99.2573 | 98.0123 | 75.6048 |
| `data/qwen36-quark-int8-tp4-noprefix-gdn-rmsgate-fp32w-single-r8-20260610.json` | active custom op | 99.3374 | 98.0895 | 75.6439 |

Smoke artifacts:

- `data/qwen36-quark-int8-tp4-noprefix-gdn-rmsgate-smoke-20260610.json`
- `data/qwen36-quark-int8-tp4-noprefix-gdn-rmsgate-fp32w-smoke-20260610.json`

The active custom-op candidate was stable on smoke and r8 speed screen, but slower than the accepted controls.

## Decision

Reject `VLLM_XPU_GDN_RMS_GATE_OP`.

Reason:

- The active custom-op graph was slower than the accepted graph by about `0.3%` to `0.45%` corrected decode throughput.
- The existing compiler graph already fuses nearby RMSNorm/quant work well enough that a separate native op adds launch/dispatch overhead rather than removing the bottleneck.
- Because speed lost, I did not run the full quality suite for this candidate.

Restored state:

- Restored `_C.abi3.so` from `_C.abi3.so.backup-20260610-gdn-rmsgate-precopy`.
- Reverted the candidate source edits in `/home/steve/src/vllm` and `/home/steve/src/vllm-xpu-kernels`.
- Relaunched the accepted runtime in tmux session `qwen36-tp4-gdn-reusequant-clone-envclean-32k`.

## Lesson

For this GDN post-core section, replacing only RMSNorm+SiLU with an external native op is not enough. The next useful path should either:

- fuse RMSNorm, SiLU gate, activation quant, and the following INT8 out-projection boundary together, or
- target a larger measured bottleneck outside this already-fused compiler region.
