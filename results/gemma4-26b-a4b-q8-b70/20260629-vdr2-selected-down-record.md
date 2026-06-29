# 2026-06-29 VDR2 Selected-Down Record

Status: **valid promoted fresh-response record** for the Gemma 4 26B A4B
`UD-Q8_K_XL` target/verifier lane on one Intel Arc Pro B70. LocalMaxxing:
`cmqyo0jyt08ippk01vhiobdnm`.

## Result

Primary metric: median generated-token throughput for tokens 1-100 after TTFT
across the fixed realistic cold prompt suite.

| GPU | Summary | Gate | Canary | Median 1-100 | p10 1-100 | Mean 1-100 | Full512 after TTFT | Wall full512 | TTFT median |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | `data/gemma4-q8-gpu0-vdr2-selecteddown-reordervdr2-full512-20260629A/summary.json` | pass | 512/512 | 113.47081786263712 | 102.18997056423927 | 114.81272787275348 | 106.59058008222027 | 102.66882811900274 | 179.7679010196589 ms |
| 1 | `data/gemma4-q8-gpu1-vdr2-selecteddown-reordervdr2-full512-20260629B/summary.json` | pass | 512/512 | **115.72789384447941** | 101.44940713540609 | 113.15845262438565 | 104.6018645861352 | 100.22769693993533 | 181.347543024458 ms |
| 2 | `data/gemma4-q8-gpu2-vdr2-selecteddown-reordervdr2-full512-20260629C/summary.json` | pass | 512/512 | 113.81540554086772 | 104.38170198227209 | 113.37437257944545 | 105.36127337885975 | 101.3641176342222 | 180.47102249693125 ms |
| 3 | `data/gemma4-q8-gpu3-vdr2-selecteddown-reordervdr2-full512-20260629D/summary.json` | pass | 512/512 | 114.8109417270852 | 104.63732760747995 | 115.24650663810468 | 105.60976692576831 | 101.70051321789589 | 180.81690149847418 ms |

Promotion basis: GPU1 has the highest passing full512 median. The four
independent one-GPU confirmations all passed the same strict gate, making this
a reliable improvement over the prior `98.34046474459183 tok/s` record.

## Validity

- Fixed suite: `repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json`.
- Each prompt sent once as a cold response.
- `cached_tokens=0` for every request in every full512 confirmation.
- No prompt/KV cache reuse, context checkpoints, response reuse,
  n-gram/history acceleration, or warmed repeated prompts.
- Target model and verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`.
- Draft model: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`; accepted speculative
  tokens are verified by the Q8 target.
- `realistic_final_gate.passed=true` and `headline_eligible_for_gemma_q8=true`
  in every promoted summary.

## Winning Change

The win is a source-level verifier MoE reduction: a VDR2-reordered Q8
implementation of `GGML_OP_MOE_SELECTED_DOWN_WEIGHTED_SUM`.

Why it mattered:

- The previous raw-layout fused-down path rejected reordered Q8 expert weights,
  so the current VDR2 record stack could not use it.
- The new path quantizes/reorders the selected hidden rows and computes the
  selected down projection plus weighted sum against VDR2 reordered Q8 weights.
- This removes separate selected-down materialization and the following
  weighted-sum pass in the strict record stack.

Enable flag:

```text
LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1
```

Required surrounding identity is still the prior strict record stack:
`GGML_SYCL_REORDER_Q8_0_VDR_MMVQ=2` build, reordered-Q8 VDR2,
`LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
`LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`, `n_max=3`, `n_min=2`,
`p_min=0.0475`, `UBATCH_SIZE=1024`, f16 KV, graph enabled, VMM disabled,
and `--ctx-checkpoints 0`.

## Artifacts

- Source patch:
  `patches/gemma4-26b-a4b-q8-b70/20260629-vdr2-selected-down-reordervdr2-source.patch`
  (`sha256=9db3ac4286e3842ece2eebd07060ac73a0e0c548cb15d17333406701576d52c8`).
- Harness patch:
  `patches/gemma4-26b-a4b-q8-b70/20260629-vdr2-selected-down-reordervdr2-harness.patch`
  (`sha256=c36baad905271f2350182372ca62ce6614bb07b87425c28318fb6dca5042cc0d`).
- Pre-experiment source snapshot:
  `patches/gemma4-26b-a4b-q8-b70/20260629-pre-vdr2-selected-down-source-snapshot.patch`.
- Repro script:
  `repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh`.

## Next Work

The reliable `>100` barrier is now broken. The next optimization should keep
this exact recipe as the baseline and only pursue source-level verifier cost
work. Best next targets:

- exact LM-head candidate-vs-max or compact argmax;
- head-only bonus token path that preserves the current bonus pipeline;
- row-adaptive verifier output rows;
- verifier MoE boundary/kernel reduction beyond the selected-down fusion.

Keep prompt processing and long-context optimization separate from the short
decode record lane, and rerun this short suite afterward to prove no regression.
