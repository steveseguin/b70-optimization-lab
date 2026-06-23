# 20260623T052850Z Valid Baseline With Reasoning Off

## Hypothesis

Disabling Gemma 4 thinking mode should make direct-answer chat canaries return
normal `message.content`, preserving Q8 quality while establishing the first
valid single-B70 llama.cpp baseline.

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
- reasoning mode: `off`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-26b-q8-llamacpp-gpu0-ctx8192-20260623T052850Z.server.log`

## Result

- Server loaded successfully in about 19 seconds and reported:
  - `n_ctx=8192`;
  - `n_ctx_train=262144`;
  - `n_params=25233142046`;
  - model-reported GGUF size `27620407416`;
  - `thinking = 0`.
- Chat canary passed **128/128** rows (`32` repeats x `4` cases).
- p512/o512 chat benchmark:
  - `26.0997 tok/s` mean after TTFT;
  - `24.2443 tok/s` mean wall;
  - `1110` completion tokens across `8` requests;
  - after-TTFT CV `0.00028`, so steady decode is stable.

## Decision

Win for correctness and fit; not a speed win. Promote as the conservative
control baseline and begin four-at-a-time optimization from it.

Do not submit this as a LocalMaxxing record unless explicitly recording a low
baseline. The public Gemma 4 family context is much higher, and this lane should
try batch/ubatch, SYCL runtime, AOT, vLLM, and later MTP before publishing.

## Artifacts

- `data/gemma4-26b-q8-llamacpp-gpu0-ctx8192-20260623T052850Z/models.json`
- `data/gemma4-26b-q8-llamacpp-gpu0-ctx8192-20260623T052850Z/chat-canary.json`
- `data/gemma4-26b-q8-llamacpp-gpu0-ctx8192-20260623T052850Z/p512o512.json`
- `data/gemma4-26b-q8-llamacpp-gpu0-ctx8192-20260623T052850Z/summary.json`
