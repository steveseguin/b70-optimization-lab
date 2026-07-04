# 2026-07-04 - EAGLE v3 target-architecture/loss screen, no endpoint candidate

## Classification

Diagnostic-only offline drafter screen. This is not endpoint throughput, not a
strict fresh-response result, and not a LocalMaxxing candidate.

## Why this was run

The current valid Qwen27 record remains:

- `webhie/Qwen3.6-27B-int4-AutoRound`;
- AutoRound W4A16 plus runtime INT8 LM-head with BF16 scales;
- one B70, TP1, MTP3/cg8, XPU graph on;
- strict fresh Qwen realistic suite, `cached_tokens=0`;
- `65.27648650325429 tok/s`, LocalMaxxing `cmr5iu3gk00bfq901nidgcana`.

The cheap config and oneDNN Graph routes are closed, so this screen tested the
remaining accepted-token idea: whether a materially different local EAGLE draft
architecture/loss can cross an offline gate before any endpoint validation.

This is intentionally not another endpoint config sweep. It trains/evaluates
offline only, using the non-final v2 chat corpus and a separate calibration
dataset.

## Reproduction

Reusable runner:

```bash
experiments/qwen36-27b-autoround-int4-b70/scripts/run-eagle-v3-target-loss-offline-screen.sh \
  > /tmp/qwen27-eagle-v3-target-loss-offline.out 2>&1
```

Run identity:

- run root:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle-v3-target-loss-offline-20260704T164700Z`;
- compact summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-eagle-v3-target-loss-offline-20260704T164700Z-summary.json`;
- target:
  `/mnt/fast-ai/llm-cache/hf/hub/models--webhie--Qwen3.6-27B-int4-AutoRound/snapshots/f5750c90b3776db658594df5fe8051098226dd8e`;
- train shards:
  `qwen27-eagledata-v2-chat-4gpu-20260704T102338Z/shard-{0,1,2}/dataset`;
- heldout:
  `qwen27-eagledata-v2-chat-4gpu-20260704T102338Z/shard-3/dataset`;
- separate calibration:
  `qwen27-eagledata-v2-chat-calib-20260704T101119Z/dataset`.

Endpoint gate for this diagnostic:

- heldout mean accepted `>= 2.0`;
- heldout step-3 conditional exact `>= 0.65`;
- separate calibration mean accepted `>= 1.5`;
- endpoint and LocalMaxxing are forbidden unless that offline gate passes.

## Variants

Four variants ran concurrently on the four B70s:

1. target draft architecture, rollout3, 4 epochs, lr `1e-5`,
   feature/token loss `0.2/1.0`;
2. target draft architecture, rollout3, 4 epochs, lr `2e-5`,
   feature/token loss `0.5/0.5`;
3. target draft architecture, rollout3, 6 epochs, lr `5e-6`,
   token-only loss;
4. compact 2-layer residual extra layer initialized from the staged v2 draft,
   base frozen, rollout3, 8 epochs, lr `2e-5`, feature/token loss `0.2/1.0`.

The target-architecture variants use the target config fields:

- `hidden_size=5120`;
- `intermediate_size=17408`;
- `num_attention_heads=24`;
- `num_key_value_heads=4`;
- `head_dim=256`.

## Results

Decision: `no_endpoint_candidate`.

| Variant | Heldout mean accepted | Heldout step1 | Heldout step2 cond | Heldout step3 cond | Calib mean accepted | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `compact2-residual-freezebase-r3-e8-lr2e5-feature02-token1-max160` | `0.64697265625` | `0.37646484375` | `0.47341115434500647` | `0.5178082191780822` | `0.4228515625` | no endpoint |
| `targetarch-r3-e4-lr2e5-feature05-token05-max160` | `0.56787109375` | `0.35302734375` | `0.42461964038727523` | `0.43322475570032576` | `0.341796875` | no endpoint |
| `targetarch-r3-e4-lr1e5-feature02-token1-max160` | `0.4677734375` | `0.31201171875` | `0.36619718309859156` | `0.36324786324786323` | `0.29248046875` | no endpoint |
| `targetarch-r3-e6-lr5e6-tokenonly-max160` | `0.43310546875` | `0.29931640625` | `0.35073409461663946` | `0.2744186046511628` | `0.26416015625` | no endpoint |

Best row family split:

- `long-context`: `0.6105769230769231` mean accepted over `1248` starts;
- `support-escalation`: `0.70375` mean accepted over `800` starts.

## Interpretation

The target-architecture drafts did not help. They started from a much weaker
training signal and remained below the compact residual variant. Token-only
training was worst. The best v3 variant (`0.647` heldout, `0.423` calibration)
does not beat the prior stronger v2 screen (`0.695` heldout; separate
calibration around `0.441`) and is far below the offline endpoint gate.

This closes the "just make EAGLE larger / target-shaped / more token-loss
heavy" path for the current small v2 corpus. A future drafter attempt needs a
larger and more diverse isolated corpus, a different architecture, or a
branch/regenerate design that changes the legal drafting process, not another
small hyperparameter sweep on this corpus.

## Decision

No endpoint test. No LocalMaxxing submission. Preserve the runner and compact
summary as a negative result. The next Qwen27 work should either scope a real
top-ID LM-head producer/custom kernel or step back to a new model/larger
drafter data plan; do not repeat compact/target-shaped EAGLE training on this
same v2 dataset without a materially new idea.
