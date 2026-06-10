# Qwen3.6 RMS INT8 Fusion And Duplicate Quant Screen

Date: 2026-06-10

## Context

This pass continued the Qwen3.6 35B A3B Quark W8A8 INT8 work on 4x Intel Arc
Pro B70. The goal was more single-request speed without changing weights,
quantization, KV dtype, sampler, context length, or quality.

Accepted comparison runtime:

- model:
  `/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118`
- cache:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-customar-clone-32k-noprefix`
- core flags:
  `--tensor-parallel-size 4`, `--max-model-len 32768`,
  `--max-num-batched-tokens 8192`, `--max-num-seqs 48`,
  `--quantization quark`, `--no-enable-prefix-caching`,
  `--compilation-config '{"cudagraph_mode":"PIECEWISE"}'`

Accepted baseline p512/n512:

| metric | value |
| --- | ---: |
| after-first output tok/s | `98.8844` |
| corrected after-first output tok/s | `98.6912` |
| e2e output tok/s | `97.4280` |
| mean client TTFT | `77.39 ms` |

## RMSNorm Plus INT8 Quant Fusion

Patch artifacts:

- `patches/vllm-xpu-kernels-qwen36-rms-int8-bf16-fp32-20260610.patch`
- `patches/vllm-qwen36-rms-int8-and-dedup-hooks-20260610.patch`

Kernel changes:

- allowed BF16 activation + FP32 RMS weight + INT8 output in
  `_C::rms_norm_dynamic_per_token_quant`;
- used BF16 rounding before INT8 quant for the Qwen/Gemma-style case;
- used `max(absmax, 1e-10) / 127` for INT8 scale;
- clamped to `[-127, 127]`.

Direct unit result:

| check | result |
| --- | ---: |
| rows=1 exact INT8 | `true` |
| rows=18 INT8 match | `99.9566%` |
| rows=18 max abs diff | `1` |
| rows=18 nonzero diffs | `16` |
| scale max abs diff | `0.0` |
| fused micro time | `0.00754 ms` |
| reference time | `0.14772 ms` |
| micro speedup | `19.59x` |

Endpoint result:

- `VLLM_XPU_FUSE_RMS_INT8_QUANT=1`
- fresh cache:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-rmsint8fp32-32k-noprefix`
- explicit `pass_config.fuse_norm_quant=true` cache:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-rmsint8fp32-fusenorm-32k-noprefix`

Graph inspection still showed the unchanged baseline counts:

- `4` `computation_graph.py` files
- `2640` `per_token_quant_int8_xpu` occurrences
- `404` `vllm_ir.rms_norm` occurrences
- `2200` `int8_gemm_w8a8` occurrences

Decision: reject for now. The kernel micro-test is promising, but the endpoint
pattern did not match the real graph. The likely blocker is that the normalized
activation has multiple users before adjacent INT8 GEMMs, so the existing
single RMSNorm+quant pattern cannot legally replace it.

Artifact:

- `data/qwen36-quark-int8-rmsint8fp32-unit-20260610.json`

## Duplicate INT8 Quant Reuse

Patch artifact:

- `patches/vllm-qwen36-xpu-dedup-int8-quant-pass-20260610.patch`

New opt-in env:

- `VLLM_XPU_DEDUP_INT8_QUANT=1`

Intent:

- identify repeated `_xpu_C.per_token_quant_int8_xpu` calls fed by the same
  base activation after only view/reshape/contiguous reshaping;
- replace later duplicate quant tuple users with the first quant tuple;
- keep quality unchanged by reusing exactly the same quantized tensor and scale.

Runtime:

- session: `qwen36-tp4-dedupquant-32k`
- cache:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-dedupquant3-32k-noprefix`
- log:
  `/tmp/qwen36-quark-int8-tp4-dedupquant3-32k-noprefix.log`

Compile logs confirmed the pass executed:

- `Enabling XPU duplicate INT8 quant elimination pass`
- several subgraphs reported `removed 1 duplicates`
- startup removed `3` duplicate quant calls per rank across the logged
  partitions

The saved `computation_graph.py` counts did not change:

- `4` files
- `2640` `per_token_quant_int8_xpu`
- `404` `vllm_ir.rms_norm`
- `2200` `int8_gemm_w8a8`

That file appears to be pre-pass or otherwise not a reliable post-pass artifact
for this transform, so the candidate was benchmarked live.

Single p512/n512:

| metric | accepted | dedupquant3 |
| --- | ---: | ---: |
| after-first output tok/s | `98.8844` | `99.1345` |
| corrected after-first output tok/s | `98.6912` | `98.9409` |
| e2e output tok/s | `97.4280` | `97.6498` |
| mean client TTFT | `77.39 ms` | `78.54 ms` |

Quality through the LAN frontdoor:

- exact checks: pass
- long-context recall: pass
- baseline parity: pass
- repeat stability: fail

Repeat failures:

- 16-repeat run: `15/16` expected output, one junk output:
  `伪伪... whiskey whiskey ... = = =`
- 32-repeat rerun: `31/32` expected output, one outlier:
  `blue whiskey whiskey green, orange, red`

Fairness control after restoring the accepted no-dedup service:

- exact checks: pass
- long-context recall: pass
- baseline parity: pass
- 32-repeat stability: pass

Direct `18080` quality was not comparable because the LAN frontdoor applies the
chat behavior used by the accepted baseline; direct backend checks failed all
exact cases and were not used for the adoption decision.

Decision: reject for production for now. The speed movement is small and inside
the accepted profile's normal performance tier, while repeat reliability is not
acceptable. The accepted no-dedup service was restored.

Artifacts:

- `data/qwen36-quark-int8-tp4-noprefix-dedupquant3-single-20260610.json`
- `data/qwen36-quark-int8-tp4-noprefix-dedupquant3-frontdoor-quality-20260610.json`
- `data/qwen36-quark-int8-tp4-noprefix-dedupquant3-frontdoor-quality-rerun32-20260610.json`
- `data/qwen36-quark-int8-tp4-noprefix-dedupquant3-direct-quality-rerun32-20260610.json`
- `data/qwen36-quark-int8-tp4-noprefix-accepted-frontdoor-quality-rerun32-20260610.json`

## Operational Lesson

Do not overwrite `vllm_xpu_kernels/_C.abi3.so` while a vLLM worker has it
mapped. A crash seen during this work was most likely caused by replacing the
loaded shared object during an active service, not by the model recipe itself.
Stop the endpoint before swapping rebuilt extension binaries.

## Current Service

The live service was restored to the accepted no-prefix TP4 32K profile without
`VLLM_XPU_DEDUP_INT8_QUANT` and without RMS INT8 fusion enabled.

## Additional Scheduler/KV Screen: Disable Hybrid KV

Candidate:

- flag delta: `--disable-hybrid-kv-cache-manager`
- session: `qwen36-tp4-noprefix-nohybridkv-32k`
- cache:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-nohybridkv-32k-noprefix`
- log:
  `/tmp/qwen36-quark-int8-tp4-nohybridkv-32k-noprefix.log`

Result: startup failure before serving.

The engine warned that the hybrid KV cache manager was disabled for a hybrid
model, then failed KV cache initialization:

`ValueError: Hybrid KV cache manager is disabled but failed to convert the KV cache specs to one unified type.`

This is not a performance knob for this checkpoint as currently configured.
Rejected without running speed or quality gates. The accepted no-prefix TP4 32K
service was restored after the failed startup.

Artifact:

- `data/qwen36-quark-int8-tp4-noprefix-nohybridkv-startup-fail-20260610.json`
