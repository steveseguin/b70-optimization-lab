# Gemma 4 Q8 AOT MTP Launcher / Runtime Flags

Date: 2026-06-23
Owner/agent: Codex
GPU / port: GPUs 0-3 / ports 18260-18263

## Hypothesis

The MTP micro-knobs did not beat the AOT n=3 record. This sweep tests broader
launcher/runtime controls that might change scheduling, memory placement, or
SYCL kernel selection.

## Common Identity

- model repo: `unsloth/gemma-4-26B-A4B-it-GGUF`
- main file: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft file: `mtp-gemma-4-26B-A4B-it.gguf`
- runtime: llama.cpp server `dec5ca557`, BMG AOT build
- backend: SYCL / Level Zero
- MTP: `--spec-type draft-mtp --spec-draft-n-max 3`
- target and draft KV: `f16/f16`
- canary: `96` repeats x `4` cases = `384` rows, except failed lanes
- benchmark: `BENCH_PROMPT_MODE=long`, actual `75` prompt tokens and `512`
  generated tokens, `8` repeats

## Results

| Label | GPU | Config delta | Canary | Tok/s after TTFT | Wall tok/s | TTFT | Decision |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-mtp-n3-aot-cacheram1-long-deep-20260623T0413` | 0 | `--cache-ram 1` | 384/384 | 47.9263 | 44.1755 | 0.907s | no record; TTFT/wall regression |
| `gemma4-q8-gpu1-mtp-n3-aot-parallel2-long-deep-20260623T0413` | 1 | `--parallel 2` | 384/384 | 47.4177 | 45.7371 | 0.397s | valid, slower |
| `gemma4-q8-gpu2-mtp-n3-aot-disablegraph-long-deep-20260623T0413` | 2 | `GGML_SYCL_DISABLE_GRAPH=1` | 384/384 | 46.3189 | 44.7090 | 0.398s | valid, slower |
| `gemma4-q8-gpu3-mtp-n3-aot-disablednn-long-deep-20260623T0413` | 3 | `GGML_SYCL_DISABLE_DNN=1` | **failed 1/384** | n/a | n/a | n/a | hard correctness failure |

## Decision

No new record. Keep the current AOT n=3 base (`--parallel 1 --cache-ram 0`,
SYCL graph and DNN enabled). `--cache-ram 1` is not useful for the sustained
decode record despite respectable after-TTFT speed because TTFT and wall speed
regress badly. `GGML_SYCL_DISABLE_DNN=1` corrupts the first JSON canary and must
not be used for Gemma 4 Q8 on this B70 stack.

## Artifacts

- summaries / outputs:
  - `data/gemma4-q8-gpu0-mtp-n3-aot-cacheram1-long-deep-20260623T0413/summary.json`
  - `data/gemma4-q8-gpu1-mtp-n3-aot-parallel2-long-deep-20260623T0413/summary.json`
  - `data/gemma4-q8-gpu2-mtp-n3-aot-disablegraph-long-deep-20260623T0413/summary.json`
  - `data/gemma4-q8-gpu3-mtp-n3-aot-disablednn-long-deep-20260623T0413/chat-canary.json`
