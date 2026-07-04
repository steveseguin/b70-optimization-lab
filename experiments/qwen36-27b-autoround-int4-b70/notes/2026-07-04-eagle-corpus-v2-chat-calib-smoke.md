# 2026-07-04 - EAGLE Corpus v2 Chat Calibration Smoke

## Classification

Diagnostic only. This is not a final-suite benchmark, not a throughput result,
and not a LocalMaxxing submission candidate.

## Purpose

After closing the first local EAGLE1 endpoint lane, the next safe step was to
verify that corpus/eval v2 tooling can collect diverse chat-style hidden states,
preserve prompt metadata, build `.pt` samples, and report offline acceptance by
prompt family.

## Raw Artifacts

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagledata-v2-chat-calib-20260704T101119Z
```

Compact in-repo summary:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-eagle-corpus-v2-chat-calib-smoke-20260704T101119Z-summary.json
```

## Collection

Config:

- model:
  `webhie/Qwen3.6-27B-int4-AutoRound`, snapshot
  `f5750c90b3776db658594df5fe8051098226dd8e`;
- one B70 (`GPU_INDEX=1`), `QWEN36_27B_ENABLE_MTP=0`;
- XPU graph PIECEWISE, `max_cudagraph_capture_size=8`;
- runtime INT8 LM-head with BF16 scales;
- suite:
  `experiments/qwen36-27b-autoround-int4-b70/calibration-suite-v1.json`;
- API mode: chat;
- `chat_template_kwargs.enable_thinking=false`;
- output tokens: `160` per prompt;
- final realistic suite was not used.

Result:

- prompts: `24`;
- families: `24`;
- generated output tokens / hidden dump rows: `3840`;
- dump shards: `3840`;
- dataset samples: `24`;
- usable rows: `3840`;
- continuity breaks: `0`;
- reconstructed current-token rows: `3840`;
- reconstructed position rows: `3840`.

## Metadata Join Fix

The first dataset build produced `samples_with_metadata=0` because vLLM's
hidden dump request IDs include a response suffix:

```text
collector response_id: chatcmpl-qwen27-eagle-v2-000000-ops-runbook
dump req_id:           chatcmpl-qwen27-eagle-v2-000000-ops-runbook-9b850c71
```

`scripts/build-qwen36-eagle-dataset-from-dump.py` now matches request metadata
exactly first, then by `collector_id + "-"` prefix. Rebuilding into
`dataset-metadata-v2` produced:

- samples saved: `24`;
- samples with metadata: `24`;
- first sample family/prompt ID: `ops-runbook` / `ops-runbook`.

## Training / Offline Eval Smoke

Draft:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagledata-v2-chat-calib-20260704T101119Z/draft-v2-smoke-e2-r3-lr3e5-tok01
```

Training shape:

- epochs: `2`;
- rollout steps: `3`;
- learning rate: `3e-5`;
- token loss weight: `0.1`;
- max len: `128`;
- compact draft: hidden `5120`, intermediate `4096`, heads `16`, KV heads `2`,
  head dim `128`.

Offline eval over the same tiny calibration dataset:

- starts: `512`;
- mean accepted: `0.240234375`;
- acceptance histogram: `{0: 414, 1: 77, 2: 17, 3: 4}`;
- step-1 exact: `0.19140625`;
- step-2 conditional exact: `0.21428571428571427`;
- step-3 conditional exact: `0.19047619047619047`;
- `family_rows` are present and usable.

This is intentionally weak and not an endpoint candidate. It proves the
metadata tooling works; it does not prove that this draft is useful.

## Interpretation

The v2 corpus path is now mechanically sound:

- chat-mode collection works;
- prompt IDs/families survive into `.pt` samples;
- offline eval can identify weak families before endpoint testing.

The 24-prompt smoke draft is much too small and undertrained. Do not run an
endpoint benchmark for this draft.

## Next Action

If EAGLE remains the chosen lane, collect a larger v2 corpus with the same
metadata path:

- keep the final realistic suite isolated;
- use diverse non-final chat prompts;
- split train/held-out by prompt family or source shard;
- require materially stronger held-out `family_rows` before endpoint testing;
- only promote endpoint results after the strict fresh final gate passes.
