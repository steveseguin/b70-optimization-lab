# Gemma 4 26B A4B Q8 / B70 Repro Recipes

These scripts reproduce the validated Gemma 4 26B A4B Q8 lanes on one Intel
Arc Pro B70 per replica. They are intentionally split by metric so service
prompt-processing work does not get confused with LocalMaxxing short-decode
headline records.

## Short Decode Record/Guard

Use `run-vdr2-selecteddown-record.sh` for a single fixed realistic cold-suite
record run, or `run-vdr2-short-decode-guard.sh` for a four-lane regression
guard.

Headline submissions must use the fixed realistic suite, one cold response per
prompt, `cached_tokens=0`, no prompt/KV/history reuse, and median generated
tokens 1-100 after TTFT as the primary metric.

Current valid headline record at time of writing:

- `123.67689864739785 tok/s`;
- `data/gemma4-q8-gpu0-finalpostnorm-on-full512-20260630T024027Z-finalpost-full512/summary.json`;
- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`.

## Long-Prefill Service Gate

Use `run-vdr2-gqa8-long-prefill-service.sh` to reproduce the validated
FlashAttention DV512/GQA8 service optimization.

This is not a short-decode headline result. It is a cold long-context service
gate that validates exact retrieval JSON, `cached_tokens=0`, and prompt
processing / TTFT behavior across long prompts.

Promoted service optimization:

- `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`;
- `FLASH_ATTN=on`;
- `GGML_SYCL_ENABLE_VMM=1`;
- default broad lanes: `UBATCH_SIZE=1024`, `2048`, `2304`, `2560`;
- best pure prefill seen: UB2304 median about `1075.98 tok/s`;
- balanced general service default remains UB2048 unless the deployment is
  purely long-prefill oriented.
- middle ubatches (`1280/1536/1792/1920`) were screened after the GQA8 win;
  UB1280 was the best compromise but still dropped the fixed short-decode guard
  to `118.73 tok/s`, below the `123.68 tok/s` record.

Primary note:
`experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-prefill-win.md`

Use `run-vdr2-gqa8-phase-prefill-service.sh` when the goal is an operational
single-server service profile: prompt processing uses
`LLAMA_PREFILL_UBATCH_SIZE=2048`, while decode remains at `UBATCH_SIZE=1024`.
This preserves the short-decode-friendly physical decode size while getting
UB2048-style prompt chunks for long-context prefill. It requires the
default-off source patch recorded at
`patches/gemma4-26b-a4b-q8-b70/20260630-llama-phase-prefill-ubatch-memory-sized-experiment.patch`.

The phase-prefill recipe is also a service lane, not a LocalMaxxing headline.
Its validation note is
`experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-phase-prefill-ubatch-service.md`.
New phase-prefill runs should record `prefill_ubatch_size` in each server log
header and `summary.json` launcher identity; use that field when comparing
service artifacts.

## Negative Prompt-Processing Knobs

Do not repeat these without a source/kernel change:

- forced DV512/GQA stream-k;
- forced one or all KQ parallel blocks;
- forced `nbatch_fa=128`;
- disabling the KV max scan for the current shape.

See:

- `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-scheduler-knobs-screen.md`;
- `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-gqa8-midubatch-balance-screen.md`;
- `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-nbatchfa128-negative.md`;
- `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-kv-max-scan-threshold-negative.md`.
