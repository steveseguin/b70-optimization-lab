# 2026-06-27T16:51Z Realistic Final Gate VDR Sweep

## Purpose

Apply the new promotion rule to the Gemma 4 26B A4B Q8 lane:

- fixed realistic prompt suite;
- each prompt once as a cold first response;
- `cached_tokens=0` for every request;
- no prompt/KV cache reuse, context checkpoints, response reuse, n-gram/history
  acceleration, or warmed repeated prompts;
- target/verifier stays `UD-Q8_K_XL`;
- primary metric is median generated-token throughput for tokens 1-100 after
  TTFT across the suite.

This demotes the earlier `170+ tok/s` synthetic filled-long rows to diagnostic
status. They remain valuable for finding kernels, but they are not publishable
real-world throughput.

## Fixed Suite

- suite: `repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json`
- runner: `scripts/bench-openai-realistic-suite.py`
- suite id: `gemma4-26b-a4b-q8-b70-realistic-v1`
- prompts: 12 fixed prompts, each sent once
- metric window: generated-token events 1-100 after TTFT
- gate requirement: `cached_tokens=0` on every row

`chunk_count == completion_tokens` is informational only. llama.cpp may count
an EOS/final token in `usage.completion_tokens` that is not emitted as a text
delta. Promotion requires enough streamed text-delta events to measure the
first 100 generated tokens.

## Results

All rows below passed the chat canary and the realistic final gate.

| Run | Mode | VDR | median tok/s 1-100 after TTFT | p10 | mean | median full512 after TTFT | median wall full512 | median TTFT |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `data/gemma4-q8-gpu0-vdr4default-realistic-gate-v2-20260627T165101Z/` | draft-MTP `n=7`, `n_min=3`, `p_min=0.10` | 4 | **75.614** | 61.816 | 72.719 | 69.210 | 67.002 | 181.3 ms |
| `data/gemma4-q8-gpu0-vdr4default-nospec-realistic-gate-v2-20260627T165335Z/` | no speculation | 4 | 74.297 | **74.175** | **74.268** | **72.214** | **70.406** | 181.6 ms |
| `data/gemma4-q8-gpu0-vdr2-realistic-gate-v2-20260627T164358Z/` | draft-MTP `n=7`, `n_min=3`, `p_min=0.10` | 2 | 67.715 | 45.358 | 62.890 | 65.055 | 63.075 | 205.3 ms |
| `data/gemma4-q8-gpu0-vdr8-realistic-gate-v2-20260627T164804Z/` | draft-MTP `n=7`, `n_min=3`, `p_min=0.10` | 8 | 66.280 | 59.285 | 68.403 | 65.270 | 63.814 | 169.5 ms |
| `data/gemma4-q8-gpu1-vdr1-realistic-gate-v2-20260627T164358Z/` | draft-MTP `n=7`, `n_min=3`, `p_min=0.10` | 1 | 55.764 | 39.944 | 57.125 | 59.546 | 57.830 | 204.2 ms |

## Interpretation

- At this initial VDR-sweep point, the best row by the required primary metric
  was **75.614 tok/s** for default VDR4 draft-MTP.
- No-spec is only `1.317 tok/s` lower on median (`-1.7%`) and is better on p10,
  mean, full-512 median, and wall median. That makes no-spec the cleaner
  baseline for further realistic-suite work.
- VDR2 was the synthetic filled-long winner, but it does not transfer to the
  realistic cold suite. The earlier `176.216 tok/s` VDR2 row is diagnostic only.
- Draft-MTP acceptance is prompt-dependent on the realistic suite. Some prompts
  benefit enough to lift the median, while hard prompts drag p10/mean below the
  no-spec control.

## Current Decision

Use the VDR4 no-spec result as the target-side control and the VDR4 MTP result
as the current primary-metric record. Future work should:

1. screen target-side no-spec improvements on the realistic suite first;
2. only re-enable MTP when it beats no-spec under the same cold gate;
3. submit to LocalMaxxing only from realistic-suite payloads carrying
   `realisticSuiteGatePassed=true`, `realisticSuiteCachedTokensAllZero=true`,
   and `primaryMetricName=median_tok_s_1_100_after_ttft`.

## Active Follow-Up

Started a no-spec `UBATCH_SIZE` sweep immediately after this note:

- `UBATCH_SIZE=512` on GPU0;
- `UBATCH_SIZE=640` on GPU1;
- `UBATCH_SIZE=768` on GPU2;
- `UBATCH_SIZE=1024` on GPU3.

These runs use the same realistic final gate, not synthetic repeats.

## Follow-Up Result: No-Spec UBATCH Sweep

All four runs passed the realistic final gate and canary. None beat the
existing no-spec `UBATCH_SIZE=720` control.

| Run | UBATCH | median tok/s 1-100 after TTFT | p10 | mean | median full512 after TTFT | median wall full512 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `data/gemma4-q8-gpu0-vdr4default-nospec-ub512-realistic-gate-v2-20260627T165813Z/` | 512 | 73.688 | 73.647 | 73.685 | 71.664 | 69.894 |
| `data/gemma4-q8-gpu1-vdr4default-nospec-ub640-realistic-gate-v2-20260627T165814Z/` | 640 | 74.193 | 74.170 | 74.191 | 72.063 | 70.232 |
| `data/gemma4-q8-gpu2-vdr4default-nospec-ub768-realistic-gate-v2-20260627T165814Z/` | 768 | 73.562 | 73.504 | 73.553 | 71.567 | 69.743 |
| `data/gemma4-q8-gpu3-vdr4default-nospec-ub1024-realistic-gate-v2-20260627T165814Z/` | 1024 | 74.137 | 74.066 | 74.133 | 72.038 | 70.235 |

Decision: keep `UBATCH_SIZE=720` for the no-spec control. The best follow-up
(`UBATCH_SIZE=640`) is close but not a record.

Next action: tune draft-MTP thresholds on the same realistic suite. MTP still
has the best median, but the p10/mean penalties suggest prompt-dependent draft
overhead; lower `n_min` or smaller `n_max` may avoid hurting hard prompts.

## Follow-Up Result: MTP Threshold Sweep

All four runs below passed the chat canary and realistic final gate. These are
fresh-response cold-suite runs, not synthetic or warmed repeats:

- fixed suite `gemma4-26b-a4b-q8-b70-realistic-v1`;
- each prompt sent once;
- `cached_tokens=0` on every request;
- `--ctx-checkpoints 0`, `--cache-ram 0`, no n-gram/history acceleration;
- target/verifier unchanged: `UD-Q8_K_XL`, Q4_0 MTP draft verified by the Q8
  target.

| Run | MTP config | median tok/s 1-100 after TTFT | p10 | mean | median full512 after TTFT | median wall full512 | median TTFT |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `data/gemma4-q8-gpu3-vdr4default-mtp-n4-nmin2-p005-realistic-gate-v2-20260627T170154Z/` | `n_max=4`, `n_min=2`, `p_min=0.05` | **82.236** | **76.114** | **81.589** | **79.751** | **77.554** | 182.0 ms |
| `data/gemma4-q8-gpu2-vdr4default-mtp-n4-nmin2-p010-realistic-gate-v2-20260627T170153Z/` | `n_max=4`, `n_min=2`, `p_min=0.10` | 82.131 | 70.302 | 80.605 | 77.863 | 75.026 | 182.5 ms |
| `data/gemma4-q8-gpu1-vdr4default-mtp-n7-nmin3-p005-realistic-gate-v2-20260627T170153Z/` | `n_max=7`, `n_min=3`, `p_min=0.05` | 71.504 | 64.716 | 73.564 | 67.498 | 65.548 | 181.9 ms |
| `data/gemma4-q8-gpu0-vdr4default-mtp-n7-nmin2-p010-realistic-gate-v2-20260627T170153Z/` | `n_max=7`, `n_min=2`, `p_min=0.10` | 70.421 | 65.618 | 72.487 | 68.670 | 66.917 | 182.4 ms |

Interpretation:

- Smaller draft depth transfers to the realistic suite much better than the
  synthetic/high-repeat `n_max=7` lane. The current candidate is
  `n_max=4`, `n_min=2`, `p_min=0.05`.
- The new candidate is `+7.938 tok/s` over the no-spec control and `+6.622
  tok/s` over the previous realistic MTP record by the required primary metric.
- It is not promoted or submitted yet. Because this lane is noisy and earlier
  synthetic rows misled us, require an independent repeat under the same final
  gate before updating headline docs or LocalMaxxing.

Active repeat / local exploration launched after this note:

- repeat current candidate: `n_max=4`, `n_min=2`, `p_min=0.05`;
- nearby variants: `n_max=3`, `n_min=2`, `p_min=0.05`;
  `n_max=5`, `n_min=2`, `p_min=0.05`; and
  `n_max=4`, `n_min=2`, `p_min=0.03`.

## Follow-Up Result: MTP n3 / n4 Confirmation And Narrowing

All rows below passed the realistic final gate and chat canary with
`cached_tokens=0` on every fixed-suite prompt.

| Run | Config | median tok/s 1-100 after TTFT | p10 | mean | median full512 after TTFT | median wall full512 | median TTFT |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `data/gemma4-q8-gpu3-vdr4default-mtp-n3-nmin2-p0075-realistic-gate-v4-20260627T171157Z/` | `n_max=3`, `n_min=2`, `p_min=0.075`, UB720 | **86.474** | 77.100 | **84.866** | 82.052 | 78.419 | 182.1 ms |
| `data/gemma4-q8-gpu2-vdr4default-mtp-n3-nmin2-p005-ub1024-realistic-gate-v4-20260627T171157Z/` | `n_max=3`, `n_min=2`, `p_min=0.05`, UB1024 | 84.825 | 76.785 | 83.874 | 81.106 | 78.321 | 183.0 ms |
| `data/gemma4-q8-gpu0-vdr4default-mtp-n4-nmin2-p005-realistic-gate-repeat-v3-20260627T170813Z/` | `n_max=4`, `n_min=2`, `p_min=0.05`, UB720 repeat | 84.233 | 73.375 | 82.418 | 78.417 | 76.211 | 181.6 ms |
| `data/gemma4-q8-gpu1-vdr4default-mtp-n3-nmin2-p005-realistic-gate-v3-20260627T170813Z/` | `n_max=3`, `n_min=2`, `p_min=0.05`, UB720 | 83.376 | 74.817 | 83.085 | 80.644 | 78.303 | 183.2 ms |
| `data/gemma4-q8-gpu0-vdr4default-mtp-n3-nmin2-p005-ub640-realistic-gate-v4-20260627T171156Z/` | `n_max=3`, `n_min=2`, `p_min=0.05`, UB640 | 83.160 | 76.642 | 84.280 | 79.600 | 76.787 | 182.9 ms |
| `data/gemma4-q8-gpu1-vdr4default-mtp-n3-nmin2-p005-ub768-realistic-gate-v4-20260627T171157Z/` | `n_max=3`, `n_min=2`, `p_min=0.05`, UB768 | 82.324 | **77.303** | 83.587 | **82.164** | **79.804** | 181.3 ms |
| `data/gemma4-q8-gpu3-vdr4default-mtp-n4-nmin2-p003-realistic-gate-v3-20260627T170813Z/` | `n_max=4`, `n_min=2`, `p_min=0.03`, UB720 | 81.700 | 74.558 | 81.796 | 76.597 | 73.962 | 184.2 ms |
| `data/gemma4-q8-gpu2-vdr4default-mtp-n5-nmin2-p005-realistic-gate-v3-20260627T170813Z/` | `n_max=5`, `n_min=2`, `p_min=0.05`, UB720 | 76.232 | 69.013 | 78.547 | 74.844 | 72.776 | 183.4 ms |

Interpretation:

- The realistic-suite frontier moved from `75.614` -> `82.236` -> `86.474`
  tok/s once `n_max` was reduced from the synthetic-oriented `7` to `3-4` and
  thresholds were tuned for cold unique prompts.
- `n_max=3`, `n_min=2` is now the strongest family. The best current row is
  `p_min=0.075`, UB720; it is the valid cold-suite observed high so far, but
  not publishable until repeats confirm it.
- The lane is still noisy enough that an independent exact repeat is required
  before LocalMaxxing submission. Active v5 runs repeat `p_min=0.075`, test
  `p_min=0.10`, combine `p_min=0.075` with UB1024, and test `p_min=0.06`.

## Follow-Up Result: v5 Stability Check

All four v5 rows passed the realistic final gate and canary. The exact repeat
of the observed-high `86.474` config did **not** confirm the high; it returned
`81.733` on GPU0. Later same-GPU / stable-family repeats also did not
re-establish it, so keep `86.474` as an observed high only and use the
confirmed `n3/p0.05/UB1024` family for LocalMaxxing.

| Run | Config | median tok/s 1-100 after TTFT | p10 | mean | median full512 after TTFT | median wall full512 | median TTFT |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `data/gemma4-q8-gpu1-vdr4default-mtp-n3-nmin2-p010-ub720-realistic-gate-v5/` | `n_max=3`, `n_min=2`, `p_min=0.10`, UB720 | **82.242** | **76.825** | 83.154 | **81.350** | **78.407** | 183.1 ms |
| `data/gemma4-q8-gpu0-vdr4default-mtp-n3-nmin2-p0075-ub720-realistic-gate-repeat-v5/` | exact repeat of `p_min=0.075`, UB720 | 81.733 | 76.367 | **83.619** | 80.552 | 78.236 | 182.7 ms |
| `data/gemma4-q8-gpu2-vdr4default-mtp-n3-nmin2-p0075-ub1024-realistic-gate-v5/` | `n_max=3`, `n_min=2`, `p_min=0.075`, UB1024 | 80.510 | 74.219 | 82.789 | 79.173 | 76.485 | 183.9 ms |
| `data/gemma4-q8-gpu3-vdr4default-mtp-n3-nmin2-p006-ub720-realistic-gate-v5/` | `n_max=3`, `n_min=2`, `p_min=0.06`, UB720 | 78.553 | 73.588 | 80.648 | 78.635 | 76.502 | 182.2 ms |

Interpretation:

- The representative cold-suite frontier is currently a stable `82-84 tok/s`
  family, not the single `86.474 tok/s` high observation.
- `p_min=0.10` and `p_min=0.075` are both viable around UB720; `p_min=0.06`
  is a loss and `p_min=0.075` at UB1024 did not repeat the previous UB1024
  strength.
- Active v6 repeats now test same-GPU `p_min=0.075` UB720, repeat `p_min=0.05`
  UB1024, repeat `n_max=4/p_min=0.05` UB720, and repeat `p_min=0.05` UB768.

## Follow-Up Result: v6 Representative-Family Check

All four v6 rows passed the realistic final gate and chat canary. The
same-GPU repeat of the `86.474` observed-high row again did not confirm the
high (`82.898`), so `86.474` remains an observation, not a publishable
headline. The strongest representative family is now `n_max=3`, `n_min=2`,
`p_min=0.05`, with `UBATCH_SIZE=1024`.

| Run | Config | median tok/s 1-100 after TTFT | p10 | mean | median full512 after TTFT | median wall full512 | median TTFT |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `data/gemma4-q8-gpu0-vdr4default-mtp-n3-nmin2-p005-ub1024-realistic-gate-repeat-v6/` | `n_max=3`, `n_min=2`, `p_min=0.05`, UB1024 repeat | 83.836 | **78.159** | **85.057** | **82.614** | 79.562 | 182.7 ms |
| `data/gemma4-q8-gpu1-vdr4default-mtp-n4-nmin2-p005-ub720-realistic-gate-repeat-v6/` | `n_max=4`, `n_min=2`, `p_min=0.05`, UB720 repeat | **85.017** | 70.833 | 81.966 | 79.947 | 76.843 | 182.2 ms |
| `data/gemma4-q8-gpu2-vdr4default-mtp-n3-nmin2-p005-ub768-realistic-gate-repeat-v6/` | `n_max=3`, `n_min=2`, `p_min=0.05`, UB768 repeat | 81.812 | 72.966 | 81.871 | 79.380 | 77.212 | 181.7 ms |
| `data/gemma4-q8-gpu3-vdr4default-mtp-n3-nmin2-p0075-ub720-realistic-gate-samegpu-repeat-v6/` | same-GPU repeat of observed high: `n_max=3`, `n_min=2`, `p_min=0.075`, UB720 | 82.898 | 75.833 | 83.903 | 80.836 | 77.770 | 182.7 ms |

Interpretation:

- The best single observation remains `86.474`, but it is not representative.
- `n4/p0.05/UB720` can produce high medians (`84-85`), but p10 is unstable
  (`70.833` here), so it is not the best submission candidate.
- `n3/p0.05/UB1024` has two valid cold-suite rows (`84.825`, `83.836`) and the
  best current p10/mean/full512 balance. The later v7 repeat supplied the
  third confirmation and this family became the policy-compliant LocalMaxxing
  submission.

## Follow-Up Result: v7 Confirmation And Submission

All four v7 rows passed the realistic final gate and chat canary.

| Run | Config | median tok/s 1-100 after TTFT | p10 | mean | median full512 after TTFT | median wall full512 | median TTFT |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `data/gemma4-q8-gpu0-vdr4default-mtp-n3-nmin2-p005-ub1024-realistic-gate-repeat-v7/` | `n_max=3`, `n_min=2`, `p_min=0.05`, UB1024 repeat | **84.527** | **77.530** | **84.370** | **81.702** | **78.747** | **181.4 ms** |
| `data/gemma4-q8-gpu1-vdr4default-mtp-n3-nmin2-p005-ub896-realistic-gate-v7/` | `n_max=3`, `n_min=2`, `p_min=0.05`, UB896 | 82.483 | 75.208 | 82.898 | 80.138 | 77.924 | 182.3 ms |
| `data/gemma4-q8-gpu2-vdr4default-mtp-n3-nmin2-p0045-ub1024-realistic-gate-v7/` | `n_max=3`, `n_min=2`, `p_min=0.045`, UB1024 | 82.508 | 74.739 | 82.102 | 78.451 | 75.809 | 182.7 ms |
| `data/gemma4-q8-gpu3-vdr4default-mtp-n4-nmin2-p005-ub720-realistic-gate-repeat-v7/` | `n_max=4`, `n_min=2`, `p_min=0.05`, UB720 repeat | 84.378 | 71.104 | 82.642 | 78.096 | 75.987 | 182.0 ms |

Decision:

- `n3/p0.05/UB1024` is now confirmed by three valid cold-suite rows:
  `84.825`, `83.836`, and `84.527`. It is the representative strict-gate
  submission family.
- `n4/p0.05/UB720` still has high median but poor p10; do not promote it.
- `p_min=0.045` and UB896 were losses.
- Submitted the best confirmed-family row to LocalMaxxing with a strict
  realistic-suite payload:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-realistic-mtp-n3-nmin2-p005-ub1024-20260627.queue.json`.
  Approved ID: `cmqwn5wq703l3qr01ilxrw6p2`.

## Follow-Up Result: v8 Strict Repeat And Submission Update

All four v8 rows passed the realistic final gate and chat canary. The exact
representative-family repeat on GPU0 produced a new strict high and superseded
the earlier `86.474` one-off observation.

| Run | Config | median tok/s 1-100 after TTFT | p10 | mean | median full512 after TTFT | median wall full512 | median TTFT |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `data/gemma4-q8-gpu0-vdr4default-mtp-n3-nmin2-p005-ub1024-realistic-gate-repeat-v8/` | exact representative repeat: `n_max=3`, `n_min=2`, `p_min=0.05`, UB1024 | **87.611** | **77.547** | **86.634** | 80.640 | 77.865 | 182.4 ms |
| `data/gemma4-q8-gpu3-vdr4default-mtp-n3-nmin2-p005-ub1152-realistic-gate-v8/` | `n_max=3`, `n_min=2`, `p_min=0.05`, UB1152 | 83.943 | 74.847 | 84.691 | **81.395** | **78.343** | **181.4 ms** |
| `data/gemma4-q8-gpu1-vdr4default-mtp-n3-nmin2-p00525-ub1024-realistic-gate-v8/` | `n_max=3`, `n_min=2`, `p_min=0.0525`, UB1024 | 82.203 | 75.261 | 83.847 | 79.394 | 77.128 | 182.6 ms |
| `data/gemma4-q8-gpu2-vdr4default-mtp-n3-nmin2-p0055-ub1024-realistic-gate-v8/` | `n_max=3`, `n_min=2`, `p_min=0.055`, UB1024 | 80.395 | 75.190 | 81.445 | 79.173 | 76.926 | 181.7 ms |

Decision:

- `n3/p0.05/UB1024` remains the best representative strict-gate family and is
  now also the best single strict observation: `84.825`, `83.836`, `84.527`,
  and `87.611 tok/s`.
- Slightly higher `p_min` values (`0.0525`, `0.055`) were losses. UB1152
  improved full-512/wall balance slightly but did not beat the primary
  median-100 metric.
- Submitted the v8 strict high to LocalMaxxing with the realistic-suite payload:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-realistic-mtp-n3-nmin2-p005-ub1024-v8-20260627.queue.json`.
  Approved ID: `cmqwnl2ag03lgqr01ch5bxknq`.

## Follow-Up Result: v9 Variants Did Not Beat v8

All four v9 rows passed the realistic final gate and chat canary. None beat the
v8 strict high (`87.611 tok/s`), so no LocalMaxxing submission was made.

| Run | Config | median tok/s 1-100 after TTFT | p10 | mean | median full512 after TTFT | median wall full512 | median TTFT |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `data/gemma4-q8-gpu0-vdr4default-mtp-n3-nmin2-p005-ub1024-realistic-gate-repeat-v9/` | exact representative repeat: `n_max=3`, `n_min=2`, `p_min=0.05`, UB1024 | **85.368** | 74.989 | **84.481** | 81.615 | 78.587 | **181.2 ms** |
| `data/gemma4-q8-gpu2-vdr4default-mtp-n3-nmin2-p005-ub1088-realistic-gate-v9/` | `n_max=3`, `n_min=2`, `p_min=0.05`, UB1088 | 85.331 | 75.052 | 83.922 | 81.053 | 77.765 | 182.4 ms |
| `data/gemma4-q8-gpu1-vdr4default-mtp-n3-nmin2-p00475-ub1024-realistic-gate-v9/` | `n_max=3`, `n_min=2`, `p_min=0.0475`, UB1024 | 84.682 | **77.675** | 84.063 | **82.099** | **79.255** | 183.0 ms |
| `data/gemma4-q8-gpu3-vdr4default-mtp-n4-nmin2-p005-ub1024-realistic-gate-v9/` | `n_max=4`, `n_min=2`, `p_min=0.05`, UB1024 | 81.901 | 75.261 | 83.436 | 77.307 | 75.251 | 182.7 ms |

Interpretation:

- The v8 `87.611` row remains the strict high. A same-family v9 repeat at
  `85.368` confirms the family is strong but variable.
- Lowering `p_min` slightly to `0.0475` improved p10/full512/wall balance but
  lost on the primary median-100 metric.
- UB1088 did not beat UB1024 on the primary metric.
- `n_max=4` with UB1024 is a clear loss on this fixed cold suite; the earlier
  n4 medians were not enough to overcome worse prompt-level balance.

Next action: stop spending sweeps on tiny `p_min`/UBATCH changes unless tied to
a new source/runtime mechanism. Try runtime overhead controls (target threads,
draft threads/batch, or verifier-side code changes) under the same strict gate.

## Follow-Up Result: v10 Runtime Thread Controls

All four v10 rows passed the realistic final gate and chat canary. None beat
the v8 strict high (`87.611 tok/s`), but target `THREADS=6` became a useful
near-miss and improved p10.

| Run | Config | median tok/s 1-100 after TTFT | p10 | mean | median full512 after TTFT | median wall full512 | median TTFT |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `data/gemma4-q8-gpu0-vdr4default-mtp-n3-nmin2-p005-ub1024-th6-realistic-gate-v10/` | `n3/p0.05/UB1024`, target `THREADS=6`, draft threads 32/32 | **87.122** | **78.538** | **85.576** | **80.920** | 77.848 | **181.3 ms** |
| `data/gemma4-q8-gpu2-vdr4default-mtp-n3-nmin2-p005-ub1024-dth16-realistic-gate-v10/` | `n3/p0.05/UB1024`, target `THREADS=8`, draft threads 16/16 | 86.386 | 75.136 | 84.094 | 80.004 | 77.757 | 183.8 ms |
| `data/gemma4-q8-gpu3-vdr4default-mtp-n3-nmin2-p005-ub1024-dth64-realistic-gate-v10/` | `n3/p0.05/UB1024`, target `THREADS=8`, draft threads 64/64 | 83.915 | 75.383 | 84.069 | 80.861 | **78.618** | 182.9 ms |
| `data/gemma4-q8-gpu1-vdr4default-mtp-n3-nmin2-p005-ub1024-th10-realistic-gate-v10/` | `n3/p0.05/UB1024`, target `THREADS=10`, draft threads 32/32 | 81.694 | 75.977 | 83.302 | 79.673 | 77.535 | 182.4 ms |

Interpretation:

- `THREADS=6` is worth a focused follow-up: it nearly matched the v8 strict high
  while improving p10, suggesting lower CPU-thread pressure can reduce
  prompt-level variance.
- Target `THREADS=10` is a loss.
- Draft helper threads 16/16 and 64/64 did not beat the current recipe. Keep
  32/32 unless paired with the `THREADS=6` follow-up.

## Follow-Up Result: v11 THREADS=6 Follow-Up Did Not Repeat

All four v11 rows passed the realistic final gate and chat canary. The
`THREADS=6` near-miss from v10 did not repeat and no row beat the v8 strict
high (`87.611 tok/s`).

| Run | Config | median tok/s 1-100 after TTFT | p10 | mean | median full512 after TTFT | median wall full512 | median TTFT |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `data/gemma4-q8-gpu2-vdr4default-mtp-n3-nmin2-p005-ub1088-th6-realistic-gate-v11/` | `THREADS=6`, `n3/p0.05`, UB1088, draft threads 32/32 | **85.634** | 73.415 | **83.676** | 78.621 | 76.408 | **181.7 ms** |
| `data/gemma4-q8-gpu3-vdr4default-mtp-n3-nmin2-p005-ub1024-th6-dth16-realistic-gate-v11/` | `THREADS=6`, `n3/p0.05`, UB1024, draft threads 16/16 | 81.905 | **77.069** | 83.112 | 80.617 | 78.083 | 182.8 ms |
| `data/gemma4-q8-gpu0-vdr4default-mtp-n3-nmin2-p005-ub1024-th6-repeat-realistic-gate-v11/` | `THREADS=6`, exact v10 near-miss repeat | 81.284 | 74.185 | 82.010 | 79.908 | 77.658 | 181.7 ms |
| `data/gemma4-q8-gpu1-vdr4default-mtp-n3-nmin2-p00475-ub1024-th6-realistic-gate-v11/` | `THREADS=6`, `n3/p0.0475`, UB1024, draft threads 32/32 | 80.611 | 75.728 | 82.349 | **81.070** | **78.178** | 182.0 ms |

Interpretation:

- Treat v10 `THREADS=6` as a variance/near-miss signal, not a stable
  improvement.
- More launcher tuning around the current MTP stack is unlikely to reach the
  `>150 tok/s` target under the realistic cold suite. The confirmed path for
  material progress remains source-level verifier-side work or a different
  fresh-valid speculation engine.
