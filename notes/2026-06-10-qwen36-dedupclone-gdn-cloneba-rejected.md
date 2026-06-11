# Qwen3.6 INT8 Dedup Clone and GDN Clone-BA Rejections

Date: 2026-06-10

## Context

These were follow-ups on the accepted Qwen3.6 35B-A3B Quark W8A8 INT8 no-prefix
runtime. The goal was to reduce redundant INT8 activation quantization or clone
overhead without changing model weights, quantization format, tensor-parallel
layout, sampling, or chat-template behavior.

Accepted control family:

- model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- hardware: 4x Intel Arc Pro B70 32GB
- runtime: local vLLM XPU TP4, BF16 runtime, 32K context
- graph: XPU PIECEWISE graph capture
- prefix caching: disabled
- accepted GDN mode: `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone`
- accepted speed reference: `99.32` corrected after-first output tok/s,
  `97.98` e2e output tok/s, and `79.45 ms` TTFT across eight p512/n512
  repeats.
- stronger later restore reference: `99.78` corrected after-first output tok/s,
  `98.55` e2e output tok/s, and `74.11 ms` TTFT across four p512/n512 repeats.

Patch snapshot:

- `patches/vllm-qwen36-dedupclone-gdn-cloneba-rejected-20260611.patch`

## Candidate 1: INT8 Quant Dedup Clone

Runtime:

- session: `qwen36-tp4-dedupquant-clone-envregistered-32k`
- cache root:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-dedupquant-clone-envregistered-32k-noprefix`
- log:
  `/tmp/qwen36-quark-int8-tp4-dedupquant-clone-envregistered-32k-noprefix-20260611.log`
- env:
  `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone`
- env:
  `VLLM_XPU_DEDUP_INT8_QUANT=clone`

The first attempt had not actually enabled clone mode because the env var was
not registered in `envs.py` and the pass manager only accepted `1`. After
registering the env and allowing `clone`, the pass ran during graph compile.

The compile logs showed no useful rewrite opportunities in the current lowered
graphs:

- saw `1` or `2` INT8 quant nodes per graph
- removed `0` duplicate quant nodes
- inserted `0` cloned tuple outputs

Startup was otherwise normal:

- model load memory: `8.58 GiB`
- available KV cache memory: `20.67 GiB`
- 32K maximum concurrency: `62.65x`
- graph capture: `12 sec`
- frontdoor smoke: exact `OK`

Single-request p512/n512 speed, four repeats:

| metric | result |
| --- | ---: |
| corrected output tok/s after first chunk | `99.19` |
| output tok/s end-to-end | `97.10` |
| mean TTFT | `122.22 ms` |
| median TTFT | `75.29 ms` |

Artifact:

- `data/qwen36-quark-int8-tp4-noprefix-dedupquant-clone-envregistered-single-r4-20260611.json`

Decision: reject. The pass was effectively a no-op for the current graph and
the measured e2e speed did not beat the accepted clone control. The high mean
TTFT was one outlier, but there is no promotion signal to justify a full quality
sweep.

## Candidate 2: GDN Clone-BA

Runtime:

- session: `qwen36-tp4-gdn-reusequant-cloneba-32k`
- cache root:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-gdn-reuseqkvzbaquant-cloneba-32k-noprefix`
- log:
  `/tmp/qwen36-quark-int8-tp4-gdn-reuseqkvzbaquant-cloneba-32k-noprefix-20260611.log`
- env:
  `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone-ba`
- `VLLM_XPU_DEDUP_INT8_QUANT` unset

The accepted `clone` mode clones both the quantized activation tensor and scale
for both GDN input-projection consumers. The clone-BA variant kept the original
quant outputs for `qkvz` and cloned only the `ba` consumer. This preserves
distinct storage across the two GEMMs while cutting the clone count in half.

Startup was normal:

- model load memory: `8.58 GiB`
- available KV cache memory: `20.67 GiB`
- 32K maximum concurrency: `62.65x`
- graph capture: `13 sec`
- frontdoor smoke: exact `OK`

Single-request p512/n512 speed, eight repeats:

| metric | accepted clone control | clone-BA |
| --- | ---: | ---: |
| corrected output tok/s after first chunk | `99.32` | `99.17` |
| output tok/s end-to-end | `97.98` | `97.90` |
| mean TTFT | `79.45 ms` | `76.94 ms` |

Artifact:

- `data/qwen36-quark-int8-tp4-noprefix-gdn-cloneba-single-r8-20260611.json`

Decision: reject at the speed gate. The result is close, but it is below the
accepted clone control and below the stronger later restore reference. No full
quality suite was run because the candidate did not produce a speed win.

## Candidate 3: GDN Clone-QKVZ

Runtime:

- session: `qwen36-tp4-gdn-reusequant-cloneqkvz-32k`
- cache root:
  `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-gdn-reuseqkvzbaquant-cloneqkvz-32k-noprefix`
- log:
  `/tmp/qwen36-quark-int8-tp4-gdn-reuseqkvzbaquant-cloneqkvz-32k-noprefix-20260611.log`
- env:
  `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone-qkvz`
- `VLLM_XPU_DEDUP_INT8_QUANT` unset

This was the mirror image of clone-BA: clone only the `qkvz` quantized
activation and scale, while passing the original quant outputs to `ba`.

Startup was normal:

- model load memory: `8.58 GiB`
- available KV cache memory: `20.67 GiB`
- 32K maximum concurrency: `62.65x`
- graph capture: `13 sec`
- FastAPI startup: pass

The first real frontdoor chat smoke then failed with HTTP `500`. The backend
log showed `UR_RESULT_ERROR_DEVICE_LOST` on the first scheduled request, before
any speed benchmark could run. The first stack pointed at block-table host to
device copy:

- `vllm/v1/worker/block_table.py commit_block_table -> copy_to_gpu`
- scheduled prompt tokens: `17`
- scheduled max output tokens: `8`

The candidate was killed, all four B70s still enumerated through `xpu-smi` and
`torch.xpu`, and the accepted `clone` runtime was restored.

Artifact:

- `data/qwen36-quark-int8-tp4-noprefix-gdn-cloneqkvz-device-lost-20260611.json`

Decision: reject as a stability failure. Do not benchmark or quality-sweep this
mode unless the first-request device loss can be reproduced and fixed in an
isolated graph/cache run.

## Restore

After both rejected screens, the accepted backend was restored:

- session: `qwen36-tp4-gdn-reusequant-clone-envclean-32k`
- log:
  `/tmp/qwen36-quark-int8-tp4-gdn-reuseqkvzbaquant-clone-envclean-32k-noprefix-restore-20260611.log`
- env:
  `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone`
- `VLLM_XPU_DEDUP_INT8_QUANT` unset

Restore startup:

- graph capture: `13 sec`
- FastAPI startup: pass
- frontdoor generation smoke: exact `OK`

Short frontdoor quality sanity:

| check | result |
| --- | --- |
| exact canaries | pass |
| JSON field semantics | pass |
| 8-repeat stability | pass |
| baseline exact/hash parity | pass |

Restore sanity artifact:

- `data/qwen36-quark-int8-tp4-noprefix-restore-after-dedupclone-cloneba-short-quality-20260611.json`

After the later clone-QKVZ stability rejection, the accepted backend was
restored again:

- session: `qwen36-tp4-gdn-reusequant-clone-envclean-32k`
- log:
  `/tmp/qwen36-quark-int8-tp4-gdn-reuseqkvzbaquant-clone-envclean-32k-noprefix-restore-after-cloneqkvz-20260611.log`
- graph capture: `12 sec`
- FastAPI startup: pass
- frontdoor generation smoke: exact `OK`
- error scan: no `UR_RESULT_ERROR_DEVICE_LOST`, traceback, runtime error, or
  error entries

## Next

Do not spend more time on generic duplicate-quant elimination for this exact
lowered graph shape unless a graph dump shows true duplicate quant consumers.
Do not promote `clone-ba` or `clone-qkvz`; the existing full `clone` mode
remains the safer accepted GDN quant-reuse recipe.

Next quality-preserving speed work should target actual hot boundaries:

- exact dense RMS/quant/GEMM fusion with Qwen's current FP32 norm-weight
  semantics preserved;
- dense W8A8 small-M GEMM epilogue or allocation reuse;
- MoE scratch or epilogue work only when full-model p512/n512 speed improves
  before quality sweep.
