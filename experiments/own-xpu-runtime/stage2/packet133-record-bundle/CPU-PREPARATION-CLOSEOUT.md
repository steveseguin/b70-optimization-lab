# Packet133 CPU preparation closeout

<!-- experiment-closeout -->

Question: prepare exactly bundle7 and bundle7 + packet130 suffix interleave,
a lane-A one-load proposal and a fully gated future chain before the B verdict.
Identity: unchanged `iq3-p49-split32-v1`, BF16 KV, packet130 v5 native binary,
24/24 split and preregistered 80,128-row draft prefix. Packet131 is disabled.

Outcome: CPU preparation passes. Both views, 22 startup paths, 83 tests and
11 subtests, all-window arguments and the whole queue rehearsal pass. All 182
parent symlinks survive. The fresh chain is absent and the proposal is unqueued.
The current build is below 300 MB; root stays above 25 GB.

Useful mechanisms retained: exact binary/source reuse, explicit native alias,
draft-only KD projection, fixed drain/teardown/limits, raw v5 evidence replay,
strict candidate-min/control-max threshold, and original argument + queue gates.

Failures/uncertainty: the B result arrived during preparation and replays exact
but at −1.605458% versus the fastest control. It fails the +0.5% gate. Lane A
and the composed smoke remain unrun. No chain or submission may proceed on the
current evidence; no speedup is claimed.

Evidence and recovery: [work note](../../../../notes/2026-10-18-own-runtime-packet133.md),
[final CPU audit](../../ops/packet133-orchestration/cpu-final.json),
[readiness](../../ops/packet133-orchestration/ready.json),
[retention](RETENTION.md). Preserve all frozen parents and current receipts.
Revisit only with a new preregistered identity that can satisfy both lanes and
the composed smoke; never replace failed evidence in place or lower the gate.
