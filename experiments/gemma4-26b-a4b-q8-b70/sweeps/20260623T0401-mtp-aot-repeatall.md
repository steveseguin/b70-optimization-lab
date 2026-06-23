# Gemma 4 Q8 AOT MTP n=3 Repeat-All

Date: 2026-06-23
Owner/agent: Codex
GPU / port: GPUs 0-3 / ports 18260-18263

## Hypothesis

The current record is an AOT n=3 repeat at `48.347` tok/s after TTFT. This
repeat-all sweep runs the same configuration on all four B70s to measure
GPU-to-GPU spread and determine whether the record is reproducible or a high
sample within normal variance.

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

| Label | GPU | Canary | Tok/s after TTFT | Wall tok/s | CV | Acceptance | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `gemma4-q8-gpu0-mtp-n3-aot-repeatall-long-deep-20260623T0401` | 0 | 384/384 | 47.1855 | 45.4991 | 0.0449 | len `3.22`; rates `(0.855, 0.733, 0.633)` | valid, below record |
| `gemma4-q8-gpu1-mtp-n3-aot-repeatall-long-deep-20260623T0401` | 1 | 384/384 | 47.4390 | 45.7508 | 0.0308 | len `3.23`; rates `(0.862, 0.738, 0.626)` | valid, below record |
| `gemma4-q8-gpu2-mtp-n3-aot-repeatall-long-deep-20260623T0401` | 2 | 384/384 | 47.6454 | 45.9356 | 0.0344 | len `3.24`; rates `(0.861, 0.743, 0.630)` | valid, below record |
| `gemma4-q8-gpu3-mtp-n3-aot-repeatall-long-deep-20260623T0401` | 3 | 384/384 | 47.0130 | 45.3574 | 0.0546 | len `3.20`; rates `(0.844, 0.730, 0.624)` | valid, below record |

## Decision

No new record. The best repeat-all result was GPU2 at `47.645365` tok/s after
TTFT, below the current `48.347281` record. The repeated AOT n=3 family remains
valid and clearly above the non-AOT and no-spec baselines, but the current
record is a high sample within a few-percent-variance family.

Next useful tests should target lower-level speculative runtime knobs or a real
new build/runtime change, not more blind AOT n=3 repeats.

## Artifacts

- summaries:
  - `data/gemma4-q8-gpu0-mtp-n3-aot-repeatall-long-deep-20260623T0401/summary.json`
  - `data/gemma4-q8-gpu1-mtp-n3-aot-repeatall-long-deep-20260623T0401/summary.json`
  - `data/gemma4-q8-gpu2-mtp-n3-aot-repeatall-long-deep-20260623T0401/summary.json`
  - `data/gemma4-q8-gpu3-mtp-n3-aot-repeatall-long-deep-20260623T0401/summary.json`
