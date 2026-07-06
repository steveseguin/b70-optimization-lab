# Qwen27 EAGLE V4 Large-Corpus Offline Screen: No Endpoint Candidate

Date: 2026-07-06

Model/checkpoint:

- `webhie/Qwen3.6-27B-int4-AutoRound`
- local snapshot:
  `/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e`
- target lane context: current valid strict fresh record is the ReplaySSM
  target-INT8/draft-INT4 recipe at `67.51904968102535 tok/s`
  (`cmr8rg5d900glqr01g4fesy6i`)

Classification: diagnostic-only drafter research. This is not endpoint
throughput, not a fresh-response speed claim, and not a LocalMaxxing result.

## Purpose

Prior compact EAGLE work failed because the local draft did not transfer to
fresh realistic prompts. The best earlier endpoint attempt produced repeated
tokens, and later offline screens on the small v2 corpus stayed far below the
endpoint gate. This run tested whether the blocker was simply too little
non-final chat data by collecting a 384-prompt, four-GPU corpus and screening
larger/longer compact drafts before any endpoint run.

Endpoint gating policy for this lane:

- held-out mean accepted draft tokens must be at least `2.0`;
- held-out step3 conditional acceptance must be at least `0.65`;
- separate calibration mean accepted must be at least `1.5`;
- only then is endpoint validation allowed.

The policy intentionally prevents spending endpoint time on drafts that cannot
plausibly beat the current target-verified MTP3 recipe.

## Corpus Collection

Suite:

```text
experiments/qwen36-27b-autoround-int4-b70/eagle-chat-corpus-v3-suite.json
```

Command:

```bash
cd /home/steve/llm-optimizations
STAMP=20260706T060924Z \
SUITE=experiments/qwen36-27b-autoround-int4-b70/eagle-chat-corpus-v3-suite.json \
SHARD_PROMPTS=96 OUTPUT_TOKENS=160 BASE_PORT=19460 \
bash experiments/qwen36-27b-autoround-int4-b70/scripts/run-eagle-chat-corpus-v2-4gpu.sh
```

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagledata-v2-chat-4gpu-20260706T060924Z
```

Tracked compact summary:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-eagle-v3-corpus-4gpu-20260706T060924Z-summary.json
```

Corpus result:

| Metric | Value |
| --- | ---: |
| Prompts | 384 |
| Shards | 4 |
| Hidden rows | 61,440 |
| Samples | 384 |
| Samples with metadata | 384/384 |
| Continuity breaks | 0 |

Each shard collected 96 prompts and 15,360 usable rows. The collection path is
healthy; data plumbing is not the blocker.

## Offline Screen

Command:

```bash
cd /home/steve/llm-optimizations
STAMP=20260706T062117Z \
V3_ROOT=/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagledata-v2-chat-4gpu-20260706T060924Z \
MAX_STARTS=4096 \
bash experiments/qwen36-27b-autoround-int4-b70/scripts/run-eagle-v4-large-corpus-offline-screen.sh
```

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle-v4-large-offline-20260706T062117Z
```

Tracked compact summary:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-eagle-v4-large-offline-20260706T062117Z-summary.json
```

Held-out split:

- train on shards `0-2`;
- evaluate on shard `3`;
- also evaluate every candidate on the separate calibration dataset
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagledata-v2-chat-calib-20260704T101119Z/dataset`.

## Results

| Variant | Held-out mean | Held-out step1 | Held-out step2 cond | Held-out step3 cond | Calib mean | Endpoint candidate |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `v4-large-residual2-initv2-r3-e5-lr2e5-max160` | 0.717529 | 0.424561 | 0.449109 | 0.536492 | 0.512286 | no |
| `v4-large-r3-e4-lr2e5-i8192-max160-tok01` | 0.701660 | 0.402588 | 0.475440 | 0.562500 | 0.497329 | no |
| `v4-large-r3-e6-lr8e6-i8192-max160-token05` | 0.679443 | 0.397461 | 0.469287 | 0.511780 | 0.451923 | no |
| `v4-large-r3-e4-lr1e5-i12288-max160-tok02` | 0.672607 | 0.395752 | 0.458359 | 0.526245 | 0.459402 | no |

Best row:

- held-out histogram: `{0: 2357, 1: 958, 2: 362, 3: 419}`;
- calibration histogram: `{0: 2449, 1: 843, 2: 281, 3: 171}`;
- held-out mean is `0.717529296875`, far below the `2.0` endpoint gate;
- separate calibration mean is `0.5122863247863247`, far below the `1.5`
  endpoint gate.

## Decision

`decision=no_endpoint_candidate`.

The larger non-final corpus and larger compact drafts did not produce a draft
close to endpoint-worthy acceptance. This closes "more data and hparams on the
same compact EAGLE architecture" for the current Qwen27 lane.

Do not endpoint-test these drafts and do not submit these numbers. They are
diagnostic acceptance measurements only.

## Implications

The current `67.519 tok/s` record is still the valid headline. To move toward
`100+ tok/s`, the credible next work is not another small EAGLE data/hparam
sweep. The remaining routes are:

- exact accepted-prefix GDN/DeltaNet transaction work, likely a low-70s
  cleanup rather than a 100+ path by itself;
- branch/regenerate or another stronger target-matched drafter that raises
  accepted tokens per verifier step materially above the current MTP3 level;
- deeper target-forward/kernel reductions that preserve exact target
  verification.

Future EAGLE/DFlash work needs a materially different drafter architecture,
training target, or branch-regenerate design before endpoint validation.
