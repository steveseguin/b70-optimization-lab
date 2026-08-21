# Qwen3.8 TP2 draft-INT4 margin qualification preregistration

Status: **preregistered; not launched**.

## Question and hard boundary

Before any throughput experiment, test whether the TP-safe draft-INT4 margin
repair preserves the exact gathered FP16 draft-head argmax on real TP2 model
calls. This is one instrumented treatment-only qualification, not an A/B,
throughput result, target-quality result, or authorization to run the 25-prompt
suite with margin enabled.

The treatment fixes the effective and independently expected margin to `0.25`.
Each TP rank repairs its local approximate winner and every local column within
the margin before the ordinary gathered draft logits. Qualification-only code
also computes full exact FP16 local logits and gathers approximate, repaired,
and exact logits. Those extra projections and three all-gathers are deliberately
expensive. No timing from this process may be interpreted or promoted.

The lab harness rejects margin `0.25` unless
`VALIDATION_REQUIRE_DRAFT_MARGIN_SCREEN=1`. The qualification mode in turn
requires smoke and quality off, exactly the tracked three-prompt suite, a
128-token output cap, and a 32-event diagnostic metric window. Therefore this
change does not self-authorize a full-25 margin arm. Any future full-25 screen
would need a separate preregistration and an immutable passing qualification
result/SHA gate that does not exist here.

M1 remains invalid, closed, and no-retry. This experiment does not reopen it.

## Frozen workload

The suite is
[`2026-08-20-draft-margin-tp2-qualification-suite.json`](../data/2026-08-20-draft-margin-tp2-qualification-suite.json),
SHA-256
`271958be5264fa095e180bd196ac82e198c6c9ae7879ef83eb3f5fa4b63a1df7`.
It contains exact copies, in order, of full-suite indices:

1. `6`, `selection--sql-debugging`;
2. `11`, `holdout--factual-protocol`;
3. `24`, `holdout--long-rollover-repository-audit`.

Only these three benchmark requests run. `RUN_SMOKE=0`, `RUN_BENCH=1`, and
`RUN_QUALITY=0`; max tokens are `128`, the non-promotable timing window is `32`,
engine seed is `0`, request seed is `1`, and cached tokens must remain zero.

The JSONL interface has a ceiling of `1024` real calls so evidence is not
artificially exhausted on the first or second prompt. It suppresses records
during Torch compilation and current-stream graph capture. The schema carries
no request ID, so records bind collectively to the only three-prompt workload.
They do not establish that each prompt contributed a record. At least 64
contiguous real call indices and 64 records are required.

## Exact runtime and source identity

Q1 runs TP2 on physical GPUs `2,3`, one request at a time, FP16 compute,
AutoRound INT4, native MTP5, greedy sampling, target INT8 head, and the already
active TP-sharded INT4 draft head. It retains the exact 4dd native-extension +
339 graph-safe FlashAttention composite, all-target INT4 dependency/completion
repair, oneDNN INT4 determinism padding, native GDN, persistent scratch, and
the sealed b991 outer/AOT cache.

The cache namespace is `b99160ae76`; its canonical manifest SHA-256 is
`f3582440de9b252cc738648aa5b690fd324bec9afeb8d89e4b73d295071cb0ff`.
The gate requires two outer and four AOT direct loads, no compile/store/save
marker, and byte-identical pre/post manifests.

vLLM remains at `44fc8fde09fc311d3099dab10366b672d9142ea4`. The tracked
TP-safe production-margin plus qualification-instrumentation artifact is
[`vllm-qwen38-draft-head-int4-tp-safe-margin-qualification-20260820.patch`](../patches/vllm-qwen38-draft-head-int4-tp-safe-margin-qualification-20260820.patch),
SHA-256
`f2cde099a74ad3fbd0a0292d5bb16029f8d00d662010b5a93833ce8273b8980d`.
The authoritative combined live binary-diff SHA-256, including the previously
tracked target/verifier marker hunk, is
`66f5823ca1f48545f1adef3731b165bc14975d374ff2899ce91272e94a30a852`.
The request-selected replay selector and umbrella bypass both remain zero, so
that earlier branch marker must not appear.

The historical standalone synthetic result
[`2026-08-20-int4-margin-equiv.json`](../data/2026-08-20-int4-margin-equiv.json)
is snapshotted at SHA-256
`bc34533363beca2dce193f85403ad24e40585117f6e2e6c8d2b577aea2d192be`
as a required supporting-context input (`40/40`, zero synthetic argmax
mismatches). It is neither sufficient TP2 proof nor authorization. The new
sealed real-call JSONL and passing arm-gate result are the qualification
artifact.

All model manifest, direct-plus-ordinary verifier, stage manifest, native/core/
MoE/FA extensions, oneCCL, source HEAD/diff, lab runner/checker/wrapper, suite,
quality-baseline input, and clean `main == origin/main` identities are pinned by
the launcher and recorded in the arm.

## Fail-closed evidence contract

The server log must contain exactly two fully parsed production-path markers:

```text
XPU TP-safe draft LM-head INT4 margin repair engaged: margin=0.25 tp_rank=R tp_size=2.
```

They must be Worker_TP0/rank 0 and Worker_TP1/rank 1 exactly once each. This
proves runtime entry into the real repair branch. The JSONL provides the
separate numerical evidence.

Every JSONL line must be strict standard JSON with no blank line, duplicate
key, non-standard constant, scalar row, unknown field, missing field, bool in
an integer field, nonfinite number, duplicate call/row pair, reordered pair,
or discontinuous call/row index. With max sequences fixed to one, each
proposer call selects exactly one hidden row for `compute_logits`, so every
captured call must contain exactly `row_index=0`. Each record must have:

- schema `qwen38-draft-margin-tp2-qualification-v1`, margin `0.25`, TP size
  `2`, and shard width `124160`;
- global token IDs in `[0,248320)` and per-rank token IDs inside the correct
  `[rank*124160,(rank+1)*124160)` shard;
- exactly two ordered per-rank records for ranks `0,1`;
- candidate counts in `[1,124160]` and
  `exact_top_is_candidate=true` for both ranks;
- truthful approximate/repaired match booleans, with the gathered exact and
  approximate winners consistent with a local rank winner;
- `repaired_matches_exact=true`; and
- every global and per-rank `max_abs_error` finite, nonnegative, and strictly
  less than `0.125`.

The strict bound is load-bearing: the repair mask uses `< margin`, so margin
`0.25` needs `0.25 > 2 * max_error`, not equality at the boundary. At least one
gathered approximate argmax must differ from the exact argmax while the
repaired argmax matches exact. A zero-mismatch sample proves only that the
added repair was inert for these observed calls and terminates as no
demonstrated acceptance lever.

The compact `tp2-sealed-gates.json` records the immutable JSONL SHA, call and
record counts, call range, candidate-count range, maximum observed error,
approximate mismatch count, and repaired mismatch count. Positive valid
SpecDecoding metrics, two rank-specific draft-INT4 preparation markers,
unchanged graph topology, the normal pad/cache/model/source gates, benchmark
freshness, and clean process-group shutdown remain mandatory.

## Terminal rules

1. Run `check`. Any source, patch, cache, model, stage, suite, synthetic-support,
   or harness identity mismatch blocks Q1.
2. Run Q1 once. Any nonzero runner status, missing/malformed JSONL, fewer than
   64 calls or records, marker mismatch, repaired mismatch, missed exact
   candidate, zero approximate-to-exact gathered mismatches, error at or above
   `0.125`, benchmark failure, cache mutation, or
   ordinary sealed-gate failure is terminal. Do not repair the artifacts and
   retry under the same preregistration.
3. A passing Q1 supports only bounded real-call TP2 draft-head equivalence for
   the observed collective records. It does not establish per-prompt coverage,
   target output exactness, lane-wide determinism, performance, or promotion.
4. No second arm, full-25 arm, LocalMaxxing submission, or service change is
   authorized by this preregistration.

Launcher:
[`run-20260820-draft-margin-tp2-qualification.sh`](../scripts/run-20260820-draft-margin-tp2-qualification.sh).

Exact operator sequence after the plan is committed and independently audited:

```bash
/home/steve/llm-optimizations/experiments/qwen38-27b-b70/scripts/run-20260820-draft-margin-tp2-qualification.sh check
/home/steve/llm-optimizations/experiments/qwen38-27b-b70/scripts/run-20260820-draft-margin-tp2-qualification.sh q1
```
