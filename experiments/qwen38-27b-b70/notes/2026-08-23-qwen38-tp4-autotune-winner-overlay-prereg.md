# TP4 historical autotune-winner overlay preregistration

Date: 2026-08-23. This is a bounded performance-preservation experiment on
the newest available upstream image. It does not authorize lowering any TP4
frontier, copying an old compiled cache, or treating one fast TP4 capture as a
replicated result.

## Hypothesis

The dev1102 to dev1120 package-version change invalidated the outer compile
namespace even though all four TP4 computation graphs, compiler identity,
cache-key environment, and Triton candidate sets were unchanged. Fresh tuning
then chose different winners for 78/152 records. Seeding only the historical
`.best_config` decisions before a fresh current-runtime compile should improve
TP4 decode while retaining newest upstream code and binaries.

## Frozen arms

1. One seeded-fresh TP4 diagnostic arm: GPUs 0,1,2,3; MTP0; F16 KV; 32K;
   XPU Graph; memory utilization 0.60; the existing 25-prompt ignore-EOS
   diagnostic contract.
2. Only if arm 1 meets its gate, one exact-cache natural-EOS replay A with the
   full TP4 baseline quality battery.
3. Only if replay A passes quality and the lower historical strict floor, one
   exact-cache natural-EOS replay B. This repeat is mandatory because the
   stock `a3561ef8` cache swung from 71.900199 to 71.245742 tok/s.

No extra fresh compile, tuning search, mixed bundle, per-kernel cherry-picking,
or fourth arm is authorized.

## Fail-closed mechanism gates

- The registry's current linux/amd64 nightly manifest must still be
  `ad7d8e8e...df41a`; otherwise stop and remap against the actual newest code.
- The target image/source/package, current AOT and outer namespaces,
  code/compiler/config/environment hashes, and all four computation-graph
  hashes must match the tracked metadata.
- The seed must contain exactly the tracked 152 regular `.best_config` files,
  no symlinks or other artifacts, and the exact tracked manifest digest.
- Startup must compile and save a fresh AOT function. Direct loading of an old
  AOT model is a failure.
- After compilation and after the full workload, the seed bundle must remain
  byte-identical and no additional `.best_config` may exist.
- All normal image/model/graph/canary/token-ID/cache-zero gates remain active.
- Each replay must leave the entire sealed cache byte-identical.
- The wrapper must rehash after the inner runner returns and the container is
  fully removed, then compare that outer-final manifest across every arm.

## Frozen performance and quality interpretation

- Diagnostic success requires at least `71.5488 tok/s`, the lower historical
  diagnostic capture. A lower result is preserved as a negative/partial and
  blocks both strict arms.
- Replay A must pass the full quality/baseline/needle contract and measure at
  least `71.29326283364946 tok/s`, the lower historical strict capture, before
  replay B is allowed.
- Stable full recovery requires both strict replays to be at least
  `71.29326283364946 tok/s` and at least one to be at least
  `71.39843006187554 tok/s`.
- A faster single result that fails the repeat rule is a captured high, not a
  promoted record.
- Preserve the stock rolling-runtime `71.900199 tok/s` captured high as a
  separate field even if a lower but stable overlay pair passes these floors.
- Any correctness, identity, compilation, cache, or quality failure
  quarantines the overlay regardless of speed.

The inner runner's `final.status=pass` covers identity, benchmark, quality,
and cache-runner gates. The outer `overlay-*.status` files and wrapper exit 5
control performance/stability promotion; a speed exit 5 is not a quality-red
result.

The preserved bundle and identity gates are under
[`autotune-winner-overlays/tp4-e9d1398-best-config`](../autotune-winner-overlays/tp4-e9d1398-best-config/README.md).

## Closure

All three authorized arms completed without an identity, correctness, quality,
or cache-integrity failure. Fresh diagnostic measured `71.722545`; strict A/B
measured `71.352872 / 71.454271`. Both strict arms cleared the lower floor and
B cleared the high bar, so the exact `a3561ef8` official-image overlay profile passed the
frozen stable-full-recovery rule. No fourth arm is authorized. See the
[result note](2026-08-23-qwen38-tp4-autotune-winner-overlay-result.md) and
[structured result](../data/2026-08-23-qwen38-tp4-autotune-winner-overlay-result.json).
