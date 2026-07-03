# 2026-07-03 INT8 LM-head Scope Attribution

Goal: identify whether the runtime INT8 LM-head speedup comes from the target
verifier LM-head, the MTP drafter LM-head, or both. This also tests whether a
lower-memory service recipe can prepare only the target INT8 head.

Patch:

`patches/qwen36-27b-autoround-int4-b70/vllm-xpu-lm-head-int8-scope-target-quality-pass-20260703.patch`

Patch details:

- keeps default behavior unchanged (`VLLM_XPU_LM_HEAD_INT8_SCOPE=all`);
- stores each `ParallelLMHead` construction prefix as `_vllm_prefix`;
- supports `VLLM_XPU_LM_HEAD_INT8_SCOPE=target` and `draft`/`mtp`;
- for this Qwen3Next speculative stack, target prefix is
  `language_model.lm_head`, while the MTP drafter remaps shared weights into a
  bare `lm_head`.

The first detector attempt looked for an explicit `mtp` prefix segment. That
was wrong for Qwen3Next: `target` prepared both heads and `draft` prepared no
heads. Those runs are preserved as controls but not used for attribution.

## Valid fixed-scope attribution

Common identity:

- `Intel/Qwen3.6-27B-int4-AutoRound` revision
  `abc86de19eb1ebbf6a7df4582341325c22ddcb7d`;
- one B70, TP1, vLLM/XPU, chat mode, thinking disabled;
- `qwen3_next_mtp`, `NUM_SPECULATIVE_TOKENS=3`;
- `COMPILATION_CONFIG={"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}`;
- `MAX_MODEL_LEN=2048`, `MAX_NUM_BATCHED_TOKENS=1024`;
- `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`;
- `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`;
- fixed Qwen realistic suite, each prompt once, `cached_tokens=0`, token-id
  timing.

| scope | prepared heads | artifact | gate | median tok/s | p10 | mean | TTFT ms |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| all | `language_model.lm_head` + `lm_head` | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int8lmhead-scopefix-all-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T140331Z.json` | pass, cached=0 | `62.101032` | `57.795600` | `62.547445` | `604.861` |
| target | `language_model.lm_head` only | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int8lmhead-scopefix-target-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T140331Z.json` | pass, cached=0 | `61.897979` | `57.494070` | `62.431561` | `520.861` |
| draft | bare `lm_head` only | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int8lmhead-scopefix-draft-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T140331Z.json` | pass, cached=0 | `52.858609` | `47.777736` | `54.077578` | `620.127` |
| BF16 control | none | `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-bf16lmhead-scopefix-control-mtp3-cg8-realistic128-chat-tokenids-qwensuite-20260703T140331Z.json` | pass, cached=0 | `52.707415` | `47.737280` | `53.881245` | `527.666` |

Interpretation:

- the speedup comes almost entirely from the **target verifier LM-head**;
- draft-only INT8 is essentially the BF16 control, so MTP draft-token selection
  is not the practical bottleneck under the current path;
- all-head INT8 is still the submitted max-throughput record family, but
  target-only INT8 is a better service candidate if it preserves quality,
  because it avoids preparing the extra MTP INT8 LM-head copy.

## Target-only quality gate

Target-only quality artifact:

`data/qwen36-27b-autoround-int4-b70-baselines/quality-int8lmhead-targetonly-mtp3-cg8-repeat32-ctx1024-20260703T140623Z.json`

Result:

- `pass_all=true`;
- `baseline_match_all=true`;
- 32-repeat stability passed;
- 1024-token long-context needle passed;
- long-context `cached_tokens=0`.

Decision:

- Keep the LocalMaxxing headline as the already approved all-head INT8 row:
  `62.628 tok/s`, id `cmr4zkcxb003yq9018408i1pn`.
- For service/production experiments, prefer
  `VLLM_XPU_LM_HEAD_INT8_SCOPE=target` first: it is quality-clean and nearly
  throughput-equivalent while using less VRAM than preparing both target and MTP
  INT8 heads.
- Do not promote draft-only INT8.
- The next decode-rate work remains true target LM-head top-1 /
  candidate-bound reduction; configuration sweeps did not expose a reliable
  record beyond the current all-head INT8 row.
