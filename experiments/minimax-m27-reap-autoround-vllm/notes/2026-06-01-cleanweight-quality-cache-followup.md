# 2026-06-01 Clean-Weight Quality and Cache Follow-up

Goal: continue REAP MiniMax M2.7 optimization after the sync quality harness
started failing with:

```text
AttributeError: 'MiniMaxText01RMSNormTP' object has no attribute '_minimax_clean_weight_xpu'
```

## What failed

The failure is a cache/source-state problem, not a model-size problem. The
compiled graph can expect MiniMax q/k RMSNorm clean-weight tensors to exist as
module attributes during engine startup. The live source only guaranteed the
clean copy on the `Parameter`; the module-level copy was populated lazily after a
forward. A sync `LLM(...)` quality run can therefore fail before the first prompt.

## Experimental source patch

I tried `patches/vllm-minimax-clean-weight-owner-experiment.patch`, which stores
an owner pointer on the RMSNorm weight parameter and mirrors the clean CPU/XPU
copies onto the owning `MiniMaxText01RMSNormTP` module during weight load.

Validation:

- Syntax check passed with `python3 -m py_compile`.
- Fresh-cache graph quality run compiled and generated, proving the startup
  missing-attribute failure was fixed.
- First fresh run failed the strict quality gate due to one token id `0` in prompt
  2:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/quality-smoke-20260601T035337Z.json`.
- Immediate repeat from the same cache passed strict quality:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/quality/quality-smoke-20260601T035827Z.json`,
  `combined_token_sha256=f97fdf040fb42b7597cab517888d9bf0309aba0a29d0c92249287c10c91df14e`,
  no NUL/control output, `1536` generated tokens.

Performance impact:

- Patched fresh/default cache:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T040006Z.log`
  - `80.47 output tok/s`
  - `107.29 total tok/s`
- Patched fresh `VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP=0`:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T040648Z.log`
  - `54.17 output tok/s`
  - `72.22 total tok/s`
- Patched fresh `VLLM_MINIMAX_POST_ATTN_NORM_MOE_CUSTOM_OP=1`:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T041236Z.log`
  - `49.19 output tok/s`
  - `65.59 total tok/s`

Decision: do not promote this patch. It fixed the sync startup issue, but the
source hash changed and forced new AOT builds that are much slower than the
preserved fast cache. I reverted the live vLLM source after capturing the patch
for future reference.

## Preserved Fast Cache Check

After reverting the experimental source patch, the preserved fast async cache
still direct-loads:

- cache root:
  `/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-sweep-moe-full-forward0-20260531T193000Z`
- explicit compile cache:
  `/mnt/fast-ai/vllm-cache-exp/minimax-m27-reap-sweep-moe-full-forward0-20260531T193000Z/torch_compile_cache/f728d2c0cf`
- log:
  `/mnt/fast-ai/bench-results/minimax-m27-reap-autoround-vllm/decode/vllm-minimax-m27-autoround-tp4-p512n1536-20260601T041712Z.log`
- result:
  - `88.40 output tok/s`
  - `117.87 total tok/s`
  - direct-loaded `f728d2c0cf` backbone and `baed0971531a4824474916a783ca5bfc09780742bb50b650626b0864e2fa9c2f` AOT

This is the best current reproducible async path after the promoted root's AOT
was overwritten, but it remains a recovery/debug path rather than a promoted
serve recipe because the sync quality harness cannot currently validate the
preserved stale AOT without changing source hash.

## Current State

- Production services remain inactive:
  - `minimax-vllm.service`: inactive
  - `minimax-openai-frontdoor.service`: inactive
- Live vLLM source was restored to the pre-experiment state.
- No new LocalMaxxing submission is justified. The approved `89.499` tok/s result
  remains archived; the best current direct reproduction is `88.40` tok/s on the
  preserved fast cache.

## Next Work

- Build a proper quality harness path for async/vLLM-server generation so the
  exact fast async cache can be validated without sync `LLM(...)` startup
  assumptions.
- Avoid source edits in the hot vLLM graph path unless the expected win justifies
  losing AOT compatibility.
- If source edits are needed, isolate them in a new cache namespace and require:
  quality pass, warmed repeat, and comparison against the preserved `f728d2c0cf`
  path before promotion.
