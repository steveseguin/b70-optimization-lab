# Laguna M8 gather-sharded Phase-A preflight aborted

Date: 2026-07-24 America/Toronto

Status: terminal infrastructure abort before candidate import, allocation,
primitive execution, timing, or result production. This is not a performance
result and does not authorize Phase B.

## Frozen identity

- approved record: LocalMaxxing `cmrx6p5dv001bo4017hb7sixz` at
  `33.89498511171744 tok/s`;
- candidate XPU-kernel commit:
  `7e6a74026a2a4370abcb7973d28bbc9d1ddd1be6`;
- corrected Stage-0 certificate:
  `data/laguna-m8-gather-sharded-stage0-completion-v2-20260724.json`,
  SHA-256
  `485f423ccbf1f4949cdcdcc08b9d0a47cf2813d1aad5788951d67516fb669a8b`;
- authorization directory:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/authorizations/m8-gather-sharded-52d1c7c-20260724T134430Z`;
- Phase-A authorization SHA-256:
  `d8ec51df4ea69fcf7a34ec827a882e151412dca305f79eeb6266345bc0617cb4`;
- conditional Phase-B authorization SHA-256:
  `478a091c7ba5c38e0e367a272d441f0e00f2c53f0178e82d9be135e873d43ad3`;
- shared common binding:
  `90b0ec0adbd138faac51460553bbe8059c72b0857ff376706debe2b3b8f380cf`.

Both authorization files were frozen to `0444` in a `0555` directory and
passed a separate full validation invocation before Phase A.

## What happened

The coordinator wrote its one-shot consumption marker:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/.laguna-m8-phase-a-preflight-d8ec51df4ea69fcf7a34ec827a882e151412dca305f79eeb6266345bc0617cb4.json
```

That immutable marker records:

```text
status=one_shot_gate_started
no_retry=true
candidate_imported=false
card_root_created=false
```

The coordinator then entered the preregistered 65-second continuous live-idle
gate. The surrounding execution wrapper terminated the process after roughly
11 seconds. The journal contains only the expected self-observing `xpu-smi`
processes during that interval. There was no child card runner, Torch/native
candidate import, XPU allocation or primitive, model load, generation,
campaign root, result, or Phase-B authorization.

Because the process was terminated outside the coordinator, it could not write
its normal pre-campaign failure record. The consumed marker and absence of the
declared campaign root are the durable fail-closed evidence.

## Decision

Do not rerun, repair, or repacket this gather-sharded treatment. Its no-retry
authorization was consumed, even though no candidate work occurred. Classify
the lane as `infrastructure_aborted_pre_candidate`, with no speed or quality
claim.

The approved record remains unchanged. The next research lane is the
previously preregistered runtime-only breakable command graph: retain the
incumbent eager Laguna kernels and BF16 boundaries, capture only target M=8,
leave draft/prefill/widths 1-7 eager, and require raw-byte identity before any
endpoint work.
