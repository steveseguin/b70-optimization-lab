# 2026-07-04 - Webhie BF16-scale INT8 LM-head MTP depth screen: no-win

## Summary

Retested MTP depth on the current fastest Qwen27 recipe:

- model: `webhie/Qwen3.6-27B-int4-AutoRound`;
- revision: `f5750c90b3776db658594df5fe8051098226dd8e`;
- runtime mode: AutoRound W4A16 + runtime INT8 LM-head with BF16 scales;
- baseline recipe: promote-source MTP3/cg8,
  `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`,
  `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`,
  `VLLM_XPU_LM_HEAD_INT8=1`,
  `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`;
- gate: fixed Qwen realistic suite, chat mode, each prompt once, streamed token
  IDs, primary metric generated tokens 1-100 after TTFT, `cached_tokens=0` on
  every request.

Result: MTP3/cg8 remains the best strict fresh-response depth. Deeper linear
MTP does not pay for itself on this realistic prompt suite because acceptance
falls while TTFT and verifier/draft work rise.

No LocalMaxxing submission: the best row here is a same-family MTP3 control at
`65.80873218927186 tok/s`, only `+0.82%` over the promoted
`65.27648650325429 tok/s` record and within the known variance band.

## Runs

All four runs were launched in one same-window pass across the four B70 GPUs.
Ports `19410-19413` were free before the run; the public LAN frontdoor on port
`8000` was left untouched.

| Variant | GPU | `num_speculative_tokens` | Capture | Gate | cached=0 | Median tok/s | p10 | Mean | TTFT median |
| --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: |
| control MTP3/cg8 | 0 | 3 | 8 | pass | yes | `65.80873218927186` | `57.86649566640587` | `64.6703843637056` | `608.4170279791579 ms` |
| MTP4/cg8 | 1 | 4 | 8 | pass | yes | `60.47790865880606` | `49.279845456118494` | `58.316228805047324` | `788.8670359971002 ms` |
| MTP5/cg8 | 2 | 5 | 8 | pass | yes | `59.256808975767214` | `46.77353832277956` | `55.668186002062946` | `985.8371954178438 ms` |
| MTP5/cg16 | 3 | 5 | 16 | pass | yes | `59.816562920681044` | `51.999193283818` | `57.84835856944469` | `986.620420939289 ms` |

Artifacts:

- control:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-depthscreen-control-mtp3-cg8-20260704T042420Z-20260704T042420Z.json`;
- MTP4/cg8:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-depthscreen-mtp4-cg8-20260704T042420Z-20260704T042420Z.json`;
- MTP5/cg8:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-depthscreen-mtp5-cg8-20260704T042420Z-20260704T042420Z.json`;
- MTP5/cg16:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-depthscreen-mtp5-cg16-20260704T042420Z-20260704T042420Z.json`.

Run directories:

- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-depthscreen-control-mtp3-cg8-20260704T042420Z-20260704T042420Z`;
- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-depthscreen-mtp4-cg8-20260704T042420Z-20260704T042420Z`;
- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-depthscreen-mtp5-cg8-20260704T042420Z-20260704T042420Z`;
- `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-depthscreen-mtp5-cg16-20260704T042420Z-20260704T042420Z`.

## Repro command shape

The four runs used `scripts/run-qwen36-27b-autoround-vllm-candidate.sh` with
the same model/runtime env and only the GPU/port/depth/capture fields changed.
Example MTP3 control:

```bash
cd /home/steve/llm-optimizations
MODEL_DIR=/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e \
QWEN36_27B_AR_REPO=webhie/Qwen3.6-27B-int4-AutoRound \
QWEN36_27B_AR_REVISION=f5750c90b3776db658594df5fe8051098226dd8e \
GPU_INDEX=0 PORT=19410 \
LABEL=qwen27-webhie-int8lmhead-bf16scale-depthscreen-control-mtp3-cg8-$(date -u +%Y%m%dT%H%M%SZ) \
NUM_SPECULATIVE_TOKENS=3 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}' \
QWEN36_27B_ENABLE_XPU_GRAPH=1 \
VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1 \
VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0 \
VLLM_XPU_LM_HEAD_INT8=1 \
VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16 \
bash scripts/run-qwen36-27b-autoround-vllm-candidate.sh
```

For MTP4/cg8, set `NUM_SPECULATIVE_TOKENS=4`.
For MTP5/cg8, set `NUM_SPECULATIVE_TOKENS=5`.
For MTP5/cg16, set `NUM_SPECULATIVE_TOKENS=5` and
`max_cudagraph_capture_size=16`.

## Interpretation

The current webhie/BF16-scale recipe has the same qualitative depth behavior
as the earlier Intel-checkpoint recipe: linear MTP depth beyond 3 lowers strict
fresh-response throughput. The acceptance trace already showed MTP3 emits about
`2.70` tokens/verifier step with only `0.38` full-accept rate. Adding deeper
linear draft positions increases LM-head/proposer/verifier work while later
positions are accepted less often.

Closed as no-win:

- do not promote or submit the `65.8087` control row; it is support/variance,
  not a distinct recipe or a statistically separated record;
- do not retest MTP4/MTP5 as config-only changes for this record family;
- do not use synthetic MTP5/cg16 wins as fresh-response claims;
- keep MTP3/cg8 as the active strict recipe unless a source change improves
  acceptance/cost enough to justify retesting depth.

Next credible work remains source-level:

1. reduce real LM-head calls/rows per verifier step;
2. improve accepted tokens per target verifier step without deeper linear MTP
   cost;
3. find a oneDNN/XPU-integrated exact top-1/top-k epilogue or equivalent
   primitive that beats dense logits plus argmax.
