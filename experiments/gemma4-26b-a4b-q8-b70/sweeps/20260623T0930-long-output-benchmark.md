# Long-Output Sustained Decode Benchmark

Date: 2026-06-23
Owner/agent: Codex
GPU / port: GPU0 / `18260`

## Hypothesis

The default p512/o512 prompt lets Gemma stop naturally around 140-160 output
tokens, which mixes decode speed with stop behavior and TTFT amortization. A
short deterministic "continue until token limit" prompt should force full
512-token completions and give a cleaner sustained-decode measurement for the
current best llama.cpp/SYCL runtime.

## Run Identity

- model repo: `unsloth/gemma-4-26B-A4B-it-GGUF`
- filename: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- file bytes: `27,636,230,944`
- model revision: `3bb10d594514ef4edb7f3a65d41a7e4eb8c5767a`
- runtime: llama.cpp
- runtime commit/version: `dec5ca557`
- backend: SYCL/Level Zero, LocalMaxxing backend enum `xpu`
- GPU: Intel Arc Pro B70, one full model replica on `level_zero:0`
- context: `8192`
- batch / ubatch: `512 / 64`
- KV cache dtype: `f16 / f16`
- API mode: OpenAI-compatible `/v1/chat/completions`
- seed: `1`
- command:

```bash
LABEL=gemma4-q8-gpu0-currentbest-longprompt-deep-20260623T0945 \
GPU_INDEX=0 PORT=18260 CTX_SIZE=8192 BATCH_SIZE=512 UBATCH_SIZE=64 THREADS=16 \
CACHE_TYPE_K=f16 CACHE_TYPE_V=f16 POLL=50 FLASH_ATTN=off REASONING=off \
GGML_SYCL_DISABLE_OPT=0 CANARY_REPEATS=96 BENCH_REPEATS=8 \
BENCH_PROMPT_MODE=long \
EXTRA_LLAMA_ARGS='--parallel 1 --cache-ram 0' \
scripts/run-gemma4-26b-first-baseline.sh
```

- env delta: `GGML_SYCL_DISABLE_OPT=0`, `FLASH_ATTN=off`, `--parallel 1`,
  `--cache-ram 0`, `THREADS=16`, `BENCH_PROMPT_MODE=long`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-currentbest-longprompt-deep-20260623T0945.server.log`

## Result

- chat canary: **384/384 pass**
- benchmark prompt shape: `prompt_mode=long`; LocalMaxxing payload records
  `75` prompt tokens and `512` output tokens
- output tok/s after TTFT: **42.7163**
- wall tok/s: **41.3512**
- TTFT: `395.68 ms`
- repeat stats: `8` benchmark repeats, exactly `512` completion tokens each,
  after-TTFT CV `0.00020`

## Decision

Win for sustained decode: this breaks the previous promoted 42.1539 tok/s
single-B70 Q8 result when measuring after-TTFT decode on a fixed 512-token
output. It is **not** a direct replacement for the natural-stop/default-prompt
record because the prompt/output shape changed.

Queued for LocalMaxxing as a separate short-prompt sustained-decode record.

## Artifacts

- benchmark JSON:
  `data/gemma4-q8-gpu0-currentbest-longprompt-deep-20260623T0945/p512o512.json`
- canary JSON:
  `data/gemma4-q8-gpu0-currentbest-longprompt-deep-20260623T0945/chat-canary.json`
- summary:
  `data/gemma4-q8-gpu0-currentbest-longprompt-deep-20260623T0945/summary.json`
- payload queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-long512-20260623.queue.json`

## Follow-Up

The `long` mode is a short instruction prompt. For future 512-input /
512-output comparisons, use the new `filled-long` prompt mode added to
`scripts/bench-openai-single-decode.py`, which also records prompt hash/preview
and usage-derived prompt/completion token stats.
