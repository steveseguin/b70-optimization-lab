# Gemma 4 Q8 AOT MTP n Sweep

Date: 2026-06-23
Owner/agent: Codex
GPU / port: GPUs 0-3 / ports 18260-18263

## Hypothesis

The BMG AOT build produced the best n=3 run so far. This sweep retests AOT n=3
and checks whether AOT changes the best draft length or polling choice.

## Common Identity

- model repo: `unsloth/gemma-4-26B-A4B-it-GGUF`
- main file: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft file: `mtp-gemma-4-26B-A4B-it.gguf`
- model revision: `3bb10d594514ef4edb7f3a65d41a7e4eb8c5767a`
- runtime: llama.cpp server `dec5ca557`, BMG AOT build
  `/home/steve/src/llama.cpp/build-sycl-b70-aot-bmg-g31/bin/llama-server`
- backend: SYCL / Level Zero
- target and draft KV: `f16/f16`
- API mode: `/v1/chat/completions`
- canary: `96` repeats x `4` cases = `384` rows
- benchmark: `BENCH_PROMPT_MODE=long`, actual `75` prompt tokens and `512`
  generated tokens, `8` repeats

## Results

| Label | GPU | Config delta | Canary | Tok/s after TTFT | Wall tok/s | CV | Acceptance | Decision |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- | --- |
| `gemma4-q8-gpu0-mtp-n3-aot-repeat-long-deep-20260623T0353` | 0 | AOT `n=3`, `POLL=50` | 384/384 | **48.3473** | **46.6021** | 0.0459 | len `3.26`; rates `(0.858, 0.752, 0.650)` | **new valid best** |
| `gemma4-q8-gpu1-mtp-n2-aot-long-deep-20260623T0353` | 1 | AOT `n=2` | 384/384 | 46.1539 | 44.5520 | 0.0181 | len `2.61`; rates `(0.858, 0.756)` | valid, slower |
| `gemma4-q8-gpu2-mtp-n4-aot-long-deep-20260623T0353` | 2 | AOT `n=4` | 384/384 | 43.5555 | 42.1337 | 0.0272 | len `3.61`; rates `(0.837, 0.701, 0.598, 0.469)` | loss |
| `gemma4-q8-gpu3-mtp-n3-aot-poll100-long-deep-20260623T0353` | 3 | AOT `n=3`, `POLL=100` | 384/384 | 47.0273 | 45.3688 | 0.0242 | len `3.21`; rates `(0.857, 0.731, 0.622)` | valid, slower |

## Decision

AOT `n=3` with the base `POLL=50`, `BATCH=512`, `UBATCH=64`, `THREADS=16`
settings remains the best. The repeat reached `48.347281` tok/s after TTFT and
`46.602117` wall tok/s with `384/384` canary, improving over the previous AOT
record (`47.922048`) by about `0.89%`. Submitted to LocalMaxxing and approved
as `cmqqctk4w014kqo011gyyks7r`.

AOT does not make `n=4` viable for this prompt shape; the extra draft work still
costs more than the accepted tokens are worth. `POLL=100` remains slower.

## Artifacts

- summaries:
  - `data/gemma4-q8-gpu0-mtp-n3-aot-repeat-long-deep-20260623T0353/summary.json`
  - `data/gemma4-q8-gpu1-mtp-n2-aot-long-deep-20260623T0353/summary.json`
  - `data/gemma4-q8-gpu2-mtp-n4-aot-long-deep-20260623T0353/summary.json`
  - `data/gemma4-q8-gpu3-mtp-n3-aot-poll100-long-deep-20260623T0353/summary.json`
- LocalMaxxing queue for promoted AOT repeat:
  - `data/localmaxxing-gemma4-26b-a4b-q8-b70-mtp-n3-aot-repeat-long512-20260623.queue.json`
- LocalMaxxing response:
  - `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n3-aot-repeat-long512-20260623.submit.log`
