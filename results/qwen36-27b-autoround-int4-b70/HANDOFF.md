# Qwen3.6 27B AutoRound Handoff

Last updated: 2026-07-03

This is the bookmark for `Intel/Qwen3.6-27B-int4-AutoRound` on Intel Arc Pro
B70.

## Current State

The lane has passed initial TP1 bring-up. The repository scaffolding exists,
the pinned Intel snapshot is downloaded under `/mnt/fast-ai/llm-cache/hf`, and
one B70 can serve the model through vLLM/XPU at `max_model_len=2048`.

Known-good smoke:

- server log:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/servers/tp1-gpu0-port19410-20260703T012317Z.log`;
- smoke JSON:
  `../../data/qwen36-27b-autoround-openai-smoke-20260703T013020Z.json`;
- result: `pass=true`, content
  `{"answer": 42, "unit": "widgets"}`, `finish_reason=stop`;
- runtime: vLLM local `/home/steve/src/vllm`, `torch 2.11.0+xpu`,
  quantization auto-detected as `inc`, XPU graph off;
- MTP2 acceptance observed: `105/108` accepted draft tokens.

Current valid fresh-response baseline:

- config: Intel checkpoint, TP1, one B70, vLLM/XPU chat endpoint, XPU graph on,
  `qwen3_next_mtp`, `num_speculative_tokens=3`,
  `COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":8}'`,
  `MAX_NUM_BATCHED_TOKENS=1024`, thinking disabled;
- final-gate policy: Qwen-specific fixed realistic suite, each prompt once,
  `cached_tokens=0` on all 12 requests, no prefix/KV/context/response reuse,
  `return_token_ids=true`, primary metric timed from streamed token-id counts
  for generated tokens 1-100 after TTFT;
- current best Qwen-suite artifact:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-realistic128-chat-tokenids-qwensuite-20260703T034112Z.json`;
- primary result: median `47.624 tok/s`, p10 `43.998`, mean `48.403`,
  full-output after-TTFT median `48.484`, wall median `39.072`,
  TTFT median `637.3 ms`;
- supporting same-config Qwen-suite artifact:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp3-xpugraph1-cg8-realistic128-chat-tokenids-20260703T033403Z.json`
  at median `48.003 tok/s`.

Current synthetic diagnostic optimization state:

- best synthetic search row so far: Intel checkpoint, TP1, XPU graph on,
  `qwen3_next_mtp`, `num_speculative_tokens=5`,
  `COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":16}'`,
  `MAX_NUM_BATCHED_TOKENS=1024`;
- synthetic p512/o512 `vllm-random` corrected after-first throughput:
  `81.773 tok/s`, decode `12.182 ms/token`, draft acceptance `95.51%`;
- evidence:
  `../../data/qwen36-27b-autoround-int4-b70-baselines/intel-mtp5-xpugraph1-cg16-specmetrics-p512o512-r3-20260703T031846Z.json`;
- MTP6/cg16 lost (`78.556 tok/s`), so do not keep increasing
  speculative-token count without a new acceptance/cost reason;
- this is **not** a headline or LocalMaxxing result. It is a synthetic
  repetitive diagnostic. It is useful for screening MTP/graph changes, but it
  lost to MTP3/cg8 under the realistic chat gate.

Fresh-gate instrumentation status:

- local vLLM reporting patch applied and preserved at
  `../../patches/qwen36-27b-autoround-int4-b70/vllm-prompt-tokens-details-zero-20260703.patch`;
- after restarting a server with that patch, non-stream chat/completions return
  `usage.prompt_tokens_details.cached_tokens=0`;
- `scripts/bench-openai-realistic-suite.py --return-token-ids` requests vLLM
  streamed token IDs and computes the primary tokens-1-100 metric from token-id
  receipt timestamps. Text chunks are still grouped, so do not use chunk counts
  as tokens.

Read in order:

1. `README.md`
2. `reproduce.md`
3. `validity-gates.md`
4. `bugs-failed-paths.md`
5. `../../experiments/qwen36-27b-autoround-int4-b70/README.md`
6. `../../experiments/qwen36-27b-autoround-int4-b70/research-plan.md`

## Current Goal

Continue INT4 optimization without promoting synthetic scores:

- use MTP5/cg16 as the current synthetic reference for quick screens;
- prefer chat-mode realistic-suite checks for quality because completions mode
  bypasses the chat template and emits `<think>` text;
- treat MTP3/cg8 as the current valid realistic-chat baseline to beat;
- rerun the realistic Qwen suite with `--return-token-ids` before promoting any
  MTP/speculation or kernel change;
- inspect the GDN/spec accepted-state postprocess path for a safe optimization;
- keep long-context/prompt-processing optimization separate from the short
  decode record.
