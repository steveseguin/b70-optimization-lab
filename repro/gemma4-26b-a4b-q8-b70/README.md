# Gemma 4 26B A4B Q8 / B70 Repro Recipes

> **Certification: `lab-replay`.** This replays the result on a host where the
> lab's source trees, binaries, caches, models, and topology already exist. It
> is not a portable install guide; see its `missing` entry in
> [`repro/guide-catalog.json`](../guide-catalog.json).

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

- `124.97714084813418 tok/s`;
- `data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`;
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
  to `118.73 tok/s`, below the `124.98 tok/s` record.

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
For direct four-GPU service comparisons,
`run-vdr2-long-context-service-gate.sh` also accepts an optional fifth
`LANE_SPECS` field:
`GPU:BATCH:UBATCH:TAG:PREFILL_UBATCH_SIZE`.
The per-lane ladder kept `2048` as the balanced phase-prefill default; `2304`
and `2560` are valid pure-prefill diagnostics but lower long-context decode.
Follow-up high/fine ladders through `3072` and near-2048 values
`2112/2176/2240` did not find a no-decode-regression improvement, so keep
`LLAMA_PREFILL_UBATCH_SIZE=2048` for the balanced service recipe. See
`experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-phase-prefill-per-lane-ladder.md`
and
`experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-phase-prefill-high-and-fine-ladders.md`.

Use `run-vdr2-kqregbcast-service-confirm.sh` to reproduce the optional
global-GQA8 KQ register/broadcast service flag:

- candidate flag: `GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1`;
- source patch:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-source.patch`;
- DKQ576 extension source patch:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-dkq576-source.patch`;
- balanced A/B/C/D result: 48/48 valid long-context rows, `cached_tokens=0`,
  approximate prefill `+0.730%` mean, decode `+0.431%` mean;
- DKQ576 balanced A/B/C/D result: 48/48 valid long-context rows,
  `cached_tokens=0`, approximate prefill `+0.722%` mean / `+0.813%` median,
  TTFT `-0.765%`, positive by GPU and by case;
- DKQ576 short-decode guard:
  `data/gemma4-short-decode-guard-20260702Tkqregbcast-dkq576-shortguard.json`,
  four lanes passed the fixed realistic gate and `cached_tokens=0` at
  `MAX_TOKENS=256`, `CANARY_REPEATS=8`;
- note:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-global-fattn-kq-reg-bcast-service-win.md`.
- DKQ576 note:
  `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-global-fattn-kq-reg-bcast-dkq576-service-win.md`.

This is a service/prefill micro-win, not a short-decode LocalMaxxing headline
record.

## Partial Prompt-Processing Experiments

Do not enable the archived `KV_min` left-bound FlashAttention scan in promoted
recipes. It repeatedly improved long-context prefill by about `+4.7%` to
`+6.1%`, but the fixed short-decode guard showed a `~1-2%` regression risk, so
it fails the "no short decode loss" rule. The active source was reverted after
the patch and results were preserved. Future versions need a prefill-only
dispatch/kernel or another design that leaves generation untouched.

Primary note:
`experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-sycl-fattn-kv-min-left-bound-partial.md`

## Negative Prompt-Processing Knobs

Do not repeat these without a source/kernel change:

- forced DV512/GQA stream-k;
- forced one or all KQ parallel blocks;
- forced `nbatch_fa=128`;
- disabling the KV max scan for the current shape.
- enabling the archived `KV_min` left-bound scan in the current form.

See:

- `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-scheduler-knobs-screen.md`;
- `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-gqa8-midubatch-balance-screen.md`;
- `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-nbatchfa128-negative.md`;
- `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-kv-max-scan-threshold-negative.md`.
- `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-sycl-fattn-kv-min-left-bound-partial.md`.
