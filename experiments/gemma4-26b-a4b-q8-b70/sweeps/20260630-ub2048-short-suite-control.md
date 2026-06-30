# Gemma 4 26B Q8 UB2048 Short-Suite Control

Date: 2026-06-30

Purpose: validate the long-prefill service candidate
`BATCH_SIZE=2048`, `UBATCH_SIZE=2048` against the fixed realistic cold-response
short-decode suite before considering it as a global/default recipe.

This is a valid strict-suite screen, but it is not a new LocalMaxxing/headline
record because it does not beat the current `121.41411987308553 tok/s` Gemma Q8
record.

## Identity

Common identity:

- target/verifier: Gemma 4 26B A4B `UD-Q8_K_XL`;
- draft: Q4_0 MTP draft;
- hardware: one Intel Arc Pro B70 per run, four GPUs used in parallel;
- llama.cpp commit: `c926ad098`;
- `FLASH_ATTN=on`;
- `CTX_SIZE=32768`;
- `GGML_SYCL_ENABLE_VMM=1`;
- `THREADS=8`;
- `POLL=100`;
- `MAX_TOKENS=512`;
- `CANARY_REPEATS=32`;
- `REALISTIC_GATE=1`;
- `REALISTIC_METRIC_TOKENS=100`;
- `--ctx-checkpoints 0`;
- no n-gram/history acceleration, prompt/KV reuse, response reuse, or context
  checkpoints;
- `cached_tokens=0` for every realistic-suite request;
- all rows passed `realistic_final_gate.passed=true`.

Only `BATCH_SIZE` / `UBATCH_SIZE` and the GPU/port changed.

## Results

Primary metric is median generated-token throughput for tokens 1-100 after
TTFT across the fixed realistic suite.

| GPU | batch | ubatch | gate | cached0 | tok/s 1-100 median | p10 | mean | full-512 after TTFT | wall full-512 | TTFT ms |
|---:|---:|---:|:---:|:---:|---:|---:|---:|---:|---:|---:|
| 0 | 1024 | 1024 | pass | yes | 114.857408 | 105.335539 | 116.277257 | 111.757975 | 106.813324 | 179.091338 |
| 2 | 1024 | 1024 | pass | yes | 118.078478 | 110.359424 | 117.758340 | 110.575621 | 106.375063 | 180.086630 |
| 1 | 2048 | 2048 | pass | yes | 118.700316 | 104.477480 | 115.098461 | 107.835546 | 103.774954 | 180.071424 |
| 3 | 2048 | 2048 | pass | yes | 117.902866 | 107.982600 | 118.838060 | 111.699849 | 106.109134 | 179.262444 |

Aggregate primary medians:

- UB1024 controls: `116.46794311469674 tok/s` average
  (`114.85740831972808`, `118.0784779096654`).
- UB2048 candidates: `118.30159066915866 tok/s` average
  (`118.70031578164084`, `117.90286555667649`).
- UB2048 was `+1.83364755446192 tok/s` / `+1.57%` on this paired screen.

Artifacts:

- `data/gemma4-q8-gpu0-short-ub1024-control-full512-20260630A/summary.json`
- `data/gemma4-q8-gpu2-short-ub1024-control-full512-20260630A/summary.json`
- `data/gemma4-q8-gpu1-short-ub2048-candidate-full512-20260630A/summary.json`
- `data/gemma4-q8-gpu3-short-ub2048-candidate-full512-20260630A/summary.json`

## Decision

- UB2048 passed the fixed cold short-decode gate and did not show a short-suite
  regression in this paired screen.
- UB2048 remains the best general long-prefill service candidate from
  `20260630-prefill-ubatch-service-screen.md`, where it improved approximate
  prefill by `+10.8%`, `+9.2%`, `+7.4%`, and `+6.1%` at 8.1K, 12.1K, 16.2K,
  and 21.5K actual prompt tokens.
- Do **not** submit this short-suite screen to LocalMaxxing and do **not**
  replace the active headline recipe from it: the best UB2048 candidate here
  (`118.70031578164084 tok/s`) is below the current strict record
  `121.41411987308553 tok/s`.
- For short-record reproduction, keep the promoted UB1024 recipe exactly as
  recorded.
- For service / long-context deployment, UB2048 is a reasonable default
  candidate because it improves long prefill and passed the short gate. If the
  service decision is high-value, retest UB2048 versus UB2560 with multiple
  unique long prompts at `>20K` actual prompt tokens before standardizing.

## Follow-Up

The short-record lane should not spend more time on batch/ubatch roulette unless
a source patch changes the compute/memory balance. The remaining credible
short-record work is still verifier-cost reduction: a bonus-preserving
accept-prefix verifier LM-head/backend design or a profile-backed verifier MoE
boundary reduction.
