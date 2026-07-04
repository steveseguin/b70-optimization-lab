# 2026-07-04: Draft top-k calibration diagnostic

## Context

The active Qwen27 target remains the strict fresh-response
`webhie/Qwen3.6-27B-int4-AutoRound + runtime INT8 LM-head (BF16 scales)` row:

- current approved record: `65.27648650325429 tok/s`;
- LocalMaxxing: `cmr5iu3gk00bfq901nidgcana`;
- recipe: TP1, one B70, MTP3/cg8, XPU graph on,
  `VLLM_XPU_LM_HEAD_INT8=1`,
  `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`,
  `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`,
  `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`;
- validity policy: fixed realistic prompts, each prompt once,
  `cached_tokens=0`, no warmed/history/prefix reuse, target-verified MTP only.

The previous verifier trace showed the current MTP3 path averages about
`2.7` target-verified tokens per verifier step. A perfect MTP3 drafter would
reach `4.0` target-verified tokens/step, so accepted-token improvement remains
valuable even though it is not enough by itself to guarantee `100+ tok/s`.

## Diagnostic patch

Added a default-off draft-top-k trace in
`/home/steve/src/vllm/vllm/v1/spec_decode/llm_base_proposer.py`.

Environment controls:

```bash
VLLM_XPU_DRAFT_TOPK_TRACE_FILE=<run>/draft-topk.jsonl
VLLM_XPU_DRAFT_TOPK_TRACE_K=32
VLLM_XPU_DRAFT_TOPK_TRACE_MAX_LINES=0
```

The trace records, per MTP draft position:

- `draft_pos`;
- sampled draft token ID;
- top-k token IDs and scores from the existing dense draft logits.

No behavior changes unless `VLLM_XPU_DRAFT_TOPK_TRACE_FILE` is set. Syntax
check passed against the XPU venv.

Patch snapshots:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-active-stack-before-draft-topk-trace-20260704T143535Z.patch
patches/qwen36-27b-autoround-int4-b70/vllm-draft-topk-trace-diagnostic-20260704T143752Z.patch
```

Added analyzer:

```text
scripts/analyze-qwen27-draft-topk-trace.py
```

Important implementation detail: the draft stream contained `1171` proposer
groups while the verifier stream contained `1147` real records, because extra
proposer groups appear around warmup/request boundaries. A fixed global offset
misaligns after the first block. The analyzer now uses greedy exact alignment
on the sampled draft-token tuple and reports alignment health.

## Run

Run directory:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/runs/qwen27-webhie-bf16scale-drafttopk-calib-20260704T143725Z
```

Strict result JSON:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-drafttopk-calib-20260704T143725Z-20260704T143725Z.json
```

Summaries:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-drafttopk-calib-20260704T143725Z-20260704T143725Z-verify-summary.md
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-drafttopk-calib-20260704T143725Z-20260704T143725Z-verify-summary.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-drafttopk-calib-20260704T143725Z-20260704T143725Z-draft-topk-analysis.json
```

Classification:

- **diagnostic only**;
- top-k tracing adds CPU/logging overhead, so the paired `56.671 tok/s`
  throughput is not a record or regression signal;
- final gate still passed mechanically with `cached_tokens=0` for all
  `24/24` calibration prompts.

Verifier summary:

- verifier steps: `1147`;
- prefix-accepted tokens: `1964`;
- mean target-verified tokens/step: `2.71229293809939`;
- full-accept rate: `0.36006974716652135`;
- per-position current draft/target match:
  - pos0 `0.8020924149956408`;
  - pos1 `0.6765475152571927`;
  - pos2 `0.5937227550130776`.

Draft top-k alignment:

- exact sampled-draft tuple matches: `1147/1147`;
- skipped extra draft groups: `24`;
- fallback matches: `0`;
- first-choice match rate after alignment: `1.0`.

Top-k oracle:

- base mean target-verified tokens/step: `2.71229293809939`;
- impossible oracle reranker over draft top-32:
  `3.910200523103749` target-verified tokens/step;
- target token appears in the draft top-32 at:
  - pos0 `0.994768962510898`;
  - pos1 `0.979947689625109`;
  - pos2 `0.963382737576286`.

This is a real signal: the draft distribution usually contains the target
token, but not at rank 1.

## Cheap calibration sanity checks

Two offline split checks were run before considering endpoint code:

1. Sparse per-position token-bias perceptron on even steps, evaluated on odd
   steps.
2. Simple margin rule, e.g. choose rank 2 when rank1-rank2 margin is small.

Results:

- base even/odd split:
  - train `2.6916` target tokens/step;
  - heldout `2.7330` target tokens/step;
- best simple margin rule found on train:
  - train `2.7003`;
  - heldout `2.7365`;
- sparse token bias can overfit train heavily, but heldout either stays flat
  or regresses after more than the tiniest update.

Interpretation: the top-k oracle headroom is not captured by a trivial static
token bias or margin heuristic. Shipping such a heuristic would be noise-level
at best and likely brittle.

## Decision

Close **simple static draft calibration** for now. Do not implement a runtime
token-bias or rank-margin reranker from this trace.

The useful follow-up is a real learned drafter/reranker trained on a larger,
isolated non-final corpus, or an architectural draft path that uses more of the
target-model signal without violating target verification. The final Qwen
realistic suite must remain isolated from tuning and promotion must still use
the strict cold/fresh gate.

No LocalMaxxing submission.

## Next credible actions

1. If continuing accepted-token work, collect a larger non-final calibration
   corpus with draft top-k and target verifier IDs, then train/evaluate a
   lightweight reranker on held-out prompts before endpoint testing.
2. If prioritizing step-cost work, return to LM-head/verifier producer
   economics. Current full-vocab top-1 and candidate-max standalone kernels
   are closed no-win; a future attempt needs a materially different primitive
   such as an integrated oneDNN/XPU top-id/candidate-score epilogue or fewer
   LM-head calls/rows.
3. Backport/test upstream spec safety fixes only as correctness/plumbing
   prerequisites. In particular, upstream vLLM now rejects `-1` placeholder
   draft tokens in the rejection sampler; that may matter if partial-group or
   padded-tail speculation is reopened, but it is not a current record path.
