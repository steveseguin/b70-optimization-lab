# Qwen3.8 Flash-Next FP8 M1 W2 N32 confirmation A2

Date: 2026-09-01
Status: complete; exact-output positive, performance negative

The three-seed, fresh-process bracket did not reproduce the A1 screen's
apparent `4.501857%` W2-only improvement. Every candidate and control arm was
bit-exact across 100 repeated outputs, but the candidate reductions were only
`1.329041%`, `-0.056631%`, and `0.073138%`. The median was `0.073138%`, and
zero seeds cleared the frozen `3%` advancement floor.

The A1 lead was timing drift, not a robust component win. W2 N32 is closed as
performance-neutral and will not consume a full-model qualification. The
weaker A1 W2 candidates are not advanced because they had less screen value
under the same drifting protocol. The opt-in phase-specific implementation and
its tests remain preserved as a research capability; neither it nor this
negative result changes any protected model speed or quality claim.

Tracked summary:
[`../data/20260901-moe-m1-w2-n32-confirm-a2.json`](../data/20260901-moe-m1-w2-n32-confirm-a2.json).
Full evidence remains outside Git at
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260901-moe-m1-w2-n32-confirm-a2`
with its `SHA256SUMS` manifest.
