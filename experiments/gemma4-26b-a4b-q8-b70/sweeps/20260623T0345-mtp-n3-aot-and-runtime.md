# Gemma 4 Q8 MTP n=3 AOT And Runtime Follow-Ups

Date: 2026-06-23
Owner/agent: Codex
GPU / port: GPUs 0-3 / ports 18260-18263

## Hypothesis

The repeated `n=3` MTP base is the best known setting. This sweep checks
whether a simple repeat, larger ubatch, fewer CPU threads, or the BMG AOT
llama.cpp build can push the same Q8/f16 quality lane higher.

## Common Identity

- model repo: `unsloth/gemma-4-26B-A4B-it-GGUF`
- main file: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft file: `mtp-gemma-4-26B-A4B-it.gguf`
- model revision: `3bb10d594514ef4edb7f3a65d41a7e4eb8c5767a`
- runtime: llama.cpp server `dec5ca557`
- backend: SYCL / Level Zero
- target and draft KV: `f16/f16`
- MTP: `--spec-type draft-mtp --spec-draft-n-max 3`
- API mode: `/v1/chat/completions`
- canary: `96` repeats x `4` cases = `384` rows
- benchmark: `BENCH_PROMPT_MODE=long`, actual `75` prompt tokens and `512`
  generated tokens, `8` repeats

## Results

| Label | GPU | Config delta | Canary | Tok/s after TTFT | Wall tok/s | CV | Acceptance | Decision |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- | --- |
| `gemma4-q8-gpu0-mtp-n3-repeat2-long-deep-20260623T0345` | 0 | base repeat | 384/384 | 47.3395 | 45.6759 | 0.0339 | len `3.22`; rates `(0.852, 0.733, 0.631)` | valid, below record |
| `gemma4-q8-gpu1-mtp-n3-ub128-long-deep-20260623T0345` | 1 | `UBATCH=128` | 384/384 | 45.7125 | 44.3342 | 0.0216 | len `3.16`; rates `(0.834, 0.714, 0.608)` | loss |
| `gemma4-q8-gpu2-mtp-n3-t8-long-deep-20260623T0345` | 2 | `THREADS=8` | 384/384 | 46.6682 | 45.0266 | 0.0451 | len `3.19`; rates `(0.851, 0.726, 0.617)` | loss |
| `gemma4-q8-gpu3-mtp-n3-aot-bmg-long-deep-20260623T0345` | 3 | BMG AOT build, `GGML_SYCL_DEVICE_ARCH=bmg-g31` | 384/384 | **47.9220** | **46.1837** | 0.0424 | len `3.24`; rates `(0.854, 0.745, 0.646)` | **new valid best** |

## Decision

The AOT BMG build is a small but real improvement on the same Q8/f16 MTP n=3
lane: `47.922048` tok/s after TTFT and `46.183651` wall tok/s, with `384/384`
canary. It improves over the previous approved record (`47.630060`) by about
`0.61%`. Submitted to LocalMaxxing and approved as
`cmqqcje2r014fqo01e8rrgwwr`. Because the margin is small and CV is `0.042`,
repeat confirmation is worthwhile, but the run is a valid new record by the
lane rules.

`UBATCH=128` and `THREADS=8` are not useful for this prompt shape. Base n=3
repeat stayed close to the prior record, which supports that the record family
is stable.

## Artifacts

- summaries:
  - `data/gemma4-q8-gpu0-mtp-n3-repeat2-long-deep-20260623T0345/summary.json`
  - `data/gemma4-q8-gpu1-mtp-n3-ub128-long-deep-20260623T0345/summary.json`
  - `data/gemma4-q8-gpu2-mtp-n3-t8-long-deep-20260623T0345/summary.json`
  - `data/gemma4-q8-gpu3-mtp-n3-aot-bmg-long-deep-20260623T0345/summary.json`
- LocalMaxxing queue for promoted AOT result:
  - `data/localmaxxing-gemma4-26b-a4b-q8-b70-mtp-n3-aot-bmg-long512-20260623.queue.json`
- LocalMaxxing response:
  - `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-mtp-n3-aot-bmg-long512-20260623.submit.log`
