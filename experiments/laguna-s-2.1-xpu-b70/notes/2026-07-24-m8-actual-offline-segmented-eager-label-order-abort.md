# Laguna M8 actual-model segmented-eager label-order abort

Date: 2026-07-24 America/Toronto

## Result first

The preregistered v7 actual-model gate completed and durably validated arm A,
then arm B completed generation and wrote a complete raw recorder but failed
closed during aggregation because the analyzer expected `full_topology` two
events too early. Arm C did not start. This is an analyzer-contract bug, not a
model-correctness, runtime-topology, performance, benchmark, payload, or
LocalMaxxing result.

The immutable sealed root is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-b601b7c5e-20260724T180806Z
```

It must never be reused. The approved record remains
`33.89498511171744 tok/s`, LocalMaxxing
`cmrx6p5dv001bo4017hb7sixz`.

## What completed

Arm A (`incumbent-eager`) completed with a canonical immutable driver record
and aggregate evidence. Its returned completion contains 32 tokens, reports
`num_cached_tokens == 0`, finishes by length, and has token-ID SHA-256
`cca03973c1998dfc3255cad724577213ed01cb606cf12eb867358de16f9b9e3f`.
The raw recorder has 60 manifests: 15 on each of four ranks, every one with 201
events, for 12,060 raw events total.

Arm B (`segmented-eager`) completed the model generation path and wrote 60 raw
manifests: 15 per rank, every one with 444 events, for 26,640 raw events total.
The analyzer rejected the first manifest before producing B's aggregate
evidence or driver record. B is therefore unvalidated and must not be compared
with A.

Arm C (`segmented-graph`) did not start. Timing and PTI did not run. No final
A/B/C analysis exists.

## Exact failure and root cause

Every B manifest has the same 444-label sequence and the same single placement
difference from the analyzer's 444-label expectation. The first mismatch is
zero-based event index 437:

```text
index  actual                       analyzer expectation
433    boundary                     boundary
434    all_gather                   all_gather
435    boundary                     boundary
436    all_gather                   all_gather
437    target_hidden_before_logits  full_topology
438    kv_capture_status            target_hidden_before_logits
439    full_topology                kv_capture_status
440    logits_boundary              logits_boundary
```

Label multiplicities match exactly. Runtime ordering is intentional:
`GPUModelRunner` records the target hidden tensor and KV-capture status before
`finish_eligible_forward()` emits `full_topology`. The analyzer incorrectly
placed `full_topology` immediately after the final layer's gather pair.

The safe correction is exact, not permissive: move the analyzer's expected
`full_topology` label after `target_hidden_before_logits` and
`kv_capture_status`, update the synthetic recorder fixture to that same
ordering, and retain strict whole-sequence equality.

## Cleanup and artifact state

The root and completed arm directories are sealed mode `0500`; retained files
are mode `0400`. A has both `driver.json` and aggregate
`evidence/evidence.json`. B has complete raw manifests but neither aggregate
evidence nor `driver.json`. C contains no regular result files.

Pre-arm and both started arms' pre/post idle snapshots passed for all four
devices. Pre/post worker reports are empty. Worker shutdown logs include
grace-period and shared-memory cleanup warnings, but the durable post-worker
and post-idle checks show no remaining model worker or device activity.

## Frozen identities and hashes

- main tooling:
  `b601b7c5efd19cde1a003b67fe8b11ec3f9e29f6`;
- preregistration:
  `a62276dfa`;
- vLLM:
  `e25867aa698f82cbf2fb835e26807078674acebc`;
- XPU kernels:
  `4772f727590c51b72add79350b913d098cf67872`;
- RPC paths: `m8p7-a`, `m8p7-b`, and unused `m8p7-c`;
- raw format: `laguna-m8-raw-evidence-v2`;
- arm A aggregate schema: `laguna-m8-actual-offline-gate-v8`.

Key retained hashes:

```text
3e401782259d12efc08a103d0a49b448594a0ec75ec1bc3d26a9b82b6104a15e  identity.txt
c1eba921ff3e6c0c85681bbf476f6f2b622b5f6ddffa20e5a6b6bb6f05c6bbc0  incumbent-eager/driver.json
4fb8a541553d591b4022e068673b01afef05caf2284a87ada04c195ed7baae30  incumbent-eager/evidence/evidence.json
fd2814b6b94e927045419a26840baafe5bc544683d28011ad307f8692f9f8e56  segmented-eager/stderr.log
```

Machine-readable classification:
`data/laguna-m8-actual-offline-segmented-eager-label-order-abort-20260724.json`.
