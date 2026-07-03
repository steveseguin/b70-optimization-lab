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

Read in order:

1. `README.md`
2. `reproduce.md`
3. `validity-gates.md`
4. `bugs-failed-paths.md`
5. `../../experiments/qwen36-27b-autoround-int4-b70/README.md`
6. `../../experiments/qwen36-27b-autoround-int4-b70/research-plan.md`

## Current Goal

Move from bring-up into optimization:

- record no-spec TP1 fresh-response baseline;
- record MTP2 TP1 fresh-response baseline;
- sweep `num_speculative_tokens=1,2,3,4` with acceptance metrics;
- test XPU graph only after each MTP setting has a correctness gate;
- scale to four independent TP1 replicas once one replica is stable;
- keep long-context/prompt-processing optimization separate from the short
  decode record.
