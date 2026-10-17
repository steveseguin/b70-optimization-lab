# Packet75 record bundle

Packet70's chain and record configuration, with independent choices from
packet74 (packed head/dense weights) and packet73 (HC and expert kernels).
All 24 combinations share one binary. Target arithmetic remains
`iq3-p49-split32-v1`; packet49 remains the oracle; BF16 KV is unchanged.

CPU preparation passed: all 24 compositions have exact GNU/Intel byte checks
with two fresh executions per compiler. All 48 production-shape mock runs
(24 views, both ranks) passed the actual allocation, post-load capture and
draft initialization path. An undersized packed-head allocation was rejected.
Device quality and performance remain pending. Preparation launches no GPU,
service or chain.

Dense: production, head-packed, dense-packed, combined.
HC: production, hc-wide. Experts: wide64, experts2-a, experts2-b.
The draft-HC, batch rollback and 24/24 placement preset stays fixed.

The lane wrapper is referenced directly from shared `screen/v4-lanes`, pinned
in `shared-wrapper-pin.json` to the reviewed d5b060769 source bytes. It is
never copied and modified. Chain and screen admission use its actual predicate.

[Preparation helper](../../ops/packet75-orchestration/README.md) selects only
both-lane confirmed exact winners and writes the coordinator command. Every
chain gap is 90 seconds. A new chain is mandatory; old packet receipts cannot
cross this binary identity. Pinned packet75 resumes remain supported.

See [CPU closeout](CPU-PREPARATION-CLOSEOUT.md), [retention and rebuilding](RETENTION.md),
and [submission rules](SUBMISSION.md). CPU evidence does not replace the
packet49 oracle, fresh device chain or realistic performance gate.
