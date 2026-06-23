# 20260623T052538Z Reasoning Auto Empty Content

## Hypothesis

First conservative Q8 llama.cpp baseline should serve at 8K with f16 KV and
chat canaries.

## Run Identity

- model:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- file bytes: `27,636,230,944`
- revision: `unsloth/gemma-4-26B-A4B-it-GGUF@3bb10d594514ef4edb7f3a65d41a7e4eb8c5767a`
- runtime: llama.cpp `dec5ca557`, SYCL/Level Zero
- GPU: B70 `level_zero:0`, port `18260`
- context: `8192`
- batch / ubatch: `512 / 64`
- KV cache dtype: f16/f16
- flags: `-fa on`, `--poll 50`, `GGML_SYCL_DISABLE_OPT=1`
- reasoning mode: auto (launcher did not yet override it)
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-26b-q8-llamacpp-gpu0-ctx8192-20260623T052538Z.server.log`

## Result

- Server loaded successfully and reported `n_ctx=8192`, `n_params=25233142046`,
  and GGUF metadata model size `27620407416`.
- First chat canary failed at repeat 0 / JSON case.
- Response `message.content` was empty.
- Server log showed Gemma chat template `thinking = 1` and generated 32 tokens:
  prompt `145.58 tok/s`, eval `27.25 tok/s`, graphs reused `31`.

## Decision

Loss, but useful. This is not a fit/OOM failure and not a Q8 model-file
failure. The first fix is to default the launcher to `REASONING=off` so direct
speed canaries receive normal chat content. Thinking-enabled mode should be
tracked separately from the direct-answer speed baseline.

## Artifacts

- `data/gemma4-26b-q8-llamacpp-gpu0-ctx8192-20260623T052538Z/models.json`
- `data/gemma4-26b-q8-llamacpp-gpu0-ctx8192-20260623T052538Z/chat-canary.json`
