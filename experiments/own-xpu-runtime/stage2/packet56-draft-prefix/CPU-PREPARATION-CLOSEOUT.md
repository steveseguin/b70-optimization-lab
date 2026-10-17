# Packet56 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can a fixed prefix of the existing shared draft head reduce serial proposal
time while preserving target output? Packet56 builds on packet49d's Unsloth
IQ3 compressed-model lane, with arithmetic `iq3-p49-split32-v1`, the same
packet49 target oracle, two B70 cards and full BF16 KV. Preparation on
October17 uses CPU work only; this closes preparation, not the optimization.

## Outcome

The independent calibration fixes N=91,392. Host numerical/controller gates
pass, including every retained prefix logit at full production geometry.
The target-model correctness and performance outcome remains pending the
coordinator's device windows. No new measured model speed is claimed.

## What worked

The same p33 expanded-Q6 row kernel accepts a smaller row count. The same
round2 argmax accepts the corresponding input extent. The target's buffer,
head and controller remain unchanged. Two fresh CPU processes agree on
182,784 prefix-logit bytes and ordinary excluded-token miss handling.
Independent text selection covers 99.512245% without using benchmark outputs.

## What failed or remains uncertain

Retained production draft profiling cannot isolate the head and layer;
the roughly52% head share is an operator proxy. Generated-token exclusion,
actual acceptance, device row scaling and full-model speed are unmeasured.
Review found that a strict shared-head guard would reject the existing
isolated KD capture; it now permits that diagnostic's original head while
requiring sharing in production. KD compares only computed prefix logits.
Posting also rechecks the current record floor to reject stale queues.

## Evidence and patches

- [Independent rule](calibration/preregistration.json) and
  [sealed selection](calibration/selection.json).
- [CPU gates](p56-cpu-gates.json), [review](REVIEW-INDEPENDENT.md),
  [timing analysis](analysis/README.md) and [runtime delta](mtp.hpp).
- [Parent identity](parent-binding.json), [source manifest](base-source-manifest.json)
  and [portable overlay](p56_portable_overlay.py).
- [Artifact retention and restore](ARTIFACT-RETENTION.md).

## When to revisit

The coordinator runs two fresh head K windows and the complete unchanged
target-oracle chain using [WINDOW.md](WINDOW.md). Keep the prefix fixed even
if benchmark coverage or timing is disappointing. If49d fails, export the
same overlay to a separate49c copy and rebuild/requalify there; never edit a
sealed parent or reuse this packet's seal for a different base.
