# 2026-07-05 - Draft INT4 + ReplaySSM stage-fix is valid but still no-win

## Summary

The separate draft-only INT4 LM-head path previously showed a real speed signal
(`~70-73 tok/s`) but failed repeat/order quality. After the ReplaySSM
S=4/cache=8 native dispatch and stage-conv window fix, the same draft-INT4 idea
passes the short quality screen and the strict fresh realistic-suite gate.

Classification: useful correctness milestone, **not a record**, **do not submit
to LocalMaxxing**. ReplaySSM fixes the unsafe state-equivalence failure, but its
transaction overhead erases the draft-INT4 speed advantage and lands below the
current valid `65.27648650325429 tok/s` record.

## Build / Patch Context

Required patch artifacts:

- `patches/qwen36-27b-autoround-int4-b70/vllm-draft-lmhead-int4-separate-draft-head-current-20260705.patch`
- `patches/qwen36-27b-autoround-int4-b70/vllm-replayssm-s4-cache8-python-dispatch-and-metadata-20260705.patch`
- `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-kernels-replayssm-s4-cache8-stageconv-window-fix-20260705.patch`

Installed XPU extension after the stage-conv fix:

- `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so`
- sha256 `9dde12dbcfe30cf6439590f9e32da93d22e83c9d8bbfb7a07c2b84c88c6058f3`

Core env:

```bash
QWEN36_27B_ENABLE_XPU_GRAPH=1
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}'
QWEN36_27B_ENABLE_MTP=1
NUM_SPECULATIVE_TOKENS=3
VLLM_XPU_GDN_REPLAYSSM_SPEC=1
VLLM_XPU_GDN_REPLAYSSM_SPEC_CACHE_LEN=8
VLLM_XPU_GDN_REPLAYSSM_TORCH_FALLBACK=0
VLLM_XPU_GDN_REPLAYSSM_STAGE_CONV_TORCH_FALLBACK=0
VLLM_XPU_LM_HEAD_INT8=1
VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16
VLLM_XPU_DRAFT_LM_HEAD_INT4=1
VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128
VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=bf16
```

Two GDN accepted-state modes were tested:

- post mode: `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=0`,
  `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=1`
- promote mode: `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`,
  `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`

## Results

All strict rows used:

- model: `webhie/Qwen3.6-27B-int4-AutoRound`
- one B70 GPU, TP1, MTP3
- fixed Qwen realistic suite, unique prompts, each prompt once
- `cached_tokens=0` for every request
- token-id timing, metric is median generated-token throughput for tokens
  1-100 after TTFT

| Label | Quality | Median tok/s | P10 | Mean | TTFT median | Gate |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `qwen27-draftint4-replayssm-stagefix-post-graph` | short pass | `61.74909074272557` | `57.43194249862535` | `62.81846097320092` | `501.966 ms` | pass, cached-zero |
| `qwen27-draftint4-replayssm-stagefix-promote-graph` | short pass | `62.28563129070112` | `57.13684740909999` | `62.75502548772885` | `507.634 ms` | pass, cached-zero |

Artifacts:

- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-replayssm-stagefix-post-nograph-quality-20260705T141908Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-replayssm-stagefix-post-graph-quality-20260705T142057Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-replayssm-stagefix-post-graph-realistic128-chat-tokenids-qwensuite-20260705T142120Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-replayssm-stagefix-promote-graph-quality-20260705T142438Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-replayssm-stagefix-promote-graph-realistic128-chat-tokenids-qwensuite-20260705T142500Z.json`
- trace dirs:
  `data/qwen36-27b-autoround-int4-b70-baselines/trace-qwen27-draftint4-replayssm-stagefix-post-graph-20260705T141934Z`
  and
  `data/qwen36-27b-autoround-int4-b70-baselines/trace-qwen27-draftint4-replayssm-stagefix-promote-graph-20260705T142314Z`

The graph-off post-mode quality run also logged strong diagnostic acceptance:
acceptance length around `3.65` and draft acceptance around `88.2%`. That is
not a headline throughput claim; the graph-off server was only a correctness
and acceptance diagnostic.

## Interpretation

This closes a useful question: the draft-INT4 invalidity was not ordinary
quality loss from INT4 logits. Target verification plus ReplaySSM can make the
path valid, which supports the hypothesis that the earlier failure was GDN
state-equivalence under changed accept/reject patterns.

However, ReplaySSM S=4/cache=8 is too expensive in the endpoint path:

- exact-draft ReplaySSM stage-fix: `57.8-58.4 tok/s`
- draft-INT4 ReplaySSM stage-fix: `61.7-62.3 tok/s`
- current promoted record without ReplaySSM: `65.27648650325429 tok/s`
- earlier invalid draft-INT4 normal-MTP screen: `~70-73 tok/s`

So ReplaySSM recovers correctness but gives back more speed than the draft INT4
head saves. Do not keep sweeping ReplaySSM flags for this objective unless a
profile shows a concrete overhead reduction.

## Next Direction

The next credible speed route is to make the normal fast MTP path correct for
the draft-INT4 proposal pattern, rather than using full ReplaySSM transactions
on every step.

Suggested next implementation:

1. Run the failing normal-MTP draft-INT4 repeat/order case with verify/GDN
   traces enabled.
2. Run the passing ReplaySSM draft-INT4 repeat/order case with the same prompt,
   seed, and traces.
3. Diff draft ids, target ids, accepted counts, partial/full accept events, and
   GDN state promotion/rollback stages.
4. Identify the first state transition that normal MTP handles differently.
5. Patch only that unsafe normal-MTP GDN state transition if possible, then
   rerun repeat/order before any strict-suite benchmark.

If that patch works, the target is to reclaim the earlier `70-73 tok/s` speed
signal as a valid result, then continue toward `100+ tok/s` by attacking
verifier LM-head cost or acceptance tokens per step.
