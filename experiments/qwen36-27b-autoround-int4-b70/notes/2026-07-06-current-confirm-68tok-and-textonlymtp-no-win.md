# 2026-07-06 - current ReplaySSM/draft-INT4 confirm and text-only MTP no-win

## Summary

The current best valid Qwen27 one-B70 row is now the same
`webhie/Qwen3.6-27B-int4-AutoRound` ReplaySSM target-INT8/draft-INT4 recipe
reconfirmed at **68.23626314761921 tok/s** median generated-token throughput
for tokens 1-100 after TTFT.

This is a valid fresh-response row, but it is a small same-recipe improvement
over the prior approved `67.51904968102535 tok/s` packet. Treat it as the
current best measured valid result and LocalMaxxing record, not as a new
mechanism. The lane has visible run-to-run/GPU-window variance around this
scale, so sub-1% endpoint changes still need same-window or multi-GPU
confirmation before claiming a source-level win.

## Valid Current Confirm

- label: `qwen27-replayssm-draftint4-current-confirm-20260706T140317Z`
- model: `webhie/Qwen3.6-27B-int4-AutoRound`
- model revision: `f5750c90b3776db658594df5fe8051098226dd8e`
- hardware: one Intel Arc Pro B70, TP1, concurrency 1
- runtime: vLLM/XPU local patch stack, branch `codex/qwen36-quark-int8-tracking`
- source heads: vLLM `e7213ba8e13b74d7bfa3cbc05435a45df90eb76a`,
  xpu kernels `3b4effeeffd83f6ef4696bbe7e76d924a0e9d171`
- config: MTP3, XPU PIECEWISE graph, `max_cudagraph_capture_size=8`,
  `MAX_NUM_BATCHED_TOKENS=1024`, `MAX_MODEL_LEN=2048`
- key env:
  `VLLM_XPU_GDN_REPLAYSSM_SPEC=1`,
  `VLLM_XPU_GDN_REPLAYSSM_SPEC_CACHE_LEN=8`,
  `VLLM_XPU_GDN_REPLAYSSM_COMMIT_IN_FORWARD=1`,
  `VLLM_XPU_GDN_REPLAYSSM_SLOT_MGMT_TORCH_FALLBACK=1`,
  `VLLM_XPU_LM_HEAD_INT8=1`,
  `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`,
  `VLLM_XPU_DRAFT_LM_HEAD_INT4=1`,
  `VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE=128`,
  `VLLM_XPU_DRAFT_LM_HEAD_INT4_SCALE_DTYPE=bf16`
- strict gate: fixed Qwen realistic suite, 12 unique prompts, each prompt once,
  `cached_tokens=0` on every request, no prefix/KV/history/response reuse,
  streamed token-id timing, metric is median generated tokens 1-100 after TTFT
- result: median **68.23626314761921 tok/s**, p10 `62.316569643325344`, mean
  `67.82964696710413`, median TTFT `479.1464500594884 ms`
- quality: exact short canaries passed, repeat64 color/order passed,
  `baseline_match_all=true`; long context not rerun for this short-decode
  confirm

Artifacts:

- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-draftint4-current-confirm-20260706T140317Z-candidate-summary-20260706T140317Z.json`
- strict suite:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-draftint4-current-confirm-20260706T140317Z-realistic128-chat-tokenids-qwensuite-20260706T140317Z.json`
- quality:
  `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-replayssm-draftint4-current-confirm-20260706T140317Z-repeat64-ctx1024-20260706T140317Z.json`
- result packet:
  `results/qwen36-27b-autoround-int4-b70/webhie-int8lmhead-bf16scale-draftint4-replayssm-current-confirm-20260706.json`
- LocalMaxxing queue:
  `experiments/qwen36-27b-autoround-int4-b70/localmaxxing/qwen36-27b-webhie-int4-int8lmhead-bf16scale-draftint4-replayssm-current-confirm-20260706.queue.json`
- LocalMaxxing response:
  `data/localmaxxing-responses/qwen36-27b-webhie-int4-int8lmhead-bf16scale-draftint4-replayssm-current-confirm-20260706.submit.log`
- LocalMaxxing id: `cmr9atqb800msqr01u760xh0t`

## Diagnostic Same-Recipe Control

`qwen27-textonlymtp-control-20260706T140004Z` was the same current recipe with
quality intentionally skipped. It passed the strict fresh/cached-zero gate at
`68.39666292601191 tok/s` median, p10 `62.67917824828565`, mean
`68.29643488937288`, median TTFT `476.4558390015736 ms`.

Use it only as support for the current variance envelope. The quality-confirmed
68.236 row above is the promoted row.

## Text-Only MTP Shortcut Closed

The attempted `VLLM_XPU_SPEC_DECODE_TEXT_ONLY_MULTIMODAL_OK=1` / flat-position
shortcut rechecked whether this text-only workload could bypass the
multimodal-style `inputs_embeds` MTP-next path. It failed before readiness with
the same known compile-shape issue:

```text
AttributeError: 'NoneType' object has no attribute 'size'
```

The crash comes from the `inputs_embeds=None` path through Torch Dynamo sizing
in `qwen3_5_mtp.py`. Do not repeat this exact shortcut. Reopen only if the
compile/cudagraph path is redesigned so text-token IDs can be passed to
recurrent MTP-next without the `None` dynamic-shape failure.

Artifacts:

- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-textonlymtp-flatpos-20260706T140004Z-candidate-summary-20260706T140004Z.json`
- server log:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-textonlymtp-flatpos-20260706T140004Z-20260706T140004Z/server.stdout.log`

## Next Credible Work

Do not continue config roulette around this exact MTP3/cg8 recipe. The current
ReplaySSM/draft-INT4 lane is now quality-gated around `68 tok/s`, and deeper
MTP/cache-length/token-tree/DFlash/simple text-input shortcuts are closed. The
credible routes remain source-level work:

- graph-safe exact accepted-prefix GDN/DeltaNet state transaction or tape;
- materially stronger target-matched drafter that improves accepted tokens per
  verifier step on the fixed fresh suite;
- target/verifier forward kernel work that reduces the expensive target pass;
- real top-ID LM-head producer only if a standalone native path beats the
  current dense/local-argmax stack before endpoint integration.

Always rerun the strict fresh suite and quality before promotion. For small
endpoint deltas, use same-window or four-GPU repeated controls before calling
the change a win.
