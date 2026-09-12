# MiniCPM5-2B native BF16 baseline on one B70

Status: preregistered, not yet qualified. User selected a new downloaded model
for setup and a lossless baseline before optimization; this lane selects the
official MiniCPM5-2B checkpoint, 2,516,756,480 BF16 parameters.

## Baseline identity and meaning of lossless

- Model: `openbmb/MiniCPM5-2B`, revision `12a3808a956f869c767195e9266b59c4d21d92e2`.
- Original BF16 checkpoint remains on the external 8TB drive at
  `/mnt/raid-models/models/intake-20260912/openbmb--MiniCPM5-2B`.
- Transformers current-main source `415e6d2f596ef2bd44fdee4261799200a7fc02bf`;
  PyTorch latest released XPU wheel `2.14.0+xpu`. Dedicated environment:
  `/home/steve/.venvs/minicpm5-baseline-20260912`.
- Standard Llama implementation, native BF16 parameters/KV, eager attention,
  no compilation, no quantization, no draft or speculative decoding. TP1/c1.
- Explicit official chat template with `enable_thinking=True`, BOS once,
  stop IDs1/130073, greedy test mode and seed7429. Greedy is an oracle setting;
  the publisher's sampled application defaults remain separately documented.

This establishes an unchanged-weight reference for future comparisons. It does
not assert that BF16 equals FP32 arithmetic, that every backend yields the same
tokens, or that finite testing proves universal losslessness. Future optimizations
must preserve this declared target and pass exact tested output/quality gates.
No Qwen4B superiority or 200tok/s claim is made by selecting this baseline.

## Preregistered execution

Read [quality-preregistration-v1.md](quality-preregistration-v1.md) and
[official model audit](notes/model-audit.md). All model files are size/hash
verified before every model load. Use current runtime without lab overlays.

The guarded campaign checks all four cards before/after, holds host and device
locks, checks render-node ownership and journal faults, and never starts a
service or changes an existing runtime. Stages:

1. Fresh model process: short native-thinking arithmetic smoke must answer4.
2. Fresh baseline A: ten unique realistic prompts at the unchanged512 cap,
   six2048-cap arithmetic/JSON/copy canaries, separate2048-cap quality
   completions for truncated realistic rows, roughly2K/8K needle screens,
   same-process full canary/realistic/context repeats after context workloads,
   six uncached first-eight-token diagnostics, and teacher-forced logit checks.
3. Fresh baseline B repeats the complete A workload with identical identity.
4. Analyze all full token streams, declared machine checks, timing and manual
   practical-quality rubrics. A failed gate stays failed; no prompt replacement
   or precision change is authorized to manufacture a pass.

The separate completion-quality rows are excluded from performance statistics;
their first512 tokens must match the original capped run. Same-prompt repeats
are correctness evidence only. Every request starts without prior request KV.
The per-token streamer verifies one token event per emitted ID and synchronizes
the device before timestamping; rates include measurement overhead. Conventional
first100 rate is99/(t100-t1), aggregated by class. Short rows cannot be dropped.

Teacher-forced logit checks compare the first eight steps of all six canaries,
recording numeric errors, top1 IDs and margins on the same eager BF16 backend.

## Reproduction

Dependencies and exact source are recorded in `runtime-freeze.txt`. No package
installation is performed by a run. From repo root, choose new output paths:

```bash
python3 experiments/minicpm5-2b-b70/device-guard.py \
  --out /home/steve/minicpm5-baseline-20260912/guard-run1 --timeout 15000 -- \
  /home/steve/.venvs/minicpm5-baseline-20260912/bin/python \
  experiments/minicpm5-2b-b70/campaign.py \
  --out /home/steve/minicpm5-baseline-20260912/campaign-run1
```

Full-model processes exit after their stage. Shared Qwen/Flash-Next source,
weights, runtime images and queued scripts remain preserved. Build/test logs,
failed attempts and exact source hashes belong in this lane's data/notes.
