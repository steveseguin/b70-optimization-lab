# Lane-aware chain admission — CPU preparation closeout

<!-- campaign-closeout -->

## Question and identity

Can future two-card full chains admit a masked cards-2/3 screen during
exactness work while keeping timing windows exclusive? This October 17
preparation uses packet61-style Python wrappers and screen v3, with reference
sources pinned in [reference.json](reference.json). No model weights, kernels,
arithmetic, KV settings or oracle were changed.

## Outcome

Prepared for adoption in new wrappers before their first seals. All 55 CPU
tests pass. Native device isolation, full-chain acceptance and useful overlap
remain unmeasured. Packet61x and existing seals were not edited by this task.

## What worked

A shared admission lock closes the flag/start race. Timing windows publish
the B hold before waiting for the current screen. PID/start-tick checks and
fresh private homes support masking. Final proof is bound to the complete
original window receipt. The future B wrapper can start under a proven live
A exactness drain permit while keeping the existing actual drain gate.

## What failed or remains uncertain

The first dangling-flag test used a group-writable mock directory and correctly
hit the root-permission check; its fixture was corrected. A mutable-reference
patch check encountered concurrent coordinator changes; pinning reference
bytes fixed that test dependency without touching their files.

Review found and fixed marker/lock cleanup, private-home, receipt-binding and
drain-admission races. Native fixtures can finish between fdinfo samples and
then refuse for missing proof. Holding a drain permit for the whole window can
delay B's drain and consume its unchanged watchdog. CPU tests cannot settle
those device behavior and duration questions.

## Evidence and patches

- [CPU receipt](evidence/cpu-validation.json) and [test log](evidence/tests.log).
- [Chain patch](integration.patch), [B wrapper patch](screen-integration.patch)
  and [read-only recipe renderer](recipe.py).
- [Protocol and adoption guide](README.md), including the shared directory,
  stale-owner handling, source closure and existing admission floors.
- [Task note](../../../../notes/2026-10-17-own-runtime-lane-aware-chain.md).

## When to revisit

The coordinator adopts both wrappers under new seals, then measures native
masking, every chain gate and bounded overlap. If drain waiting prevents useful
overlap, investigate a native fixture exit barrier as a separate candidate;
do not weaken the gate or silently extend a watchdog.
