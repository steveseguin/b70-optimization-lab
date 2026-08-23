# TP2 historical autotune-winner overlay preregistration

Date: 2026-08-23. This is a bounded performance-recovery experiment on the
newest qualified upstream image. It does not authorize lowering the old TP2
frontier or copying an old compiled cache.

## Hypothesis

The dev1102 -> dev1120 package-version change invalidated the outer compile
namespace even though the Qwen computation graphs, compiler identity,
cache-key environment, and Triton candidate sets were unchanged. Fresh tuning
then chose different winners for 46/78 TP2 records. Seeding only the historical
`.best_config` decisions before a fresh current-runtime compile should recover
the lost decode rate while retaining newest upstream code and binaries.

## Frozen arms

1. One seeded-fresh TP2 diagnostic arm: GPUs 2,3; MTP0; F16 KV; 32K; XPU
   Graph; memory utilization 0.90; the exact existing 25-prompt ignore-EOS
   diagnostic contract.
2. Only if arm 1 meets all gates, one exact-cache replay with natural EOS and
   the full TP2 baseline quality battery.

No extra tuning search, mixed bundle, per-kernel cherry-picking, or second
fresh compile is allowed inside this experiment.

## Fail-closed mechanism gates

- The registry's current linux/amd64 nightly manifest must still be
  `ad7d8e8e...df41a`; otherwise stop and remap against the actual newest code.
- The target image/source/package, current AOT and outer namespaces,
  code/compiler/config/env hashes, and both computation-graph hashes must match
  the tracked metadata.
- The seed must contain exactly the tracked 78 regular `.best_config` files,
  no symlinks or other artifacts, and the exact tracked manifest digest.
- Startup must compile and save a fresh AOT function. Direct loading of an old
  AOT model is a failure.
- After compilation, the seed bundle must still be byte-identical, and no
  additional `.best_config` record may exist.
- All normal image/model/graph/canary/token-ID/cache-zero gates remain active.

## Frozen performance and quality interpretation

- Diagnostic success requires conventional median decode at least
  `48.8301 tok/s` and at least 0.25% over the latest default control
  `48.64759224153825 tok/s`. The historical floor is the stronger numerical
  gate here.
- A result above the latest control but below the historical floor is a partial
  recovery: preserve it, do not promote, and do not run the strict arm.
- A result at or below the latest control falsifies the simple winner-overlay
  recovery hypothesis.
- Full recovery requires the conditional strict arm to meet
  `49.01965141150585 tok/s`, pass the full quality/baseline/needle battery, and
  leave the sealed cache byte-identical.
- Any correctness, identity, compilation, cache, or quality failure
  quarantines the overlay regardless of speed.

The preserved bundle and identity gates are under
[`autotune-winner-overlays/tp2-e9d1398-best-config`](../autotune-winner-overlays/tp2-e9d1398-best-config/README.md).

Closed by the
[two-arm result](2026-08-23-qwen38-tp2-autotune-winner-overlay-result.md):
diagnostic pass/new high; strict quality pass but frozen speed near-miss; no
full promotion.
