# 2026-07-09 - Corrected DFlash acceptance probe: functional, but no-go

Status: **closed acceptance no-go** for the Qwen3.6 27B INT4 one-B70 lane.

## Question

The previous local DFlash result used stale semantics: target auxiliary hidden
states `(1, 16, 31, 46, 61)` and only `k` lookahead slots. Upstream fixes use
post-layer captures `(2, 17, 32, 47, 62)`, allocate `k + 1` slots, and allocate
lookahead on first prefill. The purpose of this run was to determine whether a
corrected DFlash draft has enough acceptance on the fixed realistic suite to
justify a substantial Intel/XPU backend or Hipfire-style implementation.

## Source corrections tested

Local equivalents of these upstream changes were applied:

- `c628a93a64fb4929c3c11d8e2c7244c4826b4f76` - correct DFlash auxiliary
  hidden-state indexing;
- `7fb9c0197a3173f2a2edcc9d64f6c0e73ef20717` - allocate `k + 1` DFlash
  lookahead slots, including first prefill.

The existing local PR40898-style mixed sliding/full attention repair remained
active. The draft checkpoint was:

```text
/mnt/fast-ai/llm-cache/hf/manual/z-lab--Qwen3.6-27B-DFlash
```

## Mechanical failure and isolation

The first corrected probe combined DFlash with the target ReplaySSM state
machinery and appeared to supply `[0, 0, 0, 0, 0, 0, 0, 0]` as every draft
row. This was not evidence about DFlash model quality. ReplaySSM reserves large
per-block scratch for 48 GDN layers and the diagnostic request could remain
unscheduled; vLLM also has an explicit all-zero draft fallback when the input
cannot be proposed.

A default-off diagnostic recorded the actual proposer gate and tensors. With
ReplaySSM removed, corrected DFlash was mechanically healthy:

- proposer gate: `87 + 8 <= 2048`, `input_fits_in_drafter=true`;
- sample indices: exactly `[1, 2, 3, 4, 5, 6, 7, 8]`;
- sample hidden states: `40,960 / 40,960` finite, nonzero norm;
- mask token: `248070`;
- draft tokens: normal nonzero vocabulary IDs with finite top scores.

The one-prompt cold diagnostic completed at `39.6224 tok/s`. This row was only
a plumbing check and is not a promoted result.

## Fixed-suite acceptance result

Target:

```text
webhie/Qwen3.6-27B-int4-AutoRound
revision f5750c90b3776db658594df5fe8051098226dd8e
```

Run identity:

```text
method=dflash
num_speculative_tokens=8
cudagraph_mode=NONE
--no-async-scheduling
ReplaySSM disabled
runtime INT8 LM-head, BF16 scales
12 unique realistic prompts, once each
cached_tokens=0 for every request
```

Result:

- strict fresh-response median: `52.029724994946264 tok/s`;
- p10: `48.35401392123913 tok/s`;
- mean: `52.134584558223615 tok/s`;
- median TTFT: `2506.286 ms`;
- all 12 prompts had `cached_tokens=0`;
- 570 verifier steps;
- mean accepted draft prefix: `1.731578947368421` of 8;
- mean generated tokens per target step: `2.731578947368421`;
- median accepted draft prefix: `1`;
- zero-accept steps: `156 / 570`;
- full accepts: `10 / 570`.

Acceptance histogram:

```text
accepted drafts: 0   1   2  3  4  5  6  7  8
steps:          156 184  91 52 34 21 10 12 10
```

Evidence:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-dflash-auxfix-lookahead-k8-noreplay-acceptance-20260709T220919Z.json
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-dflash-auxfix-lookahead-k8-noreplay-20260709-verify.jsonl
verify trace sha256: 9ae4f178205794980536b49f287944141db570f3f24cfca3934736a8dd807633
```

The trace is `242,985` bytes and remains outside Git; the checksum and complete
summary above are the durable reference.

## Decision

Do not port or optimize Hipfire/DFlash kernels for this checkpoint. Corrected
DFlash averages the same approximately `2.7` generated tokens per target step
as the current intrinsic MTP3 lane, while adding draft cost and reducing strict
throughput from the valid `68.2363 tok/s` record to `52.0297 tok/s`. It is far
below the predeclared `4.5+` tokens-per-step gate needed to justify deeper
backend work.

This closes only this DFlash checkpoint on the fixed chat-style suite. A future
target-matched draft may reopen the lane, but it must first clear the same
cache-zero acceptance oracle before kernel work begins.
