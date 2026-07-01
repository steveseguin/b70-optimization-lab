# 2026-07-01 - Gemma 4 26B Q8 verifier top2/margin diagnostic

## Purpose

This is a diagnostic-only experiment for the Gemma 4 26B A4B Q8 B70 short-context
decode lane. The current valid record remains the cold realistic-suite
`124.97714084813418 tok/s` run:

- `data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`
- LocalMaxxing submission: `cmr1u77na01k2ld01kalwzs1e`

The goal here was not to claim throughput. The goal was to understand verifier
cost and draft-token miss quality by recording whether rejected draft tokens are
usually the target LM-head top2 candidate, and what the top1-top2 margin looks
like.

## Workspace discipline

Canonical active workspace:

- `/home/steve/llm-optimizations`

Archive-only / do-not-continue worktree:

- `/home/steve/qwen36-results-main`

Active source tree for the built server:

- `/home/steve/src/llama.cpp-gemma-record-repro-c926`
- base commit: `c926ad098` (detached)
- intentionally dirty with the Gemma record optimization stack

The source state before this diagnostic was preserved in:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-verifier-v3-preedit-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-verifier-v3-preedit-source.diffstat`

The current source snapshot for this diagnostic is preserved in:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-verifier-top2-margin-profile-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-verifier-top2-margin-profile-source.diffstat`

## Patch design

Default-off flags added:

- `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_SCORES=1`
- `LLAMA_SPEC_VERIFY_TOP2_PROFILE=1`

Important safety constraint:

- The verifier acceptance path still consumes the original one-token-per-row
  `sampling.sampled` tensor.
- The new top2 data is copied through a separate diagnostic side channel,
  `sampling.sampled_top2`, with four int32 slots per verifier row:
  `top1_id`, `top2_id`, `bitcast(top1_logit)`, `bitcast(top2_logit)`.
- `common_sampler_sample_and_accept_n()` is not changed by this diagnostic.

This keeps the accepted-token decision unchanged while trying to collect
top2/margin statistics after acceptance.

## Build

Build command:

```bash
source /opt/intel/oneapi/setvars.sh --force
cmake --build /home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 --target llama-server -j 8
```

Result:

- build passed on 2026-07-01
- `git diff --check` passed on the source tree

## Diagnostic runs

Initial full diagnostic:

```bash
cd /home/steve/llm-optimizations
LABEL="gemma4-q8-gpu0-verifier-top2-margin-profile-20260701T165057Z" \
GPU_INDEX=0 PORT=18420 \
CANARY_REPEATS=16 MAX_TOKENS=128 REALISTIC_METRIC_TOKENS=100 \
LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_SCORES=1 \
LLAMA_SPEC_VERIFY_TOP2_PROFILE=1 \
LLAMA_SERVER_SPEC_PROFILE=1 \
bash repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh
```

Follow-up fixes tested:

- `gemma4-q8-gpu0-verifier-top2-margin-profile-fix-20260701T170304Z`
  added `output_reorder()` before reading the side tensor.
- `gemma4-q8-gpu0-verifier-top2-margin-profile-rowapi-20260701T171524Z`
  added `llama_get_sampled_top2_ith()` so the server could request rows by
  resolved verifier output index instead of reading the side tensor directly.

Validation status:

- all three runs built and executed successfully;
- canary and fixed cold-suite gates passed for the requested shortened
  diagnostic shapes, with `cached_tokens=0`;
- no run is a record candidate and nothing was submitted to LocalMaxxing.

Observed summaries:

| Label | Shape | Canary rows | Median tok/s | Gate | Top2 rows |
| --- | --- | ---: | ---: | --- | ---: |
| `gemma4-q8-gpu0-verifier-top2-margin-profile-20260701T165057Z` | `MAX_TOKENS=128`, metric 100 | 64 | `113.8455966851666` | pass | `0` |
| `gemma4-q8-gpu0-verifier-top2-margin-profile-fix-20260701T170304Z` | `MAX_TOKENS=64`, metric 50 | 16 | `120.49005685548038` | pass | `0` |
| `gemma4-q8-gpu0-verifier-top2-margin-profile-rowapi-20260701T171524Z` | `MAX_TOKENS=64`, metric 50 | 16 | `120.32975717583233` | pass | `0` |

Evidence paths:

- `data/gemma4-q8-gpu0-verifier-top2-margin-profile-20260701T165057Z/summary.json`
- `data/gemma4-q8-gpu0-verifier-top2-margin-profile-fix-20260701T170304Z/summary.json`
- `data/gemma4-q8-gpu0-verifier-top2-margin-profile-rowapi-20260701T171524Z/summary.json`
- `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-verifier-top2-margin-profile-20260701T165057Z.server.log`
- `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-verifier-top2-margin-profile-fix-20260701T170304Z.server.log`
- `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-verifier-top2-margin-profile-rowapi-20260701T171524Z.server.log`

Final server-profile lines:

```text
initial: steps=746 rows=0 top1_matches=0 mismatches=0 draft_is_top2=0
fix:     steps=304 rows=0 top1_matches=0 mismatches=0 draft_is_top2=0
rowapi:  steps=311 rows=0 top1_matches=0 mismatches=0 draft_is_top2=0
```

## Outcome

Closed as an instrumentation failure / negative diagnostic, not an optimization
result. The top2 side-channel did not yield usable rows even after the direct
side tensor read was corrected and then replaced with a resolved-row accessor.
Do not infer anything about draft-token top2 frequency or margin from this
experiment.

The current promoted Gemma Q8 record remains
`124.97714084813418 tok/s` from
`data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`.

## Follow-up decision

Do not continue this lane by running more benchmarks. If the top2/margin idea is
reopened later, first add explicit startup and graph-build logging for:

- `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_SCORES`
- `LLAMA_SPEC_VERIFY_TOP2_PROFILE`
- whether the target verifier graph actually creates `t_sampled_top2_rows`
- whether the backend output copy receives non-null top2 row tensors

After these runs, the repo harness was updated to carry those two env flags
through the promoted wrapper, replica log header, and summary `launcher_identity`.
Future top2 diagnostics still need explicit graph-build/copy logging before
another benchmark run. Until then, better near-term work is either a
non-invasive short-decode paired A/B candidate or the separate prompt/prefill
service ladder, always guarded by the fixed cold realistic suite.
