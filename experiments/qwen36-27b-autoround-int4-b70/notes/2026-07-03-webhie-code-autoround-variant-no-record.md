# 2026-07-03 - webhie Code AutoRound variant no-record support row

## Summary

`webhie/Qwen3.6-27B-int4-AutoRound-Code` loaded through the same vLLM/XPU
AutoRound path and passed the strict fresh-response gate with the current
runtime INT8-LM-head recipe, but it did **not** beat the current webhie base
record.

## Config

- checkpoint: `webhie/Qwen3.6-27B-int4-AutoRound-Code`;
- revision: `2264cf0911559d59b08fe8d59d815565124c647d`;
- one B70, TP1, vLLM/XPU chat endpoint;
- `qwen3_next_mtp`, `NUM_SPECULATIVE_TOKENS=3`;
- `COMPILATION_CONFIG={"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}`;
- `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`;
- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`;
- `VLLM_XPU_LM_HEAD_INT8=1`.

## Result

Artifact:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-code-autoround-int8lmhead-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T174809Z.json
```

Strict fresh gate:

```text
passed = true
cached_tokens_all_zero = true
median_tok_s_1_100_after_ttft = 64.29182077914321
p10_tok_s_1_100_after_ttft    = 59.550524275275876
mean_tok_s_1_100_after_ttft   = 62.89244378903519
median_ttft_ms                = 605.988490046002
```

Decision: useful support row, but **not a new record**. The current best remains
`webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8 LM-head` at
`64.30618876596424` tok/s, LocalMaxxing `cmr576apv0079q901i6dvsh0l`.

Because this did not beat the current record and is code-calibrated, the next
better spend is screening another AutoRound calibration variant rather than
running the full quality gate here immediately.
