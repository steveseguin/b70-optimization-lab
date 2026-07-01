# Qwen3.6 GDN qkvz/ba Quant Reuse

Date: 2026-06-10

## Goal

Test whether the Qwen3.6 GatedDeltaNet input projections can reuse one XPU
W8A8 activation quantization for both `in_proj_qkvz` and `in_proj_ba`.

The expected upside is small but targeted: remove one redundant
`per_token_quant_int8_xpu` call per GDN block on decode without changing model
weights, activation dtype, sampler behavior, context length, or routing.

## Baseline

Current accepted direct single-request control:

- artifact: `data/qwen36-quark-int8-tp4-noprefix-accepted-control-current-20260610.json`
- corrected after-first output speed: `98.7741 tok/s`
- e2e output speed: `97.5295 tok/s`
- mean client TTFT: `76.28 ms`
- model load memory: `8.58 GiB`
- available KV cache memory: `20.67 GiB`
- GPU KV cache size: `2,052,915 tokens`
- max 32K concurrency estimate: `62.65x`

## Unguarded Reuse Rejected

Patch behavior:

- compute `x_q, x_s = per_token_quant_int8_xpu(hidden_states_2d)` once
- feed the same `x_q` and `x_s` tensors to both `int8_gemm_w8a8` calls
- keep separate `qkvz` and `ba` GEMM outputs, avoiding the earlier fused-output
  contiguity failure

Startup and smoke passed. Direct speed was a tiny win:

- artifact: `data/qwen36-quark-int8-tp4-noprefix-gdn-reuseqkvzbaquant-single-20260610.json`
- corrected after-first output speed: `99.0948 tok/s`
- e2e output speed: `97.8504 tok/s`
- mean client TTFT: `75.80 ms`

Quality failed repeat stability:

- frontdoor quality artifact: `data/qwen36-quark-int8-tp4-noprefix-gdn-reuseqkvzbaquant-frontdoor-quality-rerun32-20260610.json`
- direct repeat artifact: `data/qwen36-quark-int8-tp4-noprefix-gdn-reuseqkvzbaquant-direct-quality-repeat64-20260610.json`
- exact canaries and long-context recall passed through the frontdoor
- baseline hash comparisons passed for exact cases and long-context recall
- repeat stability failed with intermittent unrelated-token injection, including:
  - `idor. whiskey whiskey whiskey whiskey = = = = = =`
  - `粉红色blue, green, orange, red`

Decision: reject `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=1`. The shared quantized
activation tensors are not reliability-safe with the current XPU custom op and
graph path.

## Clone-Guarded Reuse

Patch behavior:

- `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone`
- compute `x_q, x_s` once
- clone both quant tensors for each GEMM consumer before calling
  `int8_gemm_w8a8`
- keep separate GEMM outputs

Patch artifact:

- `patches/vllm-qwen36-gdn-reuseqkvzbaquant-clone-20260610.patch`

Patch hygiene refresh:

- the patch artifact now registers
  `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT` in `vllm/envs.py`;
- the GDN model file reads `envs.VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT` instead of
  calling `os.getenv` directly;
- touched vLLM files passed `python -m py_compile`;
- the patch applies cleanly against a fresh vLLM HEAD worktree.

Env-registration restart validation:

- session: `qwen36-tp4-gdn-reusequant-clone-envclean-32k`
- cache root: `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-gdn-reuseqkvzbaquant-clone-envclean-32k-noprefix`
- log: `/tmp/qwen36-quark-int8-tp4-gdn-reuseqkvzbaquant-clone-envclean-32k-noprefix-20260610.log`
- backend health check passed on `127.0.0.1:18080`
- `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT` is no longer reported as an unknown vLLM
  environment variable;
- Torch compile still emits `Failed to read file <frozen os>` on all four
  worker ranks, so that warning is not caused solely by this GDN env lookup and
  should be tracked separately;
- startup telemetry stayed in family: `8.58 GiB` model-load memory,
  `20.67 GiB` available KV cache memory, `2,052,915` KV tokens, `62.65x`
  estimated 32K concurrency, `54.51 s` torch.compile, and `12 s` graph capture;
- `xpu-smi` after load shows about `32655 MiB` used per device because vLLM
  reserves the configured GPU memory budget. The practical headroom is the
  already-allocated KV cache capacity, not free OS-visible VRAM.

Runtime:

- session: `qwen36-tp4-gdn-reusequant-clone-32k`
- cache root: `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-gdn-reuseqkvzbaquant-clone-32k-noprefix`
- log: `/tmp/qwen36-quark-int8-tp4-gdn-reuseqkvzbaquant-clone-32k-noprefix-20260610.log`
- model load memory: `8.58 GiB`
- model loading: `14.148619 s`
- `torch.compile`: `55.35 s`
- initial profiling/warmup: `4.57 s`
- available KV cache memory: `20.67 GiB`
- GPU KV cache size: `2,052,915 tokens`
- max 32K concurrency estimate: `62.65x`
- graph capture: `12 s`, `-0.04 GiB`

Quality:

- artifact: `data/qwen36-quark-int8-tp4-noprefix-gdn-reuseqkvzbaquant-clone-frontdoor-quality-rerun32-20260610.json`
- route: frontdoor, `http://127.0.0.1:8000`
- exact canaries: pass
- 32-repeat deterministic hash stability: pass
- long-context needle recall at requested 8192 tokens: pass
- accepted-baseline comparisons: pass

Longer reliability refresh:

- artifact: `data/qwen36-quark-int8-tp4-noprefix-gdn-reuseqkvzbaquant-clone-frontdoor-quality-rerun64-20260610.json`
- exact canaries: pass
- 64-repeat deterministic hash stability: pass
- long-context needle recall at requested 8192 tokens: pass
- accepted-baseline comparisons: pass

Single-request speed:

- artifact: `data/qwen36-quark-int8-tp4-noprefix-gdn-reuseqkvzbaquant-clone-single-20260610.json`

| metric | accepted | clone reuse | delta |
| --- | ---: | ---: | ---: |
| corrected after-first output tok/s | `98.7741` | `99.1063` | `+0.3323` |
| e2e output tok/s | `97.5295` | `97.7869` | `+0.2574` |
| total tok/s | `195.0589` | `195.5738` | `+0.5149` |
| mean client TTFT | `76.28 ms` | `79.80 ms` | `+3.52 ms` |

Longer 16-repeat speed refresh:

- artifact: `data/qwen36-quark-int8-tp4-noprefix-gdn-reuseqkvzbaquant-clone-single-r16-20260610.json`
- corrected after-first output speed: `98.9941 tok/s`
- corrected after-first min/max: `98.4003` / `99.7235 tok/s`
- e2e output speed: `97.7260 tok/s`
- mean client TTFT: `76.84 ms`

This refresh remains above the accepted control, but the mean delta is still
small enough to treat as a micro-win rather than a large breakthrough.

Env-clean fresh-cache quality and speed refresh:

- quality artifact: `data/qwen36-quark-int8-tp4-noprefix-gdn-reuseqkvzbaquant-clone-envclean-frontdoor-quality-rerun32-20260610.json`
- exact canaries: pass
- 32-repeat deterministic hash stability: pass
- long-context needle recall at requested 8192 tokens: pass
- accepted-baseline comparisons: pass
- speed artifact: `data/qwen36-quark-int8-tp4-noprefix-gdn-reuseqkvzbaquant-clone-envclean-single-r8-20260610.json`

| metric | accepted | env-clean clone | delta |
| --- | ---: | ---: | ---: |
| corrected after-first output tok/s | `98.7741` | `99.3181` | `+0.5440` |
| e2e output tok/s | `97.5295` | `97.9820` | `+0.4525` |
| total tok/s | `195.0589` | `197.0858` | `+2.0269` |
| mean client TTFT | `76.28 ms` | `79.45 ms` | `+3.17 ms` |

Aggregate frontdoor p512/n256 sweep:

- artifact: `data/qwen36-quark-int8-tp4-noprefix-gdn-reuseqkvzbaquant-clone-concurrency-20260610.json`

Compared with the original no-prefix full sweep
(`data/qwen36-quark-int8-tp4-noprefix-graph32k-concurrency-20260610.json`):

| concurrency | no-prefix wall tok/s | clone wall tok/s | no-prefix from-first tok/s | clone from-first tok/s |
| --- | ---: | ---: | ---: | ---: |
| 1 | `95.94` | `96.78` | `99.02` | `99.91` |
| 2 | `170.19` | `173.21` | `181.10` | `178.45` |
| 4 | `307.85` | `317.84` | `316.24` | `326.16` |
| 8 | `553.27` | `560.76` | `566.10` | `573.63` |
| 16 | `851.63` | `888.76` | `868.43` | `907.31` |
| 32 | `1397.95` | `1400.05` | `1419.06` | `1425.47` |
| 48 | `1700.89` | `1512.24` | `1727.50` | `1531.77` |

Compared with the later accepted c48 refresh
(`data/qwen36-quark-int8-tp4-noprefix-accepted-c48-refresh-20260610.json`):

| concurrency | accepted refresh wall tok/s | clone wall tok/s | accepted refresh from-first tok/s | clone from-first tok/s |
| --- | ---: | ---: | ---: | ---: |
| 48 | `1479.66` | `1512.24` | `1495.39` | `1531.77` |

## Decision

Keep clone-guarded GDN qkvz/ba quant reuse as an opt-in candidate. It passed the
strict quality gate, passed a 64-repeat stability refresh, and gives a small
single-request decode win without reducing context length, changing
quantization, or increasing model/KV memory.

Do not promote it to the production default yet:

- the gain is small, roughly `+0.2%` to `+0.6%` corrected after-first decode
  speed across the reruns;
- TTFT is slightly worse in the single-request run;
- aggregate c48 is run-variant: better than the latest accepted c48 refresh but
  worse than the earlier full-sweep c48 result;
- the env-registration cleanup is restart-validated, but the Torch compile
  `<frozen os>` warning still needs separate root-cause work.

## Next Steps

1. Rerun accepted-control single and c48 immediately before and after the clone
   variant to reduce run-variance in the aggregate comparison.
2. Investigate the remaining Torch compile `Failed to read file <frozen os>`
   warning independently from the GDN env cleanup.
3. Investigate whether the XPU `int8_gemm_w8a8` op mutates or races on shared
   quantized activation inputs. If that can be proven and fixed at the op/schema
   level, the faster unguarded reuse may become viable.
