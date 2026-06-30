# Gemma 4 26B Q8 Prefill UBATCH Service Screen

Date: 2026-06-30

Purpose: tune prefill / long-context service TTFT for the current Gemma 4 26B
Q8 record stack without changing the promoted short-decode recipe.

This is diagnostic service-lane work. It is not a LocalMaxxing headline result
and does not replace the fixed realistic cold-suite short-decode record.

## Identity

Common run identity:

- target/verifier: Gemma 4 26B A4B `UD-Q8_K_XL`;
- draft: Q4_0 MTP draft;
- hardware: one Intel Arc Pro B70 per run, four GPUs used in parallel;
- `FLASH_ATTN=on`;
- `CTX_SIZE=32768`;
- `GGML_SYCL_ENABLE_VMM=1`;
- `THREADS=8`;
- `POLL=100`;
- `REALISTIC_GATE=0`;
- `BENCH_PROMPT_MODE=filled-long-unique`;
- `BENCH_REPEATS=1`;
- `MAX_TOKENS=16`;
- `CANARY_REPEATS=1`;
- `cached_tokens=0` and canary pass for every row below.

Only `BATCH_SIZE` / `UBATCH_SIZE` changed. The prompt generator overshoots by
tokens, so compare by the actual prompt-token column.

## Results

Summary artifacts:

- baseline UB1024:
  `data/gemma4-q8-prefill-ladder-20260630A-large-summary.json`
- UB1536:
  `data/gemma4-q8-prefill-ub1536-20260630A-summary.json`
- UB2048:
  `data/gemma4-q8-prefill-ub2048-20260630A-summary.json`
- UB2560:
  `data/gemma4-q8-prefill-ub2560-20260630A-summary.json`
- UB3072:
  `data/gemma4-q8-prefill-ub3072-20260630A-summary.json`

Approx prefill throughput is `prompt_tokens / TTFT`.

| Actual prompt tokens | UB1024 | UB1536 | UB2048 | UB2560 | UB3072 | Best |
|---:|---:|---:|---:|---:|---:|---|
| 8,141 | 1066.827 | 1114.486 | **1181.939** | 1126.020 | 1145.103 | UB2048 |
| 12,150 | 955.852 | 1021.960 | 1044.121 | **1044.277** | 1040.519 | UB2560, effectively tied with UB2048 |
| 16,164 | 887.697 | 930.271 | **953.007** | 946.462 | 937.679 | UB2048 |
| 21,511 | 794.209 | 832.078 | 842.530 | **848.589** | 837.189 | UB2560 |

Relative to UB1024:

- UB1536: `+4.5%`, `+6.9%`, `+4.8%`, `+4.8%`.
- UB2048: `+10.8%`, `+9.2%`, `+7.4%`, `+6.1%`.
- UB2560: `+5.5%`, `+9.2%`, `+6.6%`, `+6.8%`.
- UB3072: `+7.3%`, `+8.9%`, `+5.6%`, `+5.4%`.

Decode-after-TTFT is noisy with only 16 generated tokens and should not be used
as a headline decode metric from this screen.

## Decision

- Use `BATCH_SIZE=2048`, `UBATCH_SIZE=2048` as the default service-lane
  prefill candidate. It is best on two of four shapes and near-best on the
  other two, with the strongest overall improvement versus UB1024.
- Keep `UBATCH_SIZE=2560` as a possible very-long-prompt follow-up: it wins the
  21.5K actual-token row by a small margin and ties UB2048 at 12.1K.
- Reject `UBATCH_SIZE=3072` for now. It fits and passes canary, but regresses
  versus UB2048/UB2560 on these shapes.
- Follow-up short-suite control has now been completed:
  `20260630-ub2048-short-suite-control.md`. UB2048 passed the fixed cold
  short-decode gate with `cached_tokens=0` and averaged `118.30159066915866
  tok/s` versus UB1024 controls at `116.46794311469674 tok/s`, but the best
  UB2048 candidate (`118.70031578164084 tok/s`) did not beat the current
  `121.41411987308553 tok/s` headline. Treat UB2048 as a service/default
  candidate, not a new short-record recipe.

## Next Steps

1. Keep the promoted short-record reproduction on UB1024 unless a future
   full512 strict run actually beats `121.41411987308553 tok/s`.
2. For service / long-context deployment, use UB2048 as the best general
   candidate tested so far.
3. For very long prompts (`>20K` actual tokens), retest UB2048 versus UB2560
   with more than one unique prompt before making a service deployment choice.
