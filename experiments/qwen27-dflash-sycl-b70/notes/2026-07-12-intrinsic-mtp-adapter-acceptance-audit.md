# 2026-07-12 intrinsic-MTP adapter acceptance audit

## Classification

Blocked pre-integration audit. No endpoint run, quality claim, throughput
claim, or LocalMaxxing submission.

## Required gate

The current llama.cpp Q4_0 MTP3 strict suite emits `2.7881` tokens/cycle and
accepts `59.64%` of draft candidates. The requested acceptance route needs
roughly `>= 3.1` emitted tokens/cycle (`>= 69%` draft acceptance) before an
endpoint trial is worthwhile.

## What is already available

The existing offline trainer and evaluator are mature:

- `scripts/train-qwen27-intrinsic-mtp-adapter.py`;
- `scripts/evaluate-qwen27-intrinsic-mtp-offline.py`;
- static position-FC, low-rank position-adapter, prefix-survival, margin, and
  conditional-prefix objectives;
- a decode-only fixed-suite acceptance corpus and matched shared-checkpoint
  control.

The closest safe calibration experiment has therefore already been executed,
including four-GPU matrices. On 1,488 decode-only starts, the shared checkpoint
accepted `1.338710` drafts/start. The best mergeable candidate (position-FC,
margin weight `0.03`) reached only `1.516801`, a gain of `0.178091`. This was
below the predeclared `+0.205609` endpoint-trial gate and below the current
request's stronger `>= 3.1` visible-token requirement. Other tested objective
weights, conditional-prefix training, position adapters through rank 512, and
larger intrinsic-block scopes did not clear their offline gates.

## Why it cannot be safely applied to the active lane

These artifacts replace Hugging Face/vLLM
`model_extra_tensors.safetensors` for the webhie AutoRound checkpoint. The
active single-B70 lane is llama.cpp with the independently distributed
`unsloth/Qwen3.6-27B-MTP-GGUF` Q4_0 file. llama.cpp currently has no runtime
overlay loader for these position-FC/position-adapter tensors, and no verified
converter/merge contract establishes that the webhie MTP tensors are identical
to the embedded GGUF MTP tensors. Applying the overlay would therefore violate
the preserve-base-model and no-target-quality-loss requirements.

The reused 12-prompt decode corpus is also a selection set, not a fresh final
gate. Further tuning against it would be leakage rather than credible evidence.

## Decision

Do not endpoint-test or merge the existing adapter candidates into the active
GGUF. This route is genuinely blocked until both of the following exist:

1. target-owned hidden-state/next-token trajectories collected from the exact
   active GGUF on a disjoint calibration suite; and
2. a verified GGUF MTP overlay/merge path with tensor-identity checks and a
   byte-preserved base target.

Even after those prerequisites, the existing FC/adapter architecture is
unlikely to reach the requested acceptance gate: its strongest decode-only
gain was `+0.1781` accepted drafts/start, while the request needs approximately
`+0.312` emitted tokens/cycle over the current llama.cpp baseline. A materially
stronger drafter architecture or target-tail branch/regenerate mechanism is
more credible than repeating the closed FC/loss sweep.
