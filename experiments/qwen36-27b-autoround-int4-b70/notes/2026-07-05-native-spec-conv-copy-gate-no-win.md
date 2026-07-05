# Native GDN Spec Conv Pre-Copy Gate: No Win

Date: 2026-07-05

## Question

The previous Python-only SSM promotion switch
`VLLM_XPU_GDN_NATIVE_PROMOTE_CONV_STATE=0` was incomplete because the packed
C++ native spec-decode path still copied accepted conv rows into the running
row through `copy_conv_rows_to_indices` inside `gdn_attention_spec_decode`.

This test added a default-on native gate,
`VLLM_XPU_GDN_NATIVE_SPEC_COPY_CONV_STATE`, then ran the draft-INT4 candidate
with both conv promotion paths disabled:

```bash
VLLM_XPU_DRAFT_LM_HEAD_INT4=1
VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128
VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=bf16
VLLM_XPU_GDN_NATIVE_PROMOTE_CONV_STATE=0
VLLM_XPU_GDN_NATIVE_SPEC_COPY_CONV_STATE=0
QUALITY_REPEAT_RUNS=64
QUALITY_SKIP_LONG_CONTEXT=1
```

## Patch

Preserved patch:

`patches/qwen36-27b-autoround-int4-b70/vllm-xpu-kernels-gdn-native-spec-conv-copy-gate-no-win-20260705.patch`

The live XPU-kernels source and local `_xpu_C.abi3.so` runtime binary were
restored after the run. Do not carry this gate in the active runtime.

## Result

Label:

`qwen27-draftint4-native-both-convskip-20260705T203127Z`

Artifacts:

- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-native-both-convskip-20260705T203127Z-candidate-summary-20260705T203127Z.json`
- strict bench:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-native-both-convskip-20260705T203127Z-realistic128-chat-tokenids-qwensuite-20260705T203127Z.json`
- quality:
  `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-draftint4-native-both-convskip-20260705T203127Z-repeat32-ctx1024-20260705T203127Z.json`
  (filename says `repeat32` because the wrapper default path is static; the
  run used `QUALITY_REPEAT_RUNS=64`)
- server log:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-draftint4-native-both-convskip-20260705T203127Z-20260705T203127Z/server.stdout.log`

Outcome:

- smoke passed;
- `cached_tokens=0` for all 12 strict prompts;
- strict fresh gate **failed**: one prompt produced only `73` streamed token-id
  events, so the metric window had only `11` usable rows;
- diagnostic median from usable rows: `64.027 tok/s` (not valid/headline);
- quality failed:
  - exact JSON case malformed: `{"answer": 42": 2, "unit: "widgets"}`;
  - repeat64 color/order failed hard: `62/64` runs normalized to
    `blue, green red yellow`, `1/64` was correct, and `1/64` ran away into
    repeated `blue/green/red` tokens.

## Interpretation

Disabling both native conv promotion paths is worse than the earlier
draft-INT4 failures. The conv copy is not merely redundant state churn; the
packed native spec-decode path needs some conv-state transition that this
experiment removed.

This closes the "SSM-only by skipping both native conv copies" hypothesis.
Future GDN state work should not rerun this exact gate combination. A useful
next attempt would need a state trace or an exact GDN tape/replay design that
distinguishes which conv window columns must be preserved, shifted, or restored
per accepted-prefix step, rather than blindly disabling the conv copy.

