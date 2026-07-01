# Verifier Top2 V2 Instrumentation Failure

Date: 2026-07-01

## Purpose

Try to revive the verifier LM-head top2/margin diagnostic so future exact
candidate-vs-max or row-adaptive verifier work can be driven by real margin
data instead of speculation.

This was diagnostic-only. `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_SCORES=1` adds an
extra top2 LM-head side output and is not a headline throughput recipe.

## Patch Artifacts

- Pre-edit source snapshot:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-verifier-top2-v2-preedit-source.patch`
- Tested source snapshot:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-verifier-top2-v2-source.patch`
- Diffstat:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-verifier-top2-v2-source.diffstat`

The active llama.cpp source was restored to the pre-edit record stack after the
diagnostic. A post-restore diff was byte-identical to the pre-edit snapshot
(`cmp_rc=0`).

## Build

The top2-v2 source patch built successfully with the active SYCL B70 AOT build:

```text
llama-server version: 9769 (c926ad098)
built with IntelLLVM 2026.0.0 for Linux x86_64
```

Build note: the UI asset step still reports the known non-fatal npm engine
warning (`@chromatic-com/storybook` wants node >=20; local npm is 9.2.0), then
continues using the existing HF UI stamp.

## Diagnostic Runs

### `gemma4-q8-gpu0-verifier-top2-v2-smoke-20260701T194743Z`

- Result: cold realistic gate passed, `cached_tokens=0`, canary 32/32.
- Summary:
  `data/gemma4-q8-gpu0-verifier-top2-v2-smoke-20260701T194743Z/summary.json`
- Server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-verifier-top2-v2-smoke-20260701T194743Z.server.log`
- Diagnostic finding:
  `spec verify top2 profile: rows=512, missing=0`, but
  `sampled_eq_top1=0`, `draft_top1=0`, `draft_top2=0`, `draft_other=512`,
  and average margin was `NaN`.

That showed the host buffer/API path existed, but the data was not usable.

### `gemma4-q8-gpu0-verifier-top2-v2-raw-smoke-20260701T195843Z`

- Result: cold realistic gate passed, `cached_tokens=0`, canary 4/4.
- Summary:
  `data/gemma4-q8-gpu0-verifier-top2-v2-raw-smoke-20260701T195843Z/summary.json`
- Server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-verifier-top2-v2-raw-smoke-20260701T195843Z.server.log`
- Raw first rows:

```text
spec verify top2 sample: idx=0, draft=14433, sampled=14433, top1=-1, top2=-1, bits1=-1, bits2=-1, logit1=-nan, logit2=-nan
spec verify top2 sample: idx=1, draft=1083, sampled=1083, top1=-1, top2=-1, bits1=-1, bits2=-1, logit1=-nan, logit2=-nan
spec verify top2 sample: idx=2, draft=236743, sampled=236812, top1=-1, top2=-1, bits1=-1, bits2=-1, logit1=-nan, logit2=-nan
```

The top2 buffer stayed at its `LLAMA_TOKEN_NULL` initialization values. The
run header recorded `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_SCORES=1`, but the
server log did not emit the target-context enable line
`speculative verifier top2 score outputs enabled`. The sampler-side profile
env was active, but the target graph side output was not actually produced in
the active MTP verifier path.

## Post-Restore Sanity

After preserving the patch, the active source was restored to the pre-top2
record stack and rebuilt. Compact sanity run:

- Label:
  `gemma4-q8-gpu0-post-top2v2-revert-sanity-20260701T201036Z`
- Summary:
  `data/gemma4-q8-gpu0-post-top2v2-revert-sanity-20260701T201036Z/summary.json`
- Server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-post-top2v2-revert-sanity-20260701T201036Z.server.log`
- Result: cold realistic gate passed, `cached_tokens=0`, canary 16/16.
- Compact metric: median `124.03008933114222 tok/s` for tokens 1-50 after
  TTFT with `MAX_TOKENS=64`.

This is a sanity check, not a new headline record. The current full512 record
remains `124.97714084813418 tok/s`.

## Decision

Close top2-v2 as **instrumentation failure, build-valid but data-invalid**.

Do not use the top2-v2 profile output to justify LM-head candidate-vs-max,
margin thresholds, or row-adaptive verifier decisions. The useful conclusion is
that the top2 side tensor must be attached to the exact target verifier graph
path that already supplies backend sampled IDs; simply adding
`t_sampled_top2_rows` to the Gemma direct-argmax branches is insufficient for
the current MTP verifier construction.

The active optimization workspace remains:

- repo: `/home/steve/llm-optimizations`
- source: `/home/steve/src/llama.cpp-gemma-record-repro-c926`
- detached `/home/steve/qwen36-results-main`: audit/back-reference only.
