# Qwen3.6 INT8 N-Gram Scheduler Guard Rejected

Date: 2026-06-10

## Context

The previous n-gram CG128 candidate improved single-request speed and passed one
frontdoor quality suite, but failed c2 reliability. The failing scheduler step
mixed:

- one new 515-token prefill request
- one cached request with scheduled speculative decode tokens

That hit the XPU FLA GDN chunk prefill path and crashed with Intel Triton
`PassManager::run failed`.

## Guard Tested

I added an opt-in scheduler guard:

- env: `VLLM_XPU_DISABLE_SPEC_DECODE_WHEN_WAITING=1`
- behavior: when a running request has speculative tokens and there is waiting
  work, schedule only the target non-spec token and regenerate speculative
  tokens after waiting work drains

Patch artifact:

- `patches/vllm-qwen36-ngram-scheduler-waiting-prefill-guard-rejected-20260610.patch`

This was intentionally a scheduler guard, not a model or quantization change, so
it should not lower target-model quality in principle.

## Startup

The guarded candidate started successfully:

- model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- TP4, 32K context, Quark W8A8 INT8
- n-gram config: `num_speculative_tokens=5`, lookup min/max `2/5`
- graph config: PIECEWISE, max capture size `128`
- graph captures: 19
- startup was slower because this used a fresh compile/cache root
- available KV cache memory: `20.67 GiB`
- maximum 32K-request concurrency reported: `50.12x`

## Reliability

The guard fixed the immediate c2 crash:

- artifact: `data/qwen36-quark-int8-tp4-ngram5-cg128-gdnmixed-schedguard-c2-20260610.json`
- c2 completed successfully
- aggregate output tok/s from first text: `41.58`
- mean per-request output tok/s after TTFT: `24.97`
- mean TTFT: `131.7 ms`

c8 also completed successfully:

- artifact: `data/qwen36-quark-int8-tp4-ngram5-cg128-gdnmixed-schedguard-c8-20260610.json`
- aggregate output tok/s from first text: `1143.47`
- mean per-request output tok/s after TTFT: `182.79`
- mean TTFT: `454.2 ms`

The c8 number is an upper-bound/reliability signal only. The concurrency script
uses very repetitive prompts and asks the model to continue repeated benchmark
tokens, which is ideal for prompt-lookup n-gram speculation.

No `ERROR`, `Traceback`, `PassManager`, `EngineDead`, `Internal Server`, or
`RuntimeError` appeared after the guarded c2/c8 runs.

## Single-Request Speed

The guarded standard single-request gate:

- artifact: `data/qwen36-quark-int8-tp4-ngram5-cg128-gdnmixed-schedguard-single-20260610.json`
- corrected output tok/s mean: `108.04`
- corrected output tok/s median: `99.75`
- corrected output tok/s min/max: `95.33` / `167.55`
- e2e output tok/s mean: `106.43`
- TTFT mean: `76.28 ms`

This remained above the accepted no-prefix baseline but lower than the earlier
ungarded n-gram run at `114.86` corrected output tok/s mean.

## Quality Failure

The guarded candidate failed quality validation twice in different ways.

First run:

- artifact: `data/qwen36-quark-int8-tp4-ngram5-cg128-gdnmixed-schedguard-frontdoor-quality-20260610.json`
- exact cases passed
- repeat stability passed
- long-context needle failed
- output included a corrupted fragment:
  `B whiskey whiskey whiskey \\_QWEN36\\_36\\_NEEDLE\\_20260609`

Rerun:

- artifact: `data/qwen36-quark-int8-tp4-ngram5-cg128-gdnmixed-schedguard-frontdoor-quality-rerun-20260610.json`
- exact cases passed
- long-context needle passed and matched baseline
- repeat stability failed
- one temperature-0 repeat emitted extra unrelated text:
  `blue, ließ国土资源局 green, orange, red`

This is not acceptable. A target-verified speculative path should not create
rare wrong tokens at temperature 0.

## Decision

Reject the scheduler-guarded n-gram candidate.

The guard is useful diagnostically because it prevents the c2 crash, but the
overall n-gram speculative path is not safe enough for production:

- it fails quality/repeatability
- it disables async scheduling
- single-request speed is still far below the 200 tok/s target
- aggregate wins are highly workload-dependent on repetitive text

Next better targets:

1. Investigate whether the n-gram quality failures are from XPU GDN state
   handling, speculative token acceptance bookkeeping, or prompt-lookup proposer
   behavior.
2. Prefer lower-risk speed paths that keep the accepted target decode path
   unchanged, such as decode graph/cache coverage, GDN recurrent update kernels,
   custom collective overhead, and MoE INT8/XPU kernel improvements.
3. If speculation is revisited, require a strict quality gate with repeated
   long-context and repeat-stability runs before any speed result counts.
