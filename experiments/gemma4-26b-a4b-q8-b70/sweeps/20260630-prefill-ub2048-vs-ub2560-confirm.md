# Gemma 4 26B Q8 UB2048 vs UB2560 Prefill Confirmation

Date: 2026-06-30

Purpose: confirm whether the earlier service-lane hint for `BATCH_SIZE=2560`,
`UBATCH_SIZE=2560` is strong enough to replace `2048` as the Gemma 4 26B Q8
long-prefill default.

This is diagnostic service-lane work. It is not a LocalMaxxing headline result
and does not replace the fixed realistic cold-suite short-decode record. The
promoted short record remains `121.41411987308553 tok/s` from
`data/gemma4-q8-gpu3-q8lmhead-noreorder-control-full512-20260629T224927Z/summary.json`.

## Identity

Common run identity:

- target/verifier: Gemma 4 26B A4B `UD-Q8_K_XL`;
- draft: Q4_0 MTP draft;
- hardware: one Intel Arc Pro B70 per run, four GPUs used in parallel;
- llama.cpp commit: `c926ad098`;
- `FLASH_ATTN=on`;
- `CTX_SIZE=32768`;
- `GGML_SYCL_ENABLE_VMM=1`;
- `THREADS=8`;
- `POLL=100`;
- `BENCH_PROMPT_MODE=filled-long-unique`;
- `BENCH_REPEATS=3`;
- `MAX_TOKENS=64`;
- `REALISTIC_GATE=0`;
- `cached_tokens=0` for every measured request;
- all prompt hashes distinct;
- `canary_pass_all=true`, `canary_rows_completed=4` for every lane.

Only GPU/port and `BATCH_SIZE` / `UBATCH_SIZE` changed.

## Results

Approx prefill throughput is `prompt_tokens / TTFT`. Prompt generation
overshoots the requested token count, so compare by actual prompt-token rows.

| Requested prompt | Median actual prompt | batch/ubatch | Median prefill tok/s | Mean prefill tok/s | Decode tok/s after TTFT median | Decision |
|---:|---:|---:|---:|---:|---:|---|
| 12,000 | 15,773 | 2048 | **987.308** | **978.034** | **88.314** | best |
| 12,000 | 15,773 | 2560 | 982.391 | 976.278 | 86.536 | slower |
| 16,000 | 20,990 | 2048 | 865.486 | 864.148 | **78.244** | decode better |
| 16,000 | 20,990 | 2560 | **866.815** | **864.881** | 77.058 | prefill tie only |

Detail:

- At the 12K-requested / ~15.8K actual-token shape, UB2048 beats UB2560 by
  about `+0.50%` median prefill and `+2.05%` decode-after-TTFT.
- At the 16K-requested / ~21.0K actual-token shape, UB2560 is only `+0.15%`
  ahead on median prefill and `+0.08%` on mean prefill, while UB2048 is
  `+1.54%` ahead on decode-after-TTFT.
- The earlier single-repeat UBATCH screen made UB2560 look interesting at the
  very-long row; this repeat confirmation reduces that to an effective tie, not
  a reason to standardize on the larger ubatch.

Artifacts:

- `data/gemma4-q8-gpu0-prefill-confirm-ub2048-p16000o64-r3-20260630B/summary.json`
- `data/gemma4-q8-gpu1-prefill-confirm-ub2560-p16000o64-r3-20260630B/summary.json`
- `data/gemma4-q8-gpu2-prefill-confirm-ub2048-p12000o64-r3-20260630B/summary.json`
- `data/gemma4-q8-gpu3-prefill-confirm-ub2560-p12000o64-r3-20260630B/summary.json`

## Decision

- Keep `BATCH_SIZE=2048`, `UBATCH_SIZE=2048` as the best general
  long-prefill service/default candidate.
- Do not promote UB2560. It has no meaningful prefill advantage in the repeat
  confirmation and decodes slower in both confirmed shapes.
- Keep the promoted short-record reproduction on UB1024. UB2048 is a
  service/default candidate only; it did not beat the strict short-record row in
  `20260630-ub2048-short-suite-control.md`.
- Do not submit these rows to LocalMaxxing. They are unique-prompt,
  `cached_tokens=0` service diagnostics, but they are not the fixed realistic
  final gate and are not short-decode headline results.
