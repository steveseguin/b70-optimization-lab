# 2026-07-07: Intrinsic Qwen MTP Adaptation Screen

## Classification

Diagnostic tooling plus one endpoint no-win. No headline result and no
LocalMaxxing submission.

## Why This Was Tried

The current valid Qwen27 record is still the webhie AutoRound INT4 lane with
target INT8 LM head, draft INT4 LM head, ReplaySSM exact GDN handling, MTP3/cg8,
and strict fresh/cached-zero median `68.23626314761921 tok/s`.

Config-only deeper MTP, wrapper LM-head shortcuts, small target-body fusions,
and Ex0bit/DFlash import/adaptation lanes were already closed. The remaining
path to `100+ tok/s` needs more verified tokens per target step, so this screen
tested whether the checkpoint's **intrinsic Qwen MTP drafter** can be adapted
offline while keeping target verification exact.

## New Tools

- `scripts/evaluate-qwen27-intrinsic-mtp-offline.py`
  - standalone offline rollout evaluator for intrinsic MTP;
  - loads `model_extra_tensors.safetensors`, dequantizes only the one MTP
    layer, and compares greedy draft tokens against recorded target next-token
    labels;
  - supports `--draft-lm-head bf16` and `--draft-lm-head int4-dequant`. The
    latter mirrors endpoint `VLLM_XPU_DRAFT_LM_HEAD_INT4` group-128 symmetric
    quantization and then dequantizes for diagnostic PyTorch matmul;
  - diagnostic only, not a throughput benchmark.
- `scripts/train-qwen27-intrinsic-mtp-adapter.py`
  - trains mergeable intrinsic-MTP parameters (`mtp.fc.weight`, optional norms)
    against recorded sequence shards;
  - exports a replacement `model_extra_tensors.safetensors` candidate plus a
    compact `training_summary.json`;
  - target model remains unchanged; endpoint validation is still required.

Both tools accept `qwen36_eagle_sequence_v1` and `qwen36_eagle_sequence_v2`
samples. v2 aux hidden states are ignored for intrinsic MTP.

## Offline Results

Baseline intrinsic MTP over the small v2 calibration set:

- `qwen27-intrinsic-mtp-offline-8192starts-20260707.json`
- starts: `3744`
- BF16-head mean accepted draft tokens: `1.3514957264957266`
- conditional exact: `[0.7345, 0.5633, 0.4913]`
- conditional top-5: `[0.9354, 0.7953, 0.7211]`

First small FC-only sweep on v2 showed the lane was trainable:

- best: `qwen27-intrinsic-mtp-fc-lr1e5-3120s-e3-20260707`
- heldout mean accepted draft tokens: `1.3381410256410255 -> 1.4407051282051282`

The v2-trained candidate generalized on v6 shard 3 under BF16-head offline
evaluation:

- base: `1.34130859375`
- v2-trained candidate: `1.43896484375`

Direct v6 training then produced a larger offline lift. Best run:

- `qwen27-intrinsic-mtp-v6-fc-lr2e5-16k-e1-20260707`
- scope: `mtp.fc.weight` only
- train: v6 shards 0-2, `16384` random starts
- heldout: v6 shard 3, `8192` random starts
- BF16-head heldout: `1.2490234375 -> 1.505859375`
- BF16-head sequential v6 shard 3: `1.34130859375 -> 1.6302490234375`
- INT4-dequant sequential v6 shard 3: `1.334716796875 -> 1.620849609375`

This looked strong enough for one endpoint screen.

## Endpoint Screen

Candidate overlay:

```text
/mnt/fast-ai/llm-cache/hf/local/qwen36-27b-autoround-int4-webhie-mtp-v6fc-lr2e5-20260707
```

The overlay uses absolute symlinks to the original webhie snapshot and replaces
only `model_extra_tensors.safetensors`. The first overlay attempt copied the
snapshot's relative symlinks into a different directory, breaking `config.json`
resolution; the overlay was rebuilt with absolute symlinks.

Strict fresh speed screen:

- summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-intrinsic-mtp-v6fc-lr2e5-speed-screen2-candidate-summary-20260707T063023Z.json`
- fixed realistic suite, each prompt once, `cached_tokens=0`, quality skipped
  for screening
- median tokens 1-100 after TTFT: `67.40254598645147 tok/s`
- p10: `59.30990539774993`
- mean: `65.84269491557801`
- TTFT median: `488.11853490769863 ms`
- result: **no win** versus current valid `68.23626314761921 tok/s`

No quality run was spent because the speed screen did not beat the current
record.

## Endpoint Trace Explains The No-Win

Trace run:

- candidate summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-intrinsic-mtp-v6fc-lr2e5-branchtrace-candidate-summary-20260707T064014Z.json`
- trace summary:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-intrinsic-mtp-v6fc-lr2e5-branchtrace-summary-20260707.json`
- trace file:
  `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/candidates/qwen27-intrinsic-mtp-v6fc-lr2e5-branchtrace-cow-trace.jsonl`

Candidate trace over `220` scheduled verifier rows:

- mean raw visible tokens: `2.577272727272727`
- mean accepted draft prefix: `1.5772727272727274`
- full accept rate: `30.45%`
- draft-prefix histogram: `{0: 50, 1: 60, 2: 43, 3: 67}`

This is **worse** than the prior current-recipe branch trace:

- mean raw visible tokens: `2.6727`
- mean accepted draft prefix: `1.6727`
- full accept rate: `39.09%`

Conclusion: the v6 offline acceptance lift did not transfer to the fixed
realistic strict suite. The endpoint no-win is not explained by BF16-vs-INT4
offline head mismatch; the candidate improved both BF16 and INT4-dequant
offline v6 acceptance, but degraded accepted-prefix behavior on the actual
strict-suite distribution.

## Decision

Do not promote or LocalMaxxing-submit this candidate.

Keep the scripts: they are useful infrastructure, but treat the current offline
corpus as insufficiently predictive for strict-suite endpoint acceptance.

Do not repeat the same v6 `mtp.fc.weight` training loop as a speed candidate.
Future stronger-drafter work needs one of:

1. a better non-final-prompt calibration corpus that matches the fixed
   realistic suite distribution without training on the final gate prompts;
2. endpoint-trace-driven validation as the acceptance arbiter before any speed
   run;
3. multi-step/k>3 training only after a candidate improves strict-suite accepted
   prefix, because current MTP3 cannot reach `100+ tok/s` unless accepted tokens
   per target step rises materially;
4. a deeper graph-safe branch/regenerate or target-tail mechanism if accepted
   prefix remains near `1.6`.

Large exported `model_extra_tensors.safetensors` files are intentionally ignored
by Git (`*.safetensors`). Preserve compact `training_summary.json`, evaluator
JSON, endpoint summaries, and this note in Git; keep large candidate tensor
files local unless a specific one becomes a promoted reproduction artifact.
