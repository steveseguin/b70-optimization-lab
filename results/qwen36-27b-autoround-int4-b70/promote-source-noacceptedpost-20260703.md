# Promote-Source Accepted-State Result

Date: 2026-07-03

Model: `Intel/Qwen3.6-27B-int4-AutoRound`, revision
`abc86de19eb1ebbf6a7df4582341325c22ddcb7d`.

Hardware/runtime: one Intel Arc Pro B70 32 GB, local vLLM/XPU from
`/home/steve/src/vllm`, branch `codex/qwen36-quark-int8-tracking`, head
`e7213ba8e13b74d7bfa3cbc05435a45df90eb76a` plus the dirty patch snapshot
`../../patches/qwen36-27b-autoround-int4-b70/vllm-current-xpu-qwen27-promote-source-stack-20260703.patch`.

## Result

Current conservative strict/fresh headline:

- median `53.5219513537644 tok/s` for generated tokens 1-100 after TTFT;
- p10 `48.405989992323235`, mean `53.986013488006655`;
- median TTFT `628.9249174878933 ms`;
- fixed Qwen realistic suite, 12 unique prompts, each prompt once;
- `cached_tokens=0` on every request;
- token timing source: streamed OpenAI `token_ids` chunk timestamps;
- quality suite passed and matched baseline.

Support rows:

| row | median tok/s | p10 | mean | TTFT median ms | artifact |
| --- | ---: | ---: | ---: | ---: | --- |
| first | 54.861 | 48.225 | 53.556 | 623.7 | `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-promotesource-noacceptedpost-realistic128-chat-tokenids-qwensuite-20260703T044123Z.json` |
| repeat1 | 53.992 | 47.065 | 53.932 | 630.4 | `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-promotesource-noacceptedpost-repeat-realistic128-chat-tokenids-qwensuite-20260703T044221Z.json` |
| repeat2 | 53.522 | 48.406 | 53.986 | 628.9 | `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-promotesource-noacceptedpost-repeat2-realistic128-chat-tokenids-qwensuite-20260703T044519Z.json` |

Same-window plain-MTP3/cg8 control:

- median `48.34505323118557 tok/s`;
- conservative promote-source delta: `+10.708%`.

Control artifact:

```text
../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-samewindow-control-realistic128-chat-tokenids-qwensuite-20260703T044221Z.json
```

Quality artifact:

```text
../../data/qwen36-27b-autoround-int4-b70-baselines/quality-promotesource-noacceptedpost-mtp3-cg8-repeat32-ctx1024-20260703T043946Z.json
```

The quality suite reports `pass_all=true` and `baseline_match_all=true`.

LocalMaxxing:

- status: `APPROVED`
- ID: `cmr4gokx90061nv01lhoe3ft8`
- label:
  `qwen36-27b-int4-autoround-b70-vllm-realistic-promotesource-mtp3-cg8-53tok-20260703`
- queue:
  `../../experiments/qwen36-27b-autoround-int4-b70/localmaxxing/qwen36-27b-int4-promotesource-20260703.queue.json`
- response:
  `../../data/localmaxxing-responses/qwen36-27b-int4-promotesource-20260703.submit2.log`

## Config

Base config:

```text
TP1
MAX_MODEL_LEN=2048
MAX_NUM_BATCHED_TOKENS=1024
QWEN36_27B_ENABLE_MTP=1
NUM_SPECULATIVE_TOKENS=3
QWEN36_27B_ENABLE_XPU_GRAPH=1
COMPILATION_CONFIG={"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}
chat_template_kwargs={"enable_thinking":false}
```

Winning env delta:

```text
VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1
VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0
```

Interpretation: this is not the invalid blind skip path. The promote-source
flag causes forward metadata to read the accepted speculative slot as the
running source; disabling the accepted-state postprocess copy then avoids the
physical copy while preserving the recurrent-state transition.

## Diagnostic Only

Synthetic p512/o512 `vllm-random` repeat3 reached corrected after-first median
`75.81675599528684 tok/s`, decode mean `13.108653826823987 ms/token`,
iteration tokens/step median `7.816793893129771`, and acceptance median
`97.692%`.

Artifact:

```text
../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-promotesource-noacceptedpost-specmetrics-p512o512-r3-20260703T044037Z.json
```

This synthetic score is diagnostic only and must not be submitted as the
headline.

## Next Work

Make the two-flag promote-source mechanism explicit and upstreamable, then
measure remaining GDN/Mamba metadata/copy overhead and verifier cost. Do not
repeat simple full-accept copy skipping or memcpy block-size tuning.
