# Qwen27 Active Source Stack Checkpoint

Date: 2026-07-04

Status: preservation checkpoint before the next optimization lane.

## Context

After closing the EAGLE v2 and 32K MBT service screens, the optimization repo
was clean and pushed at commit `c595d454a`. The active runtime source trees used
for Qwen27 experiments are intentionally dirty:

- `/home/steve/src/vllm`;
- `/home/steve/src/vllm-xpu-kernels`.

These are not disposable changes. They contain the current Qwen/GDN/INT8-LM-head
experiment stack that supports the strict Qwen27 record family and diagnostic
instrumentation.

## Patch Snapshots

To avoid losing the active source base before the next lane, snapshots were
captured into the optimization repo:

```text
patches/qwen36-27b-autoround-int4-b70/active-vllm-stack-before-next-lane-20260704.patch
patches/qwen36-27b-autoround-int4-b70/active-vllm-xpu-kernels-stack-before-next-lane-20260704.patch
```

These are source-state snapshots only. They are not a new benchmark result and
must not be submitted to LocalMaxxing.

## Next-Lane Constraint

Two read-only audits agreed that the obvious remaining Qwen27 decode bottleneck
is dense LM-head/logits materialization and accepted-token efficiency, not
sampler plumbing or more environment/config sweeps. Do not repeat closed lanes
such as MTP4/MTP5, scheduler-only adaptive depth, hot-vocab draft top-1,
standalone full-vocab top-1 kernels that lose to oneDNN, DFlash all-sliding, or
EAGLE endpoint sweeps.

The next source experiment should have a hard stop criterion:

- exactness versus dense logits / target verification;
- strict fresh-response validation with `cached_tokens=0` before any promotion;
- clear speed threshold outside known variance before considering
  LocalMaxxing.
