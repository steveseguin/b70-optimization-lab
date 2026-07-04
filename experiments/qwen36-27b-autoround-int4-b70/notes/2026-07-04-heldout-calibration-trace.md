# 2026-07-04: Held-out verifier trace calibration suite

## Context

The current Qwen27 record remains
`65.27648650325429 tok/s` for `webhie/Qwen3.6-27B-int4-AutoRound` with runtime
INT8 LM-head BF16 scales, MTP3, cg8, one B70, strict cold Qwen realistic suite,
and `cached_tokens=0`. LocalMaxxing already approved that row as
`cmr5iu3gk00bfq901nidgcana`.

Recent source/kernel work closed the quick LM-head lanes as no-win:

- exact top-ID sampler plumbing is valid but flat because `get_top_tokens()`
  still computes dense local logits;
- draft local-argmax reduction is flat for the same reason;
- standalone native compact INT8 LM-head top-1 is exact but slower than dense
  oneDNN plus argmax;
- MTP4/MTP5 and scheduler-only adaptive depth reduce throughput.

So the non-kernel lane is accepted-token improvement / drafter calibration,
with exact target verification and no final-suite leakage.

## Tooling added

`scripts/bench-openai-realistic-suite.py` now records:

- deterministic `X-Request-Id` per prompt;
- response `X-Request-Id` and response ID;
- absolute request start, first-token, and end epoch timestamps.

This does not change benchmark semantics. It only makes single-concurrency
diagnostic traces attributable to prompt rows.

`scripts/run-qwen36-27b-autoround-vllm-candidate.sh` now accepts these defaults:

- `SUITE`;
- `BENCH_MAX_TOKENS`;
- `BENCH_METRIC_TOKENS`;
- `BENCH_REQUEST_EXTRA_JSON`.

Defaults preserve the promoted strict Qwen suite behavior.

`scripts/summarize-qwen27-spec-verify-trace.py` now joins compact verifier
trace rows to benchmark prompt windows when the paired result JSON contains
absolute request timestamps. Old traces remain supported; their per-prompt
section is simply empty.

Added held-out diagnostic suite:

```text
experiments/qwen36-27b-autoround-int4-b70/calibration-suite-v1.json
```

This suite is **diagnostic-only** and must not be used for LocalMaxxing
headline claims.

## Calibration run

Command shape:

```bash
cd /home/steve/llm-optimizations
LABEL=qwen27-webhie-int8lmhead-bf16scale-calibration-verifytrace-20260704A \
GPU_INDEX=1 PORT=19417 \
MODEL_DIR=/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e \
VLLM_XPU_LM_HEAD_INT8=1 \
VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16 \
SUITE=experiments/qwen36-27b-autoround-int4-b70/calibration-suite-v1.json \
BENCH_MAX_TOKENS=128 BENCH_METRIC_TOKENS=100 \
VLLM_XPU_SPEC_DECODE_VERIFY_TRACE_FILE=/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-int8lmhead-bf16scale-calibration-verifytrace-20260704A/verify-trace.jsonl \
VLLM_XPU_SPEC_DECODE_VERIFY_TRACE_MAX_LINES=12000 \
bash scripts/run-qwen36-27b-autoround-vllm-candidate.sh
```

Result:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-calibration-verifytrace-20260704A-20260704T071847Z.json
```

Trace and summaries:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-calibration-verifytrace-20260704A-verify-trace.jsonl
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-calibration-verifytrace-20260704A-verify-summary.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-int8lmhead-bf16scale-calibration-verifytrace-20260704A-verify-summary.md
```

Validity classification:

- diagnostic-only, not a record attempt;
- 24 held-out prompts, each prompt once;
- `cached_tokens=0` for every request;
- median `63.11820703948129 tok/s`, p10 `57.15554850685666`, mean
  `63.14942796082557`, median TTFT `618.466 ms`.

Verifier trace totals:

- `1157` verifier steps;
- `3471` draft tokens;
- `1951` prefix-accepted tokens;
- prefix acceptance fraction `0.5620858542206857`;
- mean target-verified tokens/step `2.686257562662057`;
- full-accept rate `0.3500432152117545`;
- per-position target-top1 match:
  `p0=0.7951598962834918`, `p1=0.6698357821953328`,
  `p2=0.5859982713915298`;
- accepted histogram `{0: 237, 1: 294, 2: 221, 3: 405}`.

Prompt-level acceptance correlates with throughput: Pearson
`acceptance_vs_speed ~= 0.696` for this diagnostic suite. Lowest-acceptance
prompts include `customer-root-cause` (`2.214` target tokens/step) and
`architecture-summary` (`2.346`); best include `cache-bug` (`3.047`) and
`variance-method` (`2.977`).

## Interpretation

The per-prompt attribution confirms the expected direction: improving drafter
match rate is meaningful, but it is not a magic `100 tok/s` path by itself.
The held-out suite averaged `2.686` target-verified tokens/step; the earlier
final-suite trace was about `2.795`. Even perfect MTP3 acceptance at the
current step cost would land around the low `90 tok/s` range, not reliably over
`100`.

Next credible work:

1. use the held-out trace flow to build a larger calibration corpus if pursuing
   target-matched drafter training/fine-tuning;
2. keep final-suite prompts isolated from tuning;
3. continue treating producer-side LM-head top-ID work as the kernel route, but
   do not repeat already-closed sampler/local-argmax paths until the producer
   changes.

No LocalMaxxing submission.
