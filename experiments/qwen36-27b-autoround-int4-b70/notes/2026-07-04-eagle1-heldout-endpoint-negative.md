# 2026-07-04: Qwen27 local EAGLE1 held-out training and endpoint negative

## Status

Diagnostic lane closed for the current local EAGLE1 draft. Do not promote,
submit to LocalMaxxing, or use as a headline throughput result.

The current valid Qwen27 record remains `65.27648650325429 tok/s` for
`webhie/Qwen3.6-27B-int4-AutoRound` with runtime INT8 LM-head BF16 scales,
MTP3/cg8, one B70, strict fresh Qwen realistic suite, and `cached_tokens=0`.

Compact packet:

```text
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-eagle1-heldout-endpoint-negative-20260704.json
```

Raw run root:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagledata-4gpu-trainheldout-20260704T075504Z
```

## 4-GPU corpus build

The dump path is now mechanically sound at useful scale:

- four independent no-spec vLLM replicas, one per B70;
- `32` diagnostic prompts per shard, `128` generated tokens per prompt;
- total prompts: `128`;
- total generated tokens / usable hidden rows: `16384`;
- dataset samples: `128`;
- continuity breaks: `0`;
- final Qwen realistic-suite prompts were not used for training.

This is useful infrastructure. Keep it as the current proof that no-spec hidden
dumping, async sampled-token reconstruction, and dataset building work.

## Held-Out Offline Training Screen

Training used shards 0-2 and held out shard 3. The baseline compact draft
improved from the tiny smoke, and rollout training improved it materially:

| Draft | Mean accepted | Hist 0/1/2/3 | Step1 exact | Step2 conditional | Step3 conditional |
|---|---:|---|---:|---:|---:|
| baseline e2 r1 max64 | `1.0605` | `369/368/143/144` | `0.6396` | `0.4382` | `0.5017` |
| e4 r2 max128 continued | `1.8213` | `162/187/347/328` | `0.8418` | `0.7831` | `0.4859` |
| **e6 r3 lr3e-5 token0.1** | **`2.1016`** | **`153/129/203/539`** | **`0.8506`** | **`0.8519`** | **`0.7264`** |

Best draft:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagledata-4gpu-trainheldout-20260704T075504Z/draft-e6-r3-lr3e5-tok01
```

The best offline acceptance looked plausible enough to attempt endpoint
integration, but this was still calibration-corpus validation, not final-suite
proof.

## Endpoint Integration Result

Config:

- target:
  `webhie/Qwen3.6-27B-int4-AutoRound` snapshot
  `f5750c90b3776db658594df5fe8051098226dd8e`;
- one B70, TP1, `MAX_MODEL_LEN=2048`, `MAX_NUM_BATCHED_TOKENS=1024`;
- XPU graph PIECEWISE, `max_cudagraph_capture_size=8`;
- runtime INT8 LM-head with BF16 scales;
- EAGLE `num_speculative_tokens=3`;
- promote-source GDN env pair kept on to match the current record family.

Loader notes:

- A converted copy with `layers.0.* -> layers.64.*` failed with
  `KeyError: layers.64.mlp.down_proj.weight`.
- The original trained checkpoint with `layers.0.*` loaded correctly. vLLM's
  nested draft loader strips the outer prefix before calling the EAGLE body
  loader, so no layer-index conversion is needed.
- vLLM shared the target `embed_tokens` and `lm_head` because the local draft
  intentionally omits them.

OpenAI smoke:

- path:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagledata-4gpu-trainheldout-20260704T075504Z/eagle-endpoint-smoke.json`;
- `pass=true`;
- `cached_tokens=0`;
- exact visible content: `{"answer": 42, "unit": "widgets"}`.

Strict fixed Qwen realistic suite:

- path:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagledata-4gpu-trainheldout-20260704T075504Z/qwen27-local-eagle1-e6r3-cg8-realistic128-chat-tokenids-qwensuite.json`;
- `cached_tokens=0` on all 12 requests;
- final gate failed / invalid:
  `completion_tokens_at_least_metric_window=false`,
  `metric_token_id_events_at_least_window=false`;
- only 10 rows had enough token-id events for the primary tokens-1-100 metric;
- measurable-row median `tok_s_1_100_after_ttft` was only `21.7408 tok/s`;
- quality was bad: repeated-token corruption appeared on fixed-suite prompts,
  including `Cooperativa Cooperativa ...` and `the, the, the ...` loops.

This is not a variance issue and not a cache-cheating issue. It is a failed
draft/generalization or EAGLE endpoint-quality issue.

## Conclusion

The local EAGLE1 pipeline is valuable, but the current trained draft is not a
usable speed lane. Offline acceptance on the calibration corpus did not transfer
to the fixed realistic suite, and endpoint quality failed before speed could be
considered.

Do not repeat this exact endpoint attempt. If EAGLE is revisited, first collect
a larger and more diverse non-final training corpus, add a stricter held-out
suite that resembles production prompts while still keeping the final benchmark
suite isolated, and require held-out quality/anti-repetition checks before any
endpoint run.

Near-term Qwen27 speed work should return to the record-family bottlenecks:
reducing LM-head/logits call cost, reducing LM-head row count, or improving
accepted tokens per target verifier step with exact target verification.
