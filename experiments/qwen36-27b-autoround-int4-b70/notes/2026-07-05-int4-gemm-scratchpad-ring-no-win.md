# 2026-07-05 - INT4 W4A16 GEMM Scratchpad Ring No-Win

## Scope

This was a concrete low-level Qwen27 attempt after the DFlash feasibility lane
closed: avoid per-call oneDNN scratchpad tensor allocation in the target/core
W4A16 INT4 matmul path.

The change added a default-off scratchpad ring cache to
`csrc/xpu/onednn/int4_gemm_w4a16.h`, gated by
`VLLM_XPU_INT4_GEMM_SCRATCHPAD_RING_SIZE`. Ring size `0` preserves the original
per-call allocation path; `1..16` enables the cache.

Patch snapshot:

- `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-int4-gemm-scratchpad-ring-no-win-20260705.patch`

## Smoke

Functional smoke passed on one B70 for ring `0` and ring `4`:

- repeated outputs were deterministic (`max_diff_repeat=0.0`);
- output matched the existing W4A16 reference tolerance (`max_diff_ref=0.0625`
  on the small smoke shape).

## Strict Fresh Results

All completed rows used the strict Qwen27 realistic suite:

- fixed `qwen36-27b-autoround-int4-b70-realistic-v1`;
- one cold response per prompt;
- `cached_tokens=0` for every request;
- no prompt/KV/context/response/history reuse;
- target-verified `qwen3_next_mtp` with `num_speculative_tokens=3`;
- `webhie/Qwen3.6-27B-int4-AutoRound`;
- runtime INT8 LM-head with BF16 scales.

| Label | Ring | GPU | Status | Median tok/s 1-100 after TTFT | p10 | Mean | Notes |
| --- | ---: | ---: | --- | ---: | ---: | ---: | --- |
| `qwen27-int4-scratchpad-ring0-control-20260705` | 0 | 0 | strict-valid | `66.05153909520094` | `58.24828834397495` | `65.00747022150018` | same-binary control |
| `qwen27-int4-scratchpad-ring8-20260705` | 8 | 3 | strict-valid | `65.8598988234668` | `58.13386679740853` | `64.617547044268` | no speedup |
| `qwen27-int4-scratchpad-ring4-standalone-gpu0-20260705` | 4 | 0 | strict-valid | `65.41930657531518` | `58.400372776655836` | `64.98815184914422` | standalone check on same GPU as control |
| `qwen27-int4-scratchpad-ring2-20260705` | 2 | 1 | timeout | n/a | n/a | n/a | did not reach `/v1/models` by readiness timeout; stuck during drafter load |
| `qwen27-int4-scratchpad-ring4-20260705` | 4 | 2 | timeout | n/a | n/a | n/a | did not reach `/v1/models` by readiness timeout; stuck during drafter load |

Primary artifacts:

- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int4-scratchpad-ring0-control-20260705-20260705T024028Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int4-scratchpad-ring8-20260705-20260705T024028Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-int4-scratchpad-ring4-standalone-gpu0-20260705-20260705T025258Z.json`
- timed-out run dirs under
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-int4-scratchpad-ring{2,4}-20260705-20260705T024028Z`

## Decision

No promotion. The cache is exact on the smoke, but endpoint throughput did not
improve. Ring `8` was slightly below the same-window control, and ring `4`
standalone on GPU0 was also below control. The startup timeouts on GPUs 1/2 are
not treated as proof against the patch, but they also provide no positive
evidence.

The active source should not keep this patch. Preserve it only as a failed
experiment snapshot.

## Next

Move back to the higher-upside path identified by timing and source audit:
producer-side exact top-ID LM-head work. The current dirty stack already has a
target verifier consumer (`VLLM_XPU_SPEC_GREEDY_TOP_IDS`), but
`get_top_tokens()` still materializes dense `[rows, vocab]` logits first. The
next useful source change must reduce or replace dense LM-head production for
both target verification and draft greedy top-ID generation, or improve
accepted tokens per expensive verifier step without warmed/history effects.
