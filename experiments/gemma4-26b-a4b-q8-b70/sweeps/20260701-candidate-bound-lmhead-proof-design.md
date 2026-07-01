# Gemma 4 26B Q8 Candidate-Bound LM-Head Audit And Accept-Prefix Plan

Date: 2026-07-01

Status: candidate-bound proof closed as not currently implementable; next source lane is exact accept-prefix row economics. No performance claim yet.

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
candidate-only shortcut is not exact: early mismatches still need the true
target top token. A candidate-bound LM-head proof is only useful if it can prove
candidate victory without scanning the full vocabulary. The current code does
not provide such a mathematical bound, so a proof-or-fallback implementation
would still pay the hard full-vocab Q8 LM-head work on fallback and would not be
a credible record lane.

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

## Audit Result: Candidate-Bound Proof Is Not The Next Patch

Independent read-only audit agreed with the earlier no-go note: candidate-bound
LM-head proof is not implementable as an exact shortcut in the current design
unless it avoids the full-vocab scan. Exact speculative verification must return
the target model's actual top token on the first mismatch, not only a boolean
that the draft candidate lost. Without a true conservative bound, a
candidate-vs-max kernel still does the expensive full-vocab Q8 dot/reduction,
which is the cost we need to remove.

This closes the profiler-first idea in this note. The preedit source snapshot
above remains useful as a provenance anchor, but the next code work should not
build another candidate-threshold / candidate-vs-max path that preserves
full-vocab work.

## Phase 1 Replacement: Exact Accept-Prefix Row Economics

Goal: make the existing exact accept-prefix verifier LM-head path cheaper enough
that oracle row savings beat launch/reduction overhead.

Constraints:

- default off;
- exact target top-1 for every emitted row;
- preserve full-match bonus row semantics;
- one target decode boundary, no staged server-level decode;
- fixed realistic cold suite for any gate result;
- `cached_tokens=0` required;
- no n-gram/history/cache/checkpoint acceleration;
- do not submit profiler-only or failed-parity results to LocalMaxxing.

Current row-economics evidence:

```text
rows_current=3679 rows_oracle=2893 rows_saved=786 save_pct=21.365
full_match=541 full_match_with_bonus=541 accept_prefix_counts=(0:144, 1:118, 2:123, 3:536)
```

The existing `ggml_mul_mat_argmax_accept_prefix()` path is exact, but earlier
runs lost because it serializes rows and launches/reduces per row. The useful
source lane is to keep the same semantics while reducing that overhead:

1. keep row 0 exact top1;
2. conditionally compute row 1/2/bonus only while prior sampled IDs match the
   shifted draft tokens;
3. avoid host-loop/staged decode boundaries;
4. if possible, fuse more of the row dependency into one backend path or reduce
   launches while still not computing rows after a mismatch.

If a cheaper accept-prefix implementation still loses, close this verifier row
lane and move to larger verifier/MoE boundary reduction rather than more LM-head
subgroup or threshold tuning.

## Code Touch Points

Inspect/edit only within the existing active source checkout:

- `tools/server/server-context.cpp` around verifier row construction, parity,
  and `record_spec_row_economics()`;
- `src/models/gemma4.cpp` around `accept_prefix_argmax_supported` and the
  `ggml_mul_mat_argmax_accept_prefix()` graph branch;
- `src/llama-context.cpp` for the existing accept-prefix env/cparam plumbing;
- `ggml/include/ggml.h` and `ggml/src/ggml.c` for the `GGML_OP_MUL_MAT_ARGMAX`
  mode contract;
- `ggml/src/ggml-sycl/ggml-sycl.cpp` dispatcher around `argmax_mode == 2`;
- `ggml/src/ggml-sycl/mmvq.cpp` / `mmvq.hpp` for the Q8_0 reordered
  accept-prefix kernel.

Avoid resurrecting failed pointer-only sampled-ID egress, top2 side-output, or
candidate-threshold variants without a new producer-side design.

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

If the accept-prefix implementation cannot beat current multi-row argmax after
full512 same-window validation, close this lane and move to larger verifier/MoE
boundary design rather than more subgroup, p_min, or candidate-threshold tuning.
