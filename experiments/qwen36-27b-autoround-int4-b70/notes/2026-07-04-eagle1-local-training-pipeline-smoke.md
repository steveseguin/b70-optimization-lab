# 2026-07-04: Qwen27 EAGLE1 local training pipeline smoke

## Status

Diagnostic-only pipeline bring-up. No LocalMaxxing submission, no headline
throughput claim, and no final-suite tuning.

Current promoted Qwen27 record remains
`65.27648650325429 tok/s` for `webhie/Qwen3.6-27B-int4-AutoRound` with runtime
INT8 LM-head BF16 scales, MTP3/cg8, strict cold Qwen realistic suite, and
`cached_tokens=0`.

## Why

The quick LM-head/source lanes are closed no-win, and acceptance tracing showed
that better target-matched drafting is one of the remaining credible paths. The
existing EAGLE1 scripts were not yet usable for Qwen27:

- `train-qwen36-eagle1-draft.py` defaulted to hidden size `2048`, while Qwen27
  target hidden states are `5120`.
- No-spec hidden dumps in async scheduling produced hidden states but
  `valid_sampled_token_ids=[]`, so the dump hook wrote no shards.
- After adding sampled-token fallback, async no-spec shards still had
  `current_token_ids=-1` and `positions=-1`, so the dataset builder rejected
  every row.

## Changes

Repo scripts:

- `scripts/train-qwen36-eagle1-draft.py` now infers target-facing dimensions
  from the target config and validates dataset/embedding/head shapes before
  constructing the draft.
- `scripts/build-qwen36-eagle-dataset-from-dump.py` now has explicit fallback
  flags for async no-spec dumps:
  `--allow-missing-current-token-ids` and
  `--reconstruct-positions-from-num-tokens`.

Local vLLM source patch snapshot:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-active-stack-with-qwen27-eagle-dump-fallback-20260704.patch
```

That snapshot includes the active Qwen/GDN stack plus the new EAGLE dump
fallback/debug additions in `vllm/v1/worker/gpu_model_runner.py`.

## Collection

Run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagledata-nospec-calib-fallback-20260704T074631Z
```

Config:

- target: `webhie/Qwen3.6-27B-int4-AutoRound`, snapshot
  `f5750c90b3776db658594df5fe8051098226dd8e`;
- no MTP (`QWEN36_27B_ENABLE_MTP=0`);
- one B70 (`GPU_INDEX=1`);
- XPU graph on;
- runtime INT8 LM-head BF16 scales on;
- 16 generated diagnostic prompts from
  `scripts/collect-qwen36-eagle-hidden-corpus.py`;
- final Qwen realistic suite was not used.

Result:

- collection prompts: `16`;
- total generated output tokens: `1536`;
- hidden dump shards: `1536`;
- dataset rows usable: `1536`;
- dataset samples: `16`;
- continuity matches: `1520`;
- continuity breaks: `0`;
- reconstructed current-token rows: `1536`;
- reconstructed position rows: `1536`.

Compact packet:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-eagle1-pipeline-smoke-20260704.json
```

## Training smoke

Small dataset:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagledata-nospec-calib-fallback-20260704T074631Z/dataset-small
```

Command shape:

```bash
ZE_AFFINITY_MASK=1 ONEAPI_DEVICE_SELECTOR=level_zero:0 \
/home/steve/.venvs/vllm-xpu/bin/python scripts/train-qwen36-eagle1-draft.py \
  --dataset-dir <run-root>/dataset-small \
  --target-model /mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e \
  --out-dir <run-root>/draft-smoke-compact \
  --epochs 1 --batch-size 1 --max-len 16 \
  --device xpu:0 --train-dtype bfloat16 --export-dtype bfloat16 \
  --intermediate-size 4096 --num-attention-heads 16 \
  --num-key-value-heads 2 --head-dim 128
```

Result:

- dataset samples: `4`;
- inferred hidden size: `5120`;
- compact draft shape:
  `hidden=5120`, `intermediate=4096`, `heads=16`, `kv_heads=2`,
  `head_dim=128`, `vocab=248320`;
- final smoke metrics: `loss=1.4799`, `feature_loss=1.1016`,
  `token_loss=3.7836`, `top1=0.4000`, `top3=0.5333`.

## Offline evaluator smoke

`scripts/evaluate-qwen36-eagle-draft-offline.py` ran against the 4-sample
smoke draft:

- starts: `56`;
- mean accepted: `0.5893`;
- acceptance histogram: `{0: 29, 1: 22, 2: 4, 3: 1}`;
- first-step exact: `0.4821`;
- first-step top3: `0.5714`.

This is only a feasibility sanity check. The tiny four-sample draft is not a
credible endpoint drafter and should not be benchmarked as a speed candidate.

## Next

1. Keep final Qwen realistic prompts isolated from drafter training.
2. Collect a larger held-out training corpus now that the dump path works.
3. Train compact draft variants with fixed validation splits and offline
   acceptance tracking before any vLLM endpoint EAGLE attempt.
4. If offline acceptance does not beat the built-in MTP drafter materially, stop
   this lane and return to producer-side LM-head/top-ID work.
5. If offline acceptance is strong, test endpoint EAGLE only with the strict
   fresh-response gate, `cached_tokens=0`, and exact target verification.
