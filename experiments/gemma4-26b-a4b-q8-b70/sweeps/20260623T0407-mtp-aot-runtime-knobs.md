# Gemma 4 Q8 AOT MTP Runtime Knobs

Date: 2026-06-23
Owner/agent: Codex
GPU / port: GPUs 0-3 / ports 18260-18263

## Hypothesis

The AOT n=3 family is the current best. This sweep tests lower-level draft-MTP
runtime knobs that might reduce host/draft overhead without changing model
precision or the target verification path.

## Common Identity

- model repo: `unsloth/gemma-4-26B-A4B-it-GGUF`
- main file: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft file: `mtp-gemma-4-26B-A4B-it.gguf`
- runtime: llama.cpp server `dec5ca557`, BMG AOT build
- backend: SYCL / Level Zero
- MTP: `--spec-type draft-mtp --spec-draft-n-max 3`
- target and draft KV: `f16/f16`
- canary: `96` repeats x `4` cases = `384` rows
- benchmark: `BENCH_PROMPT_MODE=long`, actual `75` prompt tokens and `512`
  generated tokens, `8` repeats

## Results

| Label | GPU | Config delta | Canary | Tok/s after TTFT | Wall tok/s | CV | Acceptance | Decision |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- | --- |
| `gemma4-q8-gpu0-mtp-n3-aot-nobackendsampling-long-deep-20260623T0407` | 0 | `--no-spec-draft-backend-sampling` | 384/384 | 46.9211 | 45.2740 | 0.0297 | len `3.18`; rates `(0.849, 0.720, 0.612)` | loss |
| `gemma4-q8-gpu1-mtp-n3-aot-draftt8-long-deep-20260623T0407` | 1 | `--spec-draft-threads 8` | 384/384 | 47.1161 | 45.4446 | 0.0307 | len `3.23`; rates `(0.856, 0.738, 0.635)` | loss |
| `gemma4-q8-gpu2-mtp-n3-aot-draftt32-long-deep-20260623T0407` | 2 | `--spec-draft-threads 32` | 384/384 | 47.6069 | 45.9011 | 0.0534 | len `3.23`; rates `(0.856, 0.736, 0.633)` | valid, below record |
| `gemma4-q8-gpu3-mtp-n3-aot-draftpoll0-long-deep-20260623T0407` | 3 | `--spec-draft-poll 0` | 384/384 | 47.1955 | 45.5226 | 0.0293 | len `3.21`; rates `(0.848, 0.738, 0.625)` | loss |

## Decision

No new record. The best knob variant was draft threads 32 at `47.606920` tok/s,
still below the current `48.347281` record. Backend sampling should stay on,
draft poll should stay at default, and explicit draft-thread overrides are not
worth promoting.

Next search should move back to broader llama.cpp / SYCL flags, such as cache
RAM, graph/DNN toggles, or a different prompt shape validation, rather than
more MTP micro-knobs.

## Artifacts

- summaries:
  - `data/gemma4-q8-gpu0-mtp-n3-aot-nobackendsampling-long-deep-20260623T0407/summary.json`
  - `data/gemma4-q8-gpu1-mtp-n3-aot-draftt8-long-deep-20260623T0407/summary.json`
  - `data/gemma4-q8-gpu2-mtp-n3-aot-draftt32-long-deep-20260623T0407/summary.json`
  - `data/gemma4-q8-gpu3-mtp-n3-aot-draftpoll0-long-deep-20260623T0407/summary.json`
