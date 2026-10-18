# Packet130 CPU preparation — closeout

<!-- campaign-closeout -->

## Question and identity

Can rank0 service the verified target-head suffix at the first completed
speculative layer boundary, while preserving bundle7 arithmetic, work order,
miss rollback and `iq3-p49-split32-v1`? This is the October 18 CPU preparation
from frozen packet124c, 24/24 layers, 46,080 suffix rows and BF16 KV. Only
`suffix_schedule` switches between production and layer-interleave.

## Outcome

CPU preparation passes all 18 final stages. No GPU executed. Full-model device
identity, speed, reduced rank1 wait and rank0 completion-time cost are pending.
The candidate is not adopted and no measured speed improvement is claimed.
The two sealed lane-B proposals pass a temporary queue plan.

## What worked

The same suffix commands run at a completed layer boundary, consume a bound
verified hidden vector once, and preserve the late-arrival fallback. Newly early
verification does not shorten the current speculative half. Both compilers pass
fresh logit/argmax, controller and private-reset checks. Complete miniature
state and token bytes match the parent through schedule switches and fresh
GNU/Intel processes. Full-size capture bytes and allocation identities remain
unchanged. All launch, queue, drain, teardown and limit gates pass.

## What failed or remains uncertain

The inherited v5 drain helper failed the clock-crossing negative test; the new
copy now uses packet124c's fixed helper. The first Intel IPC attempt could not
find its OpenMP library in the closed environment. The explicit installed path
fixes that CPU launcher, and the library hash is retained. Both failures remain
in evidence. An idle preliminary build was superseded after source edits;
final qualification rebuilds with a source-drift check.

Layer fences can slow rank0. The host-clock report retains hit/miss suffix wait,
import/service cost and full rank0 speculative-half duration separately. These
CPU checks do not predict that tradeoff. The device bracket must check every
output and unchanged acceptance before comparing two candidate views against
all three controls. This 128-token screen is not a strict512 promotion.

## Evidence and patches

- [Implementation and trace](README.md), [owner note](../../../../notes/2026-10-18-own-runtime-packet130.md).
- [Final counts, memory and disk](v5/evidence/preparation-summary.json).
- [Head bytes](evidence/head-byte-identity.json), [controller](evidence/controller.json), [private reset](evidence/reset-regression.json).
- [Full-size captures](v5/evidence/full-shape.json), [complete miniature outputs](v5/evidence/protocol.json).
- [CPU seal](v5/lineage/screen-seal.json), [extended qualification](v5/evidence/qualification.json).
- [Temporary queue plan](v5/evidence/queue-plan.json), [queue rehearsal](v5/evidence/queue-gate.json).
- [Original drain failure](evidence/drain-before-fix.log), [Intel loader failure](v5/evidence/protocol-first-refusal.log).
- [Retention and local rebuild dependencies](RETENTION.md). Frozen source hashes
  and symlink targets are in `parent-manifest.json`; no frozen packet is edited.

## When to revisit

The coordinator admits the 12 × 64 smoke, then the conditional one-load
A/B/A/B/A 12 × 128 bracket. Expected durations are 4–6 and 12–20 minutes, both
with 80-minute watchdogs. Keep live safety admission, full exact output checks,
unchanged acceptance, at most 3% control drift and the preregistered 0.5% gain
bar. Compare rank0 completion cost with rank1 wait saved. No automatic retries,
resident service, changed precision or extra transferred rows belong to this arm.
