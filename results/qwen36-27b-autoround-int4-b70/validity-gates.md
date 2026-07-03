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

- This vLLM build may omit `prompt_tokens_details` when cached tokens are zero,
  even if prompt-token details are enabled. Diagnostic rows with
  `cached_tokens=null` are not promoted under the strict policy. Before
  LocalMaxxing submission, either patch/enable explicit zero reporting or
  capture an auditable no-cache exception approved for this lane.
- Chat streaming for this Qwen setup can emit generated text in
  `delta.reasoning` rather than `delta.content`. The benchmark harness records
  both counts. This is acceptable for diagnostics, but promoted artifacts must
  clearly state the timing source.
- vLLM can group multiple generated tokens into one SSE text delta. Do not use
  chunk counts as token counts for the primary "tokens 1-100 after TTFT"
  metric unless token-per-delta is proven. Prefer server metric deltas or
  token-id-level timing.

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
