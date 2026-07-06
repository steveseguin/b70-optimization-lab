# 2026-07-06 - ReplaySSM draft-INT4 valid record; native slot-copy no endpoint win

## Summary

We found a new conservative Qwen3.6 27B INT4 fresh-response record, but not for
the reason initially hypothesized.

Promoted headline:

- model: `webhie/Qwen3.6-27B-int4-AutoRound`
- target quantization: AutoRound INT4 W4A16
- target LM-head: runtime INT8 weights/activations with BF16 scales
- speculation: target-verified `qwen3_next_mtp`, `num_speculative_tokens=3`
- GDN path: ReplaySSM exact state path, commit-in-forward
- draft LM-head: runtime INT4, group size 128, BF16 scales
- headline run:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-draftint4-slotmgmt-torchfallback-solo-confirm-20260706T050135Z-candidate-summary-20260706T050135Z.json`
- primary metric: **67.51904968102535 tok/s** median generated tokens 1-100
  after TTFT
- p10: `62.6631682840432`, mean: `68.15364467092054`
- TTFT median: `477.85088047385216 ms`
- full-output after-TTFT median: `66.30253635160514 tok/s`
- wall full-output median: `61.27225175272477 tok/s`
- quality: repeat64 pass, exact canaries pass, baseline match all
- freshness: fixed Qwen realistic suite, each prompt once, `cached_tokens=0`
  on every request, no prompt/KV/context/history/response reuse
- LocalMaxxing: approved as `cmr8rg5d900glqr01g4fesy6i`

This supersedes the previous conservative `65.27648650325429 tok/s` webhie
BF16-scale INT8-LM-head row (`cmr5iu3gk00bfq901nidgcana`) for this local
Qwen27/B70 lane.

## Why this is not a native-slot-copy win

The implementation experiment fused ReplaySSM slot copy/reset into native XPU
ops:

- `_xpu_C.gdn_replayssm_copy_slots`
- `_xpu_C.gdn_replayssm_reset_slots`

Direct parity passed for BF16, FP16, and FP32:

- `data/qwen36-27b-autoround-int4-b70-baselines/gdn-replayssm-slot-copy-20260706T045143Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/gdn-replayssm-slot-copy-fp16-20260706T045157Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/gdn-replayssm-slot-copy-fp32-20260706T045157Z.json`

But endpoint attribution failed:

- native one-off high:
  `qwen27-draftint4-replayssm-slotcopy-native-20260706T045223Z`,
  `68.48075611477094 tok/s`, quality pass;
- same-window native:
  `qwen27-replayssm-slotcopy-native-confirm-gpu1-20260706T045712Z`,
  `66.87138386688892 tok/s`, quality pass;
- same-window PyTorch slot-management fallback:
  `qwen27-replayssm-slotcopy-torchfallback-control-gpu2-20260706T045712Z`,
  `67.29981507165695 tok/s`, quality pass;
- solo PyTorch slot-management fallback confirmation:
  `qwen27-replayssm-draftint4-slotmgmt-torchfallback-solo-confirm-20260706T050135Z`,
  `67.51904968102535 tok/s`, quality pass.

The PyTorch fallback control matched or beat native in the same-window pair, so
the native slot-copy op is not the demonstrated endpoint speed source. Preserve
it as a parity-passing experiment patch, not a promoted optimization.

## Reproduction

Conservative headline command shape:

```bash
cd /home/steve/llm-optimizations
LABEL=qwen27-replayssm-draftint4-slotmgmt-torchfallback-solo-confirm-$(date -u +%Y%m%dT%H%M%SZ) \
GPU_INDEX=0 PORT=19420 \
QUALITY_REPEAT_RUNS=64 QUALITY_SKIP_LONG_CONTEXT=1 \
VLLM_XPU_GDN_REPLAYSSM_SPEC=1 \
VLLM_XPU_GDN_REPLAYSSM_SPEC_CACHE_LEN=8 \
VLLM_XPU_GDN_REPLAYSSM_TORCH_FALLBACK=0 \
VLLM_XPU_GDN_REPLAYSSM_STAGE_CONV_TORCH_FALLBACK=0 \
VLLM_XPU_GDN_REPLAYSSM_COMMIT_IN_FORWARD=1 \
VLLM_XPU_GDN_REPLAYSSM_SLOT_MGMT_TORCH_FALLBACK=1 \
VLLM_XPU_LM_HEAD_INT8=1 \
VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16 \
VLLM_XPU_DRAFT_LM_HEAD_INT4=1 \
VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128 \
VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=bf16 \
QWEN36_27B_ENABLE_XPU_GRAPH=1 \
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}' \
QWEN36_27B_ENABLE_MTP=1 \
NUM_SPECULATIVE_TOKENS=3 \
experiments/qwen36-27b-autoround-int4-b70/scripts/run-vllm-candidate.sh
```

The result packet is:

- `results/qwen36-27b-autoround-int4-b70/webhie-int8lmhead-bf16scale-draftint4-replayssm-20260706.json`

Submission artifacts:

- queue:
  `experiments/qwen36-27b-autoround-int4-b70/localmaxxing/qwen36-27b-webhie-int4-int8lmhead-bf16scale-draftint4-replayssm-20260706.queue.json`
- first rejected response, quantization string too long:
  `data/localmaxxing-responses/qwen36-27b-webhie-int4-int8lmhead-bf16scale-draftint4-replayssm-20260706.submit.log`
- approved response:
  `data/localmaxxing-responses/qwen36-27b-webhie-int4-int8lmhead-bf16scale-draftint4-replayssm-20260706.submit2.log`

Patch snapshots:

- active vLLM source diff:
  `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-active-source-diff-replayssm-draftint4-record-20260706.patch`
- vLLM XPU kernels diff:
  `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-kernels-active-diff-replayssm-slotcopy-20260706.patch`

## Interpretation

What changed from the previous closed draft-INT4 story:

- Earlier fast draft-INT4 rows around `68-72 tok/s` were invalid because
  repeat64 split between the correct `blue, green, red, yellow` and truncated
  `blue, green, red`.
- ReplaySSM/align was the quality-clean family but had been measured around
  `61-64 tok/s`.
- The current active source stack plus commit-in-forward, target INT8 LM-head
  BF16 scales, and draft INT4 LM-head BF16 scales now gives a repeat64-clean
  `67.5 tok/s` conservative row.

Do not claim this breaks the `>100 tok/s` frontier. It is an incremental
policy-compliant record for Qwen27 on one B70. The next material path is still:

- increase verified accepted tokens per target step with a stronger
  target-matched drafter, branch/regenerate, or tree path that remains legal on
  fresh responses; or
- reduce target forward cost with real kernel/source work; or
- make the exact GDN/DeltaNet transaction graph-safe enough to support a better
  drafter without recurring state corruption.

## Follow-up

1. Update README/HANDOFF/CURRENT to point at the `67.519` conservative record.
2. Keep the native slot-copy op as an experiment artifact unless a later
   same-window test shows a real endpoint win.
3. Continue Qwen27 work from the stronger-drafter / target-forward reduction
   lanes, not from more slot-copy micro-optimizations.
