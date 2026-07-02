# Gemma 4 26B Q8 KQ Register Broadcast Full512 Short-Decode A/B

Date: 2026-07-02

Status: closed no-win for short-decode headline. No LocalMaxxing submission.

## Question

The default-off global FlashAttention KQ register/broadcast path is a validated
service/prefill micro-win for long-context Gemma shapes. A previous
short-decode guard used only `MAX_TOKENS=256`, so this follow-up tested the
same path under the full `MAX_TOKENS=512` fixed realistic cold-suite gate.

This isolates the KQ register/broadcast flag:

- control: `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`
- candidate: control plus `GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1`

All lanes used the short-record UB1024 shape, Q8 target/verifier, Q4_0 MTP
draft, one B70 per replica, fixed cold prompts, and `cached_tokens=0`.

## Harness Changes

Added/updated reproducibility plumbing:

- `scripts/run-gemma4-26b-first-baseline.sh` now passes through and records
  `GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST`;
- `scripts/run-gemma4-26b-llamacpp-replica.sh` logs
  `GGML_SYCL_FATTN_DV512_GQA_NCOLS2` and
  `GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST`;
- `repro/gemma4-26b-a4b-q8-b70/run-vdr2-short-decode-guard.sh` includes those
  flags in its aggregate rows;
- `repro/gemma4-26b-a4b-q8-b70/run-vdr2-kqregbcast-short-full512-ab.sh`
  reproduces the full512 two-wave control/candidate crossover and paired
  per-prompt analysis.

## Evidence

Run stamp:

```text
20260702T112211Z-kqregbcast-short-full512-ab
```

Paired analysis:

- `data/gemma4-kqregbcast-short-full512-ab-20260702T112211Z-kqregbcast-short-full512-ab.json`
- `data/gemma4-kqregbcast-short-full512-ab-20260702T112211Z-kqregbcast-short-full512-ab.md`

Aggregate guard summaries:

- `data/gemma4-short-decode-guard-20260702T112211Z-kqregbcast-short-full512-ab-waveA-control.json`
- `data/gemma4-short-decode-guard-20260702T112211Z-kqregbcast-short-full512-ab-waveA-candidate.json`
- `data/gemma4-short-decode-guard-20260702T112211Z-kqregbcast-short-full512-ab-waveB-control.json`
- `data/gemma4-short-decode-guard-20260702T112211Z-kqregbcast-short-full512-ab-waveB-candidate.json`

Per-lane result directories:

- `data/gemma4-q8-gpu0-shortguard-control-gpu0-ctx32768-o512-20260702T112211Z-kqregbcast-short-full512-ab-waveA-control/`
- `data/gemma4-q8-gpu1-shortguard-kqregbcast-gpu1-ctx32768-o512-20260702T112211Z-kqregbcast-short-full512-ab-waveA-candidate/`
- `data/gemma4-q8-gpu2-shortguard-control-gpu2-ctx32768-o512-20260702T112211Z-kqregbcast-short-full512-ab-waveA-control/`
- `data/gemma4-q8-gpu3-shortguard-kqregbcast-gpu3-ctx32768-o512-20260702T112211Z-kqregbcast-short-full512-ab-waveA-candidate/`
- `data/gemma4-q8-gpu1-shortguard-control-gpu1-ctx32768-o512-20260702T112211Z-kqregbcast-short-full512-ab-waveB-control/`
- `data/gemma4-q8-gpu3-shortguard-control-gpu3-ctx32768-o512-20260702T112211Z-kqregbcast-short-full512-ab-waveB-control/`
- `data/gemma4-q8-gpu0-shortguard-kqregbcast-gpu0-ctx32768-o512-20260702T112211Z-kqregbcast-short-full512-ab-waveB-candidate/`
- `data/gemma4-q8-gpu2-shortguard-kqregbcast-gpu2-ctx32768-o512-20260702T112211Z-kqregbcast-short-full512-ab-waveB-candidate/`

All eight lanes passed:

- canary gate;
- fixed realistic final gate;
- `cached_tokens=0` for every prompt.

## Result

Run medians for primary metric, generated tokens 1-100 after TTFT:

| group | medians tok/s |
| --- | --- |
| control | `117.584`, `124.161`, `115.228`, `116.737` |
| candidate | `116.760`, `117.590`, `124.444`, `115.657` |

Paired prompt bootstrap:

```text
median paired ratio 95% CI: -2.666% / -0.040% / +3.119%
decision: no_win
```

The candidate average was effectively tied with control but below the current
strict cold-suite record (`124.97714084813418 tok/s`). Because the confidence
interval crosses negative and the central estimate is slightly negative, this
does not qualify for promotion.

## Decision

Keep `GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1` as an optional
service/prefill flag only. Do not add it to the short-decode record recipe, do
not submit it to LocalMaxxing, and do not retest this exact full512 short
variant unless the underlying FlashAttention kernel changes materially.

## Reproduction

```bash
cd /home/steve/llm-optimizations
STAMP=YYYYMMDDTHHMMSSZ-kqregbcast-short-full512-ab \
BASE_PORT=19020 \
MAX_TOKENS=512 \
CANARY_REPEATS=32 \
REALISTIC_METRIC_TOKENS=100 \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-kqregbcast-short-full512-ab.sh
```
