# Qwen3.6 27B AutoRound Validity Gates

## Bring-Up Smoke

A bring-up smoke only proves the model can load and generate. It requires:

- vLLM process starts on XPU without CPU fallback or silent dequantization
  warnings that invalidate the lane;
- `/v1/models` returns the served model id;
- one deterministic completion returns non-empty visible text;
- no NUL/control-character flood, repeated single-token collapse, or obvious
  loader crash on shutdown;
- exact command, model revision, runtime version, env flags, and log path are
  recorded.

Bring-up smoke is not a speed claim.

## Baseline Result

A baseline result requires:

- fixed prompt(s), each run once cold;
- `cached_tokens=0` for every measured request when the server reports cache
  details;
- no prompt/KV/context checkpoint/response reuse;
- target model and quantization unchanged:
  `Intel/Qwen3.6-27B-int4-AutoRound` at revision
  `abc86de19eb1ebbf6a7df4582341325c22ddcb7d`;
- speculation either disabled or explicitly target-verified by vLLM;
- prompt and output hashes stored in the result JSON.

Current vLLM/Qwen27 caveats:

- Unpatched vLLM omitted `prompt_tokens_details` when cached tokens were zero,
  even if prompt-token details were enabled. Diagnostic rows with
  `cached_tokens=null` are not promoted under the strict policy.
- A local reporting-only patch is preserved at
  `../../patches/qwen36-27b-autoround-int4-b70/vllm-prompt-tokens-details-zero-20260703.patch`.
  It changes the OpenAI usage checks to emit `cached_tokens=0` whenever the
  value is known. Servers must be restarted after applying it.
- Patch smoke on the restarted MTP5/cg16 server proved non-stream chat and
  completions return `usage.prompt_tokens_details.cached_tokens=0`.
- The current valid gate path is chat streaming with
  `--return-token-ids`. vLLM returns `choices[].token_ids` for each stream
  event; the harness expands those counts into token-id receipt timestamps and
  uses that for the primary generated-token window.
- Chat streaming for this Qwen setup can emit generated text in
  `delta.reasoning` rather than `delta.content`. The benchmark harness records
  both counts. This is acceptable for diagnostics, but promoted artifacts must
  clearly state the timing source.
- vLLM can group multiple generated tokens into one SSE text delta. Do not use
  chunk counts as token counts for the primary "tokens 1-100 after TTFT"
  metric unless token-per-delta is proven. Use token-id-level timing for
  promotion-style runs.
- Token-id timing is still stream-chunk granularity: multiple token IDs in the
  same SSE chunk share one client receipt timestamp. This is acceptable for the
  current Qwen baseline because it measures streamed availability more
  directly than text chunks, but report the timing source in every result.
- Text completions bypass the chat template and can expose `<think>` text even
  when the server default disables thinking for chat. Prefer chat-mode final
  gates unless the prompt is manually chat-templated and quality-checked.

## Promoted / LocalMaxxing Candidate

Use the same realistic final-gate policy as Gemma:

- fixed realistic prompt suite;
- each prompt run once as a cold first response;
- `cached_tokens=0` for every request;
- no n-gram/history acceleration, warmed repeated prompts, APC, LMCache,
  response reuse, or context checkpoints;
- primary metric: median tok/s for generated tokens 1-100 after TTFT;
- also report p10, mean, TTFT, wall-clock tok/s, full-output tok/s,
  prompt/output hashes, model identity, runtime commit, env vars, flags, and
  logs;
- MTP/speculation is allowed only when accepted tokens are verified by the
  declared target model.

No LocalMaxxing submission should happen before this gate exists and passes.

Current gate-passing best:

- config: Intel checkpoint, TP1, one B70, XPU graph on, `qwen3_next_mtp`,
  `num_speculative_tokens=3`,
  `COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}'`,
  chat mode, thinking disabled;
- env delta:
  `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1` and
  `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`;
- suite: `../../repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json`;
- artifact:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-promotesource-noacceptedpost-repeat2-realistic128-chat-tokenids-qwensuite-20260703T044519Z.json`;
- result: median `53.522 tok/s` for generated tokens 1-100 after TTFT, p10
  `48.406`, mean `53.986`, TTFT median `628.9 ms`, `cached_tokens=0` for all
  12 requests, `realistic_final_gate.passed=true`;
- support: two earlier strict repeats at `54.861` and `53.992 tok/s`, plus a
  same-window plain-MTP3/cg8 control at `48.345 tok/s`;
- quality: `quality-promotesource-noacceptedpost-mtp3-cg8-repeat32-ctx1024`
  passed exact canaries, repeat32, and 1024-token needle with
  `baseline_match_all=true`.
