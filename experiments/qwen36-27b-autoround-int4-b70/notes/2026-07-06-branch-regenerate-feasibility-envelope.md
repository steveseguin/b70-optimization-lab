# Qwen27 Branch/Regenerate Feasibility Envelope

Date: 2026-07-06

Classification: diagnostic cost model, no endpoint, no LocalMaxxing.

## Purpose

We have strong evidence from draft top-k64 traces that the target token is
usually somewhere in the draft distribution, but the previous "independent
oracle" is invalid as an endpoint patch: Qwen27 MTP drafting is sequential, so
changing an early draft token invalidates the later already-generated draft
rows. A real speed win must legally regenerate the dependent suffix, use an
equivalent branch/tree drafter, and still have every accepted token verified by
the target model on a fresh request.

This note turns the existing top-k64 trace into a stricter engineering
question:

- on steps where current MTP3 first rejects at position `a`, how often is the
  target token in draft top-k at that first rejected position?
- if a future legal implementation could choose that branch and regenerate the
  rest of the MTP3 suffix perfectly, what is the optimistic tokens/step ceiling?
- normalized to the current valid `67.51904968102535 tok/s` record, how much
  extra per-step cost can such a design afford before missing `80/90/100/125/150
  tok/s`?

## Artifacts

- script:
  `../../../scripts/model-qwen27-branch-regenerate-feasibility.py`
- compact JSON:
  `../../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-branch-regenerate-feasibility-20260706.json`
- compact Markdown:
  `../../../data/qwen36-27b-autoround-int4-b70-baselines/qwen27-branch-regenerate-feasibility-20260706.md`
- raw draft top-k trace:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-bf16scale-drafttopk64-eaglechat96-20260704T152429Z/draft-topk.jsonl`
- raw verifier trace:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-bf16scale-drafttopk64-eaglechat96-20260704T152429Z/verify-trace.jsonl`

Command:

```bash
cd /home/steve/llm-optimizations
scripts/model-qwen27-branch-regenerate-feasibility.py \
  --draft-topk /mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-bf16scale-drafttopk64-eaglechat96-20260704T152429Z/draft-topk.jsonl \
  --verify-trace /mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-bf16scale-drafttopk64-eaglechat96-20260704T152429Z/verify-trace.jsonl \
  --baseline-tok-s 67.51904968102535 \
  --out-json data/qwen36-27b-autoround-int4-b70-baselines/qwen27-branch-regenerate-feasibility-20260706.json \
  --out-md data/qwen36-27b-autoround-int4-b70-baselines/qwen27-branch-regenerate-feasibility-20260706.md
```

## Inputs And Baseline

- aligned verifier steps: `18761`
- accepted-prefix histogram: `{0: 4498, 1: 4532, 2: 3251, 3: 6480}`
- current mean target-verified tokens/step in this trace: `2.6243270614572785`
- current valid record used for normalization:
  `67.51904968102535 tok/s`
- inferred current verifier-step cost:
  `38.86795021338673 ms/step`

This uses the existing BF16-scale top-k64 diagnostic trace as the acceptance
shape evidence and normalizes step cost to the current valid draft-INT4
ReplaySSM record. It is a bound, not a promoted endpoint result.

## Result

Optimistic legal envelope: choose the target token at the first rejected
position when it is inside top-k, then regenerate the remaining MTP3 suffix
perfectly.

| cutoff | first-reject target in top-k | optimistic tokens/step | no-extra-cost tok/s |
| ---: | ---: | ---: | ---: |
| 1 | `0.000000` | `2.624327` | `67.519` |
| 2 | `0.373097` | `3.169181` | `81.537` |
| 4 | `0.620064` | `3.517776` | `90.506` |
| 8 | `0.779822` | `3.731304` | `96.000` |
| 16 | `0.874033` | `3.852673` | `99.122` |
| 32 | `0.929322` | `3.920900` | `100.877` |
| 64 | `0.959694` | `3.956506` | `101.794` |

Extra per-step cost budget:

| cutoff | 80 tok/s | 90 tok/s | 100 tok/s | 125 tok/s | 150 tok/s |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `-6.064 ms` | `-9.709` | `-12.625` | `-17.873` | `-21.372` |
| 2 | `0.747 ms` | `-3.655` | `-7.176` | `-13.515` | `-17.740` |
| 4 | `5.104 ms` | `0.218` | `-3.690` | `-10.726` | `-15.416` |
| 8 | `7.773 ms` | `2.591` | `-1.555` | `-9.018` | `-13.993` |
| 16 | `9.290 ms` | `3.940` | `-0.341` | `-8.047` | `-13.183` |
| 32 | `10.143 ms` | `4.698` | `0.341` | `-7.501` | `-12.729` |
| 64 | `10.588 ms` | `5.093` | `0.697` | `-7.216` | `-12.491` |

## Interpretation

MTP3 has a hard ceiling of `4` target-verified tokens per step. At the current
`38.87 ms/step`, even a perfect no-overhead MTP3 path tops out near
`102.9 tok/s`. The rank-64 first-reject branch/regenerate envelope is slightly
below that at `101.8 tok/s` because some first rejected target tokens are still
not in top-64.

That means:

- MTP3 branch/regenerate might barely crack `100 tok/s`, but only if the total
  branch selection, suffix regeneration, state transaction, and verification
  overhead is under about `0.7 ms/step` at top-64. That is an extremely tight
  budget.
- MTP3 branch/regenerate cannot reach `125+ tok/s` at the current step cost,
  even under a perfect suffix and zero overhead.
- A one-token first-reject correction alone is not enough, because rejecting at
  position `a` already emits the target token for that position. The speed win
  requires legally regenerating and verifying later suffix rows, or an
  equivalent target-verified branch/tree path.
- The next credible `100+` lane is either (a) deeper speculation with legal
  partial-group/GDN handling, (b) materially lower verifier-step cost, or
  (c) both. Branch/regenerate remains useful as correctness infrastructure, but
  it is no longer a standalone path to `125+`.

## Decision

Do not start a large MTP3-only branch/regenerate implementation expecting
`125+ tok/s`. If we implement it, scope it as a narrow attempt to crack `100`
and as reusable infrastructure for deeper `k>3` speculation. For the main
record push, prioritize designs that either reduce the `~38.9 ms` verifier step
or increase verified tokens/step beyond the MTP3 maximum.
