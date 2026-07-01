# 2026-07-01 Record reproduction after workspace consolidation

## Purpose

Confirm the current Gemma 4 26B A4B Q8 short-decode recipe after the workspace
consolidation and source rebuild. This is a baseline/variance check, not a new
record attempt.

The prior valid headline record remains:

- `124.97714084813418 tok/s` median generated-token throughput for tokens
  1-100 after TTFT;
- summary:
  `data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`;
- LocalMaxxing ID: `cmr1u77na01k2ld01kalwzs1e`.

## Command

```bash
cd /home/steve/llm-optimizations
source /opt/intel/oneapi/setvars.sh --force
STAMP=20260701Trecord-repro-canon1 \
CTX_SIZE=32768 FLASH_ATTN=on GGML_SYCL_ENABLE_VMM=1 \
MAX_TOKENS=512 CANARY_REPEATS=128 BASE_PORT=18560 READINESS_TIMEOUT_S=900 \
LANE_SPECS="0:1024:1024:repro-a 1:1024:1024:repro-b 2:1024:1024:repro-c 3:1024:1024:repro-d" \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-short-decode-guard.sh
```

## Artifacts

- Summary: `data/gemma4-short-decode-guard-20260701Trecord-repro-canon1.json`

All four lanes passed:

- fixed realistic cold suite;
- `cached_tokens=0`;
- full 512-token output run;
- `512/512` canary rows per lane.

## Results

| GPU | Median tok/s 1-100 | p10 | Mean | Full512 tok/s | Wall full512 tok/s | TTFT ms |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 117.026 | 108.329 | 117.814 | 109.588 | 105.655 | 178.337 |
| 1 | 114.584 | 100.744 | 115.145 | 108.992 | 104.561 | 178.778 |
| 2 | 120.155 | 106.178 | 119.057 | 110.998 | 106.588 | 179.335 |
| 3 | 113.383 | 105.183 | 114.052 | 106.972 | 103.109 | 179.877 |

Group average median 1-100: `116.28698939080547 tok/s`.

## Decision

Valid reproduction of the recipe, but not a reproduction of the `124.977`
outlier. Do not submit to LocalMaxxing and do not treat this as a record. Use
this as the post-consolidation variance baseline for future source patches:
a small patch must beat this same-window range clearly before promotion.

This result reinforces the existing reliability guidance: the 124.977 record is
valid under the fixed gate, but the lane has high variance. Future micro-wins
need paired same-window A/B or a stronger no-spec/isolated diagnostic before
claiming sub-percent improvements.
