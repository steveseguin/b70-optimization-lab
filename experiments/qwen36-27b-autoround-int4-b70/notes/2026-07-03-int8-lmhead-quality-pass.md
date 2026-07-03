# 2026-07-03 INT8 LM-head quality-passing candidate

## Summary

`VLLM_XPU_LM_HEAD_INT8=1` is the first large Qwen3.6 27B AutoRound speedup
found after the promote-source MTP3 result. It is a runtime quantization change
for the dense BF16 `lm_head`, so it must be labeled as:

```text
Intel/Qwen3.6-27B-int4-AutoRound + runtime INT8 LM-head
```

Do not label it as the original BF16-LM-head AutoRound quantization. The patch
is default-off and the original BF16/FP16 LM-head weight remains resident.

## Patch

```text
patches/qwen36-27b-autoround-int4-b70/vllm-xpu-lm-head-int8-quality-pass-20260703.patch
```

Implementation site:

```text
/home/steve/src/vllm/vllm/model_executor/layers/vocab_parallel_embedding.py
```

The patch adds:

- `VLLM_XPU_LM_HEAD_INT8=1`;
- transient per-output-channel INT8 copy of `ParallelLMHead.weight`;
- per-token INT8 activation quantization through `_xpu_C.per_token_quant_int8_xpu`;
- existing oneDNN `_xpu_C.int8_gemm_w8a8` for the LM-head projection;
- default-off fallback to the normal BF16/FP16 path.

## Why It Was Tried

The current MTP3 path is dominated by repeated BF16 LM-head/logits work:

- draft `spec_decode.greedy_sample.compute_logits`: about `4.45 ms`;
- target `gpu_model_runner.compute_logits`: about `4.42 ms`;
- proposer forward: only about `0.65-0.83 ms`.

FP8 LM-head was faster but failed the 1K long-context quality gate. INT8 W8A8
looked higher fidelity on a synthetic full-vocab screen:

```text
BF16 projection + argmax: about 5.41 ms
INT8 projection + argmax: about 2.52 ms
random top1 agreement: 16/16
```

## Strict Fresh-Response Results

Primary run:

```text
data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-cg8-promotesource-int8lmhead-realistic128-chat-tokenids-qwensuite-20260703T133109Z.json
```

Result:

```text
passed = true
cached_tokens_all_zero = true
median_tok_s_1_100_after_ttft = 62.62792826965406
p10_tok_s_1_100_after_ttft    = 58.10368015123676
mean_tok_s_1_100_after_ttft   = 62.997843075167445
median_ttft_ms                = 606.5752394497395
```

Same-window repeat on GPU3:

```text
data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-cg8-promotesource-int8lmhead-repeat-gpu3-realistic128-chat-tokenids-qwensuite-20260703T133535Z.json
median_tok_s_1_100_after_ttft = 62.276492398420544
p10_tok_s_1_100_after_ttft    = 57.89575369361654
mean_tok_s_1_100_after_ttft   = 62.72443347316918
cached_tokens_all_zero        = true
```

Same-window BF16-LM-head control on GPU2:

```text
data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-cg8-promotesource-bf16lmhead-control-gpu2-realistic128-chat-tokenids-qwensuite-20260703T133535Z.json
median_tok_s_1_100_after_ttft = 53.33195697867582
p10_tok_s_1_100_after_ttft    = 48.24059291131892
mean_tok_s_1_100_after_ttft   = 54.43245870896934
cached_tokens_all_zero        = true
```

Interpretation: the gain is about `+16-17%`, far outside the current Qwen27
variance floor.

## Quality Gate

Short smoke passed:

```text
data/qwen36-27b-autoround-int4-b70-baselines/quality-int8lmhead-smoke-20260703T132934Z.json
```

Full quality gate passed:

```text
data/qwen36-27b-autoround-int4-b70-baselines/quality-int8lmhead-mtp3-cg8-repeat32-ctx1024-20260703T133323Z.json
pass_all=true
baseline_match_all=true
repeat_pass=true
long_context_pass=true
```

This is the same full quality gate that rejected the FP8 LM-head path.

## Validity

Valid as a fresh-response result for a distinct runtime quantization:

- fixed Qwen realistic suite;
- each prompt once;
- `cached_tokens=0` on every request;
- no prompt/KV/context/response/n-gram/history reuse;
- target-verified internal MTP;
- quality gate passed against the BF16-LM-head baseline outputs.

Not valid as a same-quantization replacement for the original
`Intel/Qwen3.6-27B-int4-AutoRound` BF16-LM-head lane. It was submitted to
LocalMaxxing as a separate runtime-quantized variant:

```text
AutoRound W4A16 + runtime INT8 LM-head
```

LocalMaxxing approved id: `cmr4zkcxb003yq9018408i1pn`.

## Next Steps

1. Consider a longer quality ladder before production use:
   `ctx1024` already passed; next useful checks are `ctx1536/ctx1792` within
   the current `max_model_len=2048`, or a separate `max_model_len=4096` quality
   baseline.
2. Run service soak/smoke on the runtime INT8 head before using it as a stable
   production recipe.
3. Search for a semantics-preserving BF16 top-1/candidate-bound design in
   parallel; INT8 LM-head is a strong practical lane, but not exact BF16 math.
