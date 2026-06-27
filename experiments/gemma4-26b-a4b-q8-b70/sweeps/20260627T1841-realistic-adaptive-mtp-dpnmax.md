# 2026-06-27 Realistic Adaptive MTP Depth Cap

Status: negative / default-off patch preserved. Do not submit to LocalMaxxing.

## Promotion Rule

These runs used the realistic final gate, not the older synthetic filled-long
diagnostic gate:

- fixed `gemma4-26b-a4b-q8-b70-realistic-v1` prompt suite;
- each prompt run once as a cold first response;
- `cached_tokens=0` for every request;
- no prompt/KV/context/response reuse, no n-gram/history acceleration, no
  warmed repeated prompts;
- primary metric is median generated-token throughput for tokens 1-100 after
  TTFT across the suite.

Current strict one-B70 Q8 record remains:

```text
data/gemma4-q8-gpu0-vdr4default-mtp-n3-nmin2-p005-ub1024-realistic-gate-repeat-v8/summary.json
median100 = 87.61145306230438 tok/s
LocalMaxxing = cmqwnl2ag03lgqr01ch5bxknq
```

## Idea Tested

The hypothesis was that some realistic prompts have low MTP acceptance early in
the response. If the server detects a low acceptance EMA, it can cap MTP draft
depth to reduce wasted assistant/verifier work while keeping speculation on
prompts that accept well.

Two source changes were tested:

1. Server-side default-off adaptive state in `tools/server/server-context.cpp`.
   The gate is `LLAMA_SPEC_ADAPTIVE_MTP=1`, with knobs for warmup, low/high EMA
   thresholds, and the low `n_max` cap.
2. A follow-up fix in `common/speculative.cpp` so MTP draft generation itself
   honors per-request `dp.n_max`, not just later truncation. Without this,
   adaptive cap only reduced target-side verification shape and still
   over-generated draft work.

Patch snapshot:

```text
patches/gemma4-26b-a4b-q8-b70/20260627T1856-llamacpp-adaptive-mtp-dpnmax-negative.patch
sha256 08132eefce96f341ec1e1c498d32963ba72c92798d9698bdfd84c6ef75c783af
```

## v13 Matrix: Before MTP `dp.n_max` Generation Fix

| Label | Median100 | p10 | Mean | Full512 | Wall512 | TTFT ms | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `gpu0-strict-rebuild-control-v13` | 83.3848 | 78.3399 | 83.5717 | 80.6436 | 77.6320 | 181.276 | pass, no record |
| `gpu1-strict-adapt-n3-low050-v13` | 81.1877 | 74.6112 | 81.7522 | 80.2830 | 77.1852 | 182.199 | pass, loss |
| `gpu2-strict-adapt-n4-cap3-v13` | 81.1980 | 76.5701 | 82.3372 | 76.7204 | 74.1464 | 182.715 | pass, loss |
| `gpu3-strict-adapt-n7-cap3-v13` | 74.4960 | 67.9337 | 76.5610 | 71.3569 | 69.5632 | 181.974 | pass, large loss |

All four runs passed the realistic gate and had `cached_tokens=0`, but none
approached the `87.611` record.

## v14 Matrix: After MTP `dp.n_max` Generation Fix

| Label | Median100 | p10 | Mean | Full512 | Wall512 | TTFT ms | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `gpu0-strict-dpnmax-control-n3-v14` | 81.2834 | 74.6065 | 82.6125 | 80.0781 | 77.8709 | 181.690 | pass, no record |
| `gpu1-strict-dpnmax-adapt-n3-low050-v14` | 83.3421 | 75.0117 | 83.0816 | 77.5562 | 75.4725 | 183.988 | pass, best adaptive, no record |
| `gpu2-strict-dpnmax-adapt-n4-cap3-v14` | 81.0393 | 73.6252 | 81.0775 | 77.9003 | 75.0771 | 182.093 | pass, loss |
| `gpu3-strict-dpnmax-adapt-n5-cap3-v14` | 79.9259 | 69.6250 | 79.7721 | 76.5479 | 74.3719 | 181.431 | pass, loss |

The `dp.n_max` fix improved the specific `n3` adaptive lane relative to v13,
but the best row was still `83.3421 tok/s`, more than `4 tok/s` below the
current strict record.

## Conclusion

Adaptive MTP depth cap is not the next Gemma 26B Q8 speed lever. It is useful
as an audit artifact and possible future ingredient, but should remain
default-off and should not be promoted.

Likely reasons:

- The strict suite is only 12 cold prompts, so prompt-to-prompt variance is
  high and early EMA decisions can overreact.
- Lower draft depth reduces wasted work on low-acceptance prompts but also
  forfeits high-acceptance early tokens where the current `n_max=3` recipe wins.
- The current bottleneck is still target/verifier work, especially Gemma4 MoE
  and LM-head cost, not the small amount of extra draft work after the direct
  argmax unroll patches.

Next work should target a structural verifier-side reduction or a fresh-valid
speculation design, not more adaptive-threshold sweeps.
