# 2026-07-04 - Webhie BF16-scale MTP1/MTP2 depth coverage: no-win

## Summary

Closed the missing shallow-depth coverage for the current fastest Qwen27 recipe.
The earlier current-recipe depth screen tested MTP3/4/5 and found MTP3 best,
but it did not retest MTP1/MTP2 on the webhie/BF16-scale INT8-LM-head recipe.
This mattered because vLLM's Qwen3-Next examples commonly show MTP2, and public
warnings note that `num_speculative_tokens > 1` reuses the same MTP layer and
can lower acceptance.

Result: MTP3/cg8 remains best. MTP2 is strict-valid but slower; MTP1 is much
slower. No LocalMaxxing submission.

## Identity

- model: `webhie/Qwen3.6-27B-int4-AutoRound`;
- revision: `f5750c90b3776db658594df5fe8051098226dd8e`;
- runtime mode: AutoRound W4A16 + runtime INT8 LM-head with BF16 scales;
- recipe baseline: promote-source MTP3/cg8,
  `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`,
  `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`,
  `VLLM_XPU_LM_HEAD_INT8=1`,
  `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`;
- gate: fixed Qwen realistic suite, chat mode, each prompt once, streamed token
  IDs, primary metric generated tokens 1-100 after TTFT, `cached_tokens=0` on
  every request.

## Same-window four-GPU run

| Variant | GPU | `num_speculative_tokens` | Capture | Gate | cached=0 | Median tok/s | p10 | Mean | TTFT median |
| --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: |
| MTP1/cg8 | 0 | 1 | 8 | pass | yes | `51.24613704631071` | `46.9882748332936` | `48.70815152719461` | `298.7594275036827 ms` |
| MTP2/cg8 | 1 | 2 | 8 | pass | yes | `59.589096936159876` | `52.52660105751295` | `56.54483043795461` | `437.3506020056084 ms` |
| MTP3/cg8 control | 2 | 3 | 8 | pass | yes | `64.72972570060101` | `57.92812326501689` | `64.26985284367179` | `610.369234578684 ms` |
| MTP4/cg8 repeat | 3 | 4 | 8 | pass | yes | `59.88620742185209` | `49.2554251975043` | `58.51717712632195` | `779.4782184064388 ms` |

Artifacts:

- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-depthscreen-mtp1-cg8-20260704-codex-20260704T121026Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-depthscreen-mtp2-cg8-20260704-codex-20260704T121026Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-depthscreen-mtp3-cg8-control2-20260704-codex-20260704T121026Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-depthscreen-mtp4-cg8-repeat-20260704-codex-20260704T121026Z.json`

## Decision

Keep MTP3/cg8 as the current strict recipe. This closes MTP1/MTP2 retesting for
the current webhie/BF16-scale INT8-LM-head lane.

Interpretation:

- MTP1 has low TTFT because it captures fewer shapes and drafts less, but it
  emits too few tokens per verifier step to compete.
- MTP2 is the common conservative Qwen3-Next setting, but on this B70 recipe it
  still loses by about `5.14 tok/s` median to MTP3 control.
- MTP4 repeats the previous deeper-depth no-win.

Do not revisit MTP depth as a config-only sweep unless a source change improves
draft cost, target verifier row cost, or acceptance.

References checked during this pass:

- vLLM Qwen3-Next MTP recipe: `https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3-Next.html`
- vLLM issue showing the MTP-layer reuse warning:
  `https://github.com/vllm-project/vllm/issues/36643`
