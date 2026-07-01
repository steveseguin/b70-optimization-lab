# Gemma 4 26B Q8 Candidate-Bound LM-Head Proof Plan

Date: 2026-07-01

Status: next active source lane; design/profiler first, no performance claim yet.

## Why This Lane

The promoted Gemma Q8 record is still dominated by target/verifier-side work.
Simple config roulette is exhausted: p_min/n_min/depth/ubatch, LM-head subgroup,
DMMV/no-reorder, accept-prefix v1/v2, late-head, direct sampled-ID egress,
adaptive/no-bonus rows, and several MoE/FA-side lanes are closed or not record
paths. The host-side candidate-proof profile showed useful structure:

```text
steps=452 verifier_rows=1802 draft_rows=1350 draft_match_rows=1102 (81.630%)
full_draft_matches=277 (61.283%) missing_sampled_rows=0 nonconsecutive_steps=0
first_mismatch_counts=(0:72, 1:48, 2:59, 3:273)
```

That means the draft candidate is often the token the target accepts, but a
host-side shortcut is not exact: early mismatches still need the true target top
token. The only acceptable path is an in-graph/default-off proof-or-fallback
path that preserves exact verification.

## Active Workspace Rules

Use one workspace only:

```text
repo:   /home/steve/llm-optimizations
source: /home/steve/src/llama.cpp-gemma-record-repro-c926
```

Do not run new experiments from `/home/steve/qwen36-results-main`; it is an
archive/back-reference checkout only.

Preedit source snapshot for this lane:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-candidate-bound-lmhead-proof-preedit-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-candidate-bound-lmhead-proof-preedit-source.diffstat`

Source base: llama.cpp `c926ad098` plus the active dirty record stack.

## Phase 1: Exact Proof-Rate Profiler

Goal: measure whether a backend candidate-bound proof could skip meaningful
full LM-head work without changing output tokens.

Constraints:

- default off;
- no token/output behavior changes;
- fixed realistic cold suite for any gate result;
- `cached_tokens=0` required;
- no n-gram/history/cache/checkpoint acceleration;
- do not submit profiler-only results to LocalMaxxing.

Target shape:

1. Carry the sampled draft candidate token IDs already observed by the verifier
   path down to a backend-visible diagnostic path for the narrow Q8 LM-head
   verifier rows.
2. Compute candidate logits and a conservative challenger bound or exact
   challenger result sufficient to prove `candidate >= max(other tokens)`.
3. Count proofable rows, fallback rows, full-draft proofable steps, and where
   proof fails by draft position.
4. Always retain the current exact full LM-head path for actual sampling and
   accepted-token decisions in Phase 1.

The Phase 1 result is useful only if it answers:

- how many verifier rows are proofable without full-vocab top1;
- how many full steps could avoid the expensive verifier path;
- how often fallback would still dominate;
- whether the proof computation itself is plausibly cheaper than current Q8
  reordered LM-head work.

## Candidate Touch Points

Likely source locations to inspect first:

- `tools/server/server-context.cpp` around the existing MTP verifier/profile
  counters;
- `common/sampling.cpp` and `common/speculative.cpp` for sampled candidate row
  plumbing;
- `src/models/gemma4.cpp` around LM-head graph construction;
- `ggml/src/ggml-sycl/ggml-sycl.cpp` and `ggml/src/ggml-sycl/mmvq.cpp` for the
  Q8_0 reordered LM-head backend path.

Do not resurrect the failed pointer-only sampled-ID egress path. It proved that
`op_params` metadata alone does not make backend-produced sampled IDs visible to
the host. Any candidate-bound implementation must attach to the actual producer
or remain purely diagnostic.

## Promotion Bar

A later performance patch can be considered only after Phase 1 shows a credible
skip rate and a strict parity/canary path is clean. Promotion requires:

1. fixed realistic final gate;
2. cold first response per prompt;
3. `cached_tokens=0` on every request;
4. target/verifier model and quantization unchanged;
5. exact target verification preserved;
6. primary metric reported as median tok/s for generated tokens 1-100 after
   TTFT, with p10/mean/TTFT/wall/full512 and logs.

If the proof profiler shows low proofability or high proof cost, close this lane
as negative and move to a different verifier/MoE-boundary design rather than
more subgroup or p_min tuning.
