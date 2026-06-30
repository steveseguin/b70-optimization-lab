# Gemma 4 26B Q8 Prefill Ladder Baseline

Date: 2026-06-30

Purpose: establish a service-lane prefill / long-context baseline for the
current Gemma 4 26B A4B Q8 record stack without changing the short-decode
recipe. These runs are diagnostic service data, not LocalMaxxing headline
throughput.

## Identity

- Runtime/source: llama.cpp record tree at `c926ad098` family.
- Target/verifier: Gemma 4 26B A4B `UD-Q8_K_XL` GGUF.
- Draft: Q4_0 MTP draft.
- Hardware: one Intel Arc Pro B70 per run; four replicas were used in parallel.
- Recipe family: current selected-down VDR2 record stack.
- Common env/flags:
  - `FLASH_ATTN=on`
  - `CTX_SIZE=32768`
  - `GGML_SYCL_ENABLE_VMM=1`
  - `BATCH_SIZE=1024`
  - `UBATCH_SIZE=1024`
  - `THREADS=8`
  - `POLL=100`
  - `CANARY_REPEATS=1`
  - `REALISTIC_GATE=0`
  - `BENCH_PROMPT_MODE=filled-long-unique`
  - `BENCH_REPEATS=1`
  - `MAX_TOKENS=16`

Freshness: every summarized row reported `cached_tokens=0` and canary pass.
The prompt generator uses a character heuristic, so actual prompt token counts
are higher than the requested ladder labels.

## Results

Summaries:

- `data/gemma4-q8-prefill-ladder-20260630A-summary.json`
- `data/gemma4-q8-prefill-ladder-20260630A-large-summary.json`
- `data/gemma4-q8-prefill-ladder-20260630A-combined-summary.json`

| Requested prompt | Actual prompt | TTFT s | Approx prefill tok/s | Decode tok/s after TTFT | Wall tok/s | GPU | Label |
|---:|---:|---:|---:|---:|---:|---:|---|
| 128 | 294 | 0.566 | 519.095 | 150.169 | 23.777 | 0 | `gemma4-q8-gpu0-prefill-ladder-p128-o16-20260630A` |
| 512 | 804 | 0.986 | 815.783 | 141.368 | 14.562 | 1 | `gemma4-q8-gpu1-prefill-ladder-p512-o16-20260630A` |
| 2048 | 2857 | 2.584 | 1105.705 | 125.367 | 5.901 | 2 | `gemma4-q8-gpu2-prefill-ladder-p2048-o16-20260630A` |
| 4096 | 5597 | 5.146 | 1087.740 | 94.380 | 3.010 | 3 | `gemma4-q8-gpu3-prefill-ladder-p4096-o16-20260630A` |
| 6000 | 8141 | 7.631 | 1066.827 | 106.308 | 2.056 | 0 | `gemma4-q8-gpu0-prefill-ladder-p6000-o16-20260630A` |
| 9000 | 12150 | 12.711 | 955.852 | 95.420 | 1.242 | 1 | `gemma4-q8-gpu1-prefill-ladder-p9000-o16-20260630A` |
| 12000 | 16164 | 18.209 | 887.697 | 86.351 | 0.870 | 2 | `gemma4-q8-gpu2-prefill-ladder-p12000-o16-20260630A` |
| 16000 | 21511 | 27.085 | 794.209 | 92.993 | 0.587 | 3 | `gemma4-q8-gpu3-prefill-ladder-p16000-o16-20260630A` |

## Readout

- Prefill is strongest around the 2.9K to 8.1K actual-token region
  (`~1.07K-1.11K tok/s` by `prompt_tokens / TTFT`).
- Long prompts decline gradually after ~8K actual tokens: `955.9 tok/s` at
  12.1K, `887.7 tok/s` at 16.2K, and `794.2 tok/s` at 21.5K.
- Short decode after TTFT is not the primary metric here because only 16 tokens
  were generated. It remains useful as a smoke signal and stayed in the
  `~86-150 tok/s` range.
- Wall-clock tok/s naturally collapses with long prompts because this ladder is
  measuring first-response TTFT-heavy service behavior.

## Decision

Keep the short-decode record recipe unchanged:

- headline record remains `121.41411987308553 tok/s` on the fixed realistic
  cold suite;
- this ladder is a separate service/context baseline;
- no LocalMaxxing submission from these rows;
- any service-lane candidate must rerun the short fixed suite afterward before
  being allowed to change the promoted recipe.

## Next Service-Lane Experiments

1. Test larger `BATCH_SIZE` / `UBATCH_SIZE` only on long-prompt service shapes,
   starting with representative actual prompt sizes around 8K, 12K, 16K, and
   21K. Candidate values: `1152`, `1536`, and cautiously `2048`. Do not infer
   short-decode wins from this lane.
2. If a long-prompt batch/ubatch candidate improves TTFT without memory or
   correctness issues, rerun a short fixed-suite control to prove no decode
   regression before promotion.
3. Keep KV/cache precision changes separate. They may be useful for service
   capacity, but the user requires no quality loss from the Q8 target lane.
