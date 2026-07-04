# 2026-07-04 - Webhie BF16-scale capture-size screen: no-win

## Summary

Closed the remaining graph capture-size question on the current fastest Qwen27
recipe:

- model: `webhie/Qwen3.6-27B-int4-AutoRound`;
- revision: `f5750c90b3776db658594df5fe8051098226dd8e`;
- runtime mode: AutoRound W4A16 + runtime INT8 LM-head with BF16 scales;
- baseline recipe: promote-source MTP3 with
  `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`,
  `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`,
  `VLLM_XPU_LM_HEAD_INT8=1`,
  `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`;
- gate: fixed Qwen realistic suite, chat mode, each prompt once, streamed token
  IDs, primary metric generated tokens 1-100 after TTFT, `cached_tokens=0` on
  every request.

Result: `max_cudagraph_capture_size=8` remains the best strict/fresh policy for
the current webhie/BF16-scale recipe. No LocalMaxxing submission: there is no
new recipe win.

## Same-window four-GPU run

All four variants ran in one same-window pass across GPUs `0-3`, with ports
`19410-19413`, and differed only by `max_cudagraph_capture_size`.

| Variant | GPU | Capture | Gate | cached=0 | Median tok/s | p10 | Mean | TTFT median |
| --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: |
| cg4 | 0 | 4 | pass | yes | `64.50723868600724` | `57.8929448541949` | `61.82622967510124` | `603.4633135423064 ms` |
| cg8 control | 1 | 8 | pass | yes | `65.15325429304669` | `57.52355861513786` | `64.3304713492659` | `614.0623604878783 ms` |
| cg16 | 2 | 16 | pass | yes | `63.50007036851265` | `57.573663187852375` | `63.41169526072755` | `608.7074019014835 ms` |
| cg32 | 3 | 32 | pass | yes | `64.07081789350849` | `51.447518562195434` | `61.36648516330225` | `606.1191268963739 ms` |

Artifacts:

- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-capsweep-cg4-20260704-codex-20260704T115252Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-capsweep-cg8-control-20260704-codex-20260704T115252Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-capsweep-cg16-20260704-codex-20260704T115252Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-capsweep-cg32-20260704-codex-20260704T115252Z.json`

Run directories:

- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-bf16scale-capsweep-cg4-20260704-codex-20260704T115252Z`
- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-bf16scale-capsweep-cg8-control-20260704-codex-20260704T115252Z`
- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-bf16scale-capsweep-cg16-20260704-codex-20260704T115252Z`
- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-bf16scale-capsweep-cg32-20260704-codex-20260704T115252Z`

## Repro command shape

The four arms used `scripts/run-qwen36-27b-autoround-vllm-candidate.sh`.
Example cg8 control:

```bash
cd /home/steve/llm-optimizations
MODEL_DIR=/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e \
QWEN36_27B_AR_REPO=webhie/Qwen3.6-27B-int4-AutoRound \
QWEN36_27B_AR_REVISION=f5750c90b3776db658594df5fe8051098226dd8e \
GPU_INDEX=1 PORT=19411 \
LABEL=qwen27-webhie-bf16scale-capsweep-cg8-control-20260704-codex \
NUM_SPECULATIVE_TOKENS=3 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}' \
QWEN36_27B_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1 \
VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0 \
VLLM_XPU_LM_HEAD_INT8=1 \
VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16 \
bash scripts/run-qwen36-27b-autoround-vllm-candidate.sh
```

For the other arms, change `GPU_INDEX`, `PORT`, label, and
`max_cudagraph_capture_size` to `4`, `16`, or `32`.

## Decision

Keep `max_cudagraph_capture_size=8` for the current webhie/BF16-scale
INT8-LM-head MTP3 recipe.

This closes capture-size retesting for the current recipe unless a source
change materially alters graph shapes, target/draft row counts, or acceptance.
The next useful work remains source-level:

1. a real fused/top-ID LM-head producer that helps both draft and target greedy
   LM-head calls;
2. target-matched drafter calibration that increases accepted tokens per target
   verifier step without final-suite leakage;
3. a native row-adaptive verifier only if it avoids the known rows-1 oneDNN
   launch penalty;
4. deeper DFlash/EAGLE metadata/runtime work only with a stronger draft-quality
   story.
