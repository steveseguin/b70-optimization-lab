# 2026-07-03 - acyildirimer AutoRound variant variance-class no-record

## Summary

`acyildirimer/Qwen3.6-27B-int4-AutoRound` loaded through the same vLLM/XPU
AutoRound path and passed the strict fresh-response gate, but the apparent
single-run high was too small to promote. Same-window confirmation landed in
the same variance band as the current webhie record and had worse p10.

## Config

- checkpoint: `acyildirimer/Qwen3.6-27B-int4-AutoRound`;
- revision: `c71c579b605c5bd10d50e94360fec1fb7078b577`;
- one B70, TP1, vLLM/XPU chat endpoint;
- `qwen3_next_mtp`, `NUM_SPECULATIVE_TOKENS=3`;
- `COMPILATION_CONFIG={"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}`;
- `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`;
- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`;
- `VLLM_XPU_LM_HEAD_INT8=1`.

## Results

Initial strict row:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-acyildirimer-autoround-int8lmhead-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T182009Z.json
median = 64.44270385128195
p10    = 58.26052278539215
mean   = 63.59877666836558
gate   = pass, cached_tokens=0
```

Same-window confirmation:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-acyildirimer-autoround-int8lmhead-repeat-gpu2-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T182348Z.json
median = 64.24536110123208
p10    = 58.19083850279297
mean   = 63.694854170452494
gate   = pass, cached_tokens=0
```

Same-window webhie base control:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-autoround-int8lmhead-control-gpu3-samewindow-acyildirimer-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T182348Z.json
median = 64.09114577395833
p10    = 59.41866000607334
mean   = 63.51536068667696
gate   = pass, cached_tokens=0
```

## Decision

No promotion and no LocalMaxxing submission. The current record remains:

```text
webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8 LM-head
median = 64.30618876596424
LocalMaxxing = cmr576apv0079q901i6dvsh0l
```

The acyildirimer mean is slightly above the webhie same-window control, but the
median delta is below the observed variance floor and p10 is worse. Do not run
the full quality gate unless a later reason appears; use this as a support row
showing AutoRound calibration variants are clustered around the current ceiling.
