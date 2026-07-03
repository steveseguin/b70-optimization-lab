# 2026-07-03 - webhie AutoRound variant quality-passing record

## Summary

`webhie/Qwen3.6-27B-int4-AutoRound` is a quality-passing speed improvement over
the prior `Intel/Qwen3.6-27B-int4-AutoRound` checkpoint under the same one-B70
vLLM/XPU recipe:

- `qwen3_next_mtp`, `num_speculative_tokens=3`;
- XPU graph on, `max_cudagraph_capture_size=8`;
- `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`;
- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`;
- `VLLM_XPU_LM_HEAD_INT8=1`.

This is a model-variant result. Keep it labeled as:

```text
webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8 LM-head
```

Do not merge it into the Intel-checkpoint row.

## Speed Evidence

Primary strict fresh-response repeat:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-autoround-int8lmhead-repeat-gpu2-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T171159Z.json
```

Result:

```text
passed = true
cached_tokens_all_zero = true
median_tok_s_1_100_after_ttft = 64.30618876596424
p10_tok_s_1_100_after_ttft    = 59.49563660285311
mean_tok_s_1_100_after_ttft   = 63.61518423375664
median_ttft_ms                = 605.9380329679698
```

Support rows:

- initial webhie strict row:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-autoround-int8lmhead-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T170250Z.json`
  at `63.33596589025419` tok/s;
- same-window Intel INT8-LM-head control:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-intel-int8lmhead-control-gpu3-samewindow-webhie-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T171159Z.json`
  at `62.36616020083166` tok/s;
- prior Intel record:
  `62.62792826965406` tok/s, LocalMaxxing `cmr4zkcxb003yq9018408i1pn`.

Interpretation: primary webhie repeat is `+2.09%` over the prior Intel record
and `+3.11%` over the same-window Intel control. The two webhie rows averaged
`63.82` tok/s.

## Quality Evidence

Full quality gate:

```text
data/qwen36-27b-autoround-int4-b70-baselines/quality-webhie-int8lmhead-mtp3-cg8-repeat32-ctx1024-20260703T170941Z.json
```

Result:

```text
pass_all = true
baseline_match_all = true
repeat_pass = true
long_context_pass = true
```

The baseline comparator was the prior accepted Intel INT8-LM-head quality JSON:

```text
data/qwen36-27b-autoround-int4-b70-baselines/quality-int8lmhead-mtp3-cg8-repeat32-ctx1024-20260703T133323Z.json
```

The first quality attempt used system `python3` and failed before writing the
final JSON because `transformers` was unavailable. The successful rerun used
`/home/steve/.venvs/vllm-xpu/bin/python`.

## Promotion Artifacts

- result packet:
  `results/qwen36-27b-autoround-int4-b70/webhie-int8-lmhead-20260703.json`;
- LocalMaxxing queue:
  `experiments/qwen36-27b-autoround-int4-b70/localmaxxing/qwen36-27b-webhie-int4-int8lmhead-20260703.queue.json`;
- LocalMaxxing payload:
  `experiments/qwen36-27b-autoround-int4-b70/localmaxxing/qwen36-27b-webhie-int4-int8lmhead-20260703.payload.json`.
- LocalMaxxing approved id:
  `cmr576apv0079q901i6dvsh0l`;
- submission response:
  `data/localmaxxing-responses/qwen36-27b-webhie-int4-int8lmhead-20260703.submit.log`.

## Next Follow-Ups

1. Screen `webhie/Qwen3.6-27B-int4-AutoRound-Code` if disk/network budget is
   acceptable. It is code-calibrated and may trade general quality for coding
   behavior; run the same strict and quality gates before promotion.
2. Continue source-level verifier work only with a real tiled/candidate-bound
   design. The naive scalar fused top-1 microbench was about 1000x slower than
   the current oneDNN path and is closed.
