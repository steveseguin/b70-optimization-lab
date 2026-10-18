# Packet95 — expert table prefetch and effective-scale decision

Sealed design before reading packet86's pending verdict. Source: copied packet90
sources, themselves packet84 lineage; hashes in `parent-source-manifest.json`.
Control: hc-wide, wide64, ordered, rec-parallel, production route/norm/dense,
draft HC, batch rollback, rank1 draft, 24/24, full BF16 KV. Arithmetic remains
`iq3-p49-split32-v1`. No frozen packet, screen or live queue is edited.

E3 `exp-grid-prefetch` issues next-block IQ2 dependent table reads before
consuming current tiles. Each logical chain has only current/next raw 64-bit
grid words. The original step/chain/j FP32 product/add order, adjacent tree,
BF16 boundaries, route validation and status/error behavior stay unchanged.
IQ4 down is unchanged. This is not packet65 raw code lookahead, packet73 raw
span residency or packet81 packed activation loads. A linked offline census
must identify the mechanism and spills before a coordinator screen.

E2 `exp-scalecache` is closed, not an executable or a fake queue choice. Exact
arithmetic and both rank censuses are in [E2 closeout](E2-CLOSEOUT.md). No E5 is
implemented in this time box; its separate gate/up scheduling needs its own
register and byte gates. No source, measurement or verdict from pending packet86
is used to choose or tune this implementation. Supplied diagnostic deltas are
non-exact bounds, not exact performance results or promises.

CPU gates: GNU and Intel fresh repeats with raw FP32 chains/trees and BF16
bytes; full-size startup on both ranks using the real allocation, dispatch,
prepared capture, snapshot and draft constructor; real arena admission;
malformed extent/alignment and selection refusals; linked offline register
report; shared pinned v4 seal/worker/admission checks and temporary queue plans.
This follows `cpu-plans-must-exercise-device-startup-paths`: a metadata-only
plan cannot satisfy startup. No model payloads or devices execute here.

Full grid after the explicit E2 closure is production / E3 / production.
Both A-grid/B-confirm and B-grid/A-confirm directions are provided, plus named
single-E3 brackets with separate output paths. Choose one grid family; never
combine its controls with another. The second lane admits only an exact source
winner that beats both controls with identical per-prompt acceptance counts.
The same exact winner must beat both controls on confirmation. Shared pinned
v4 supplies its 64-token incident oracle followed by twelve cold requests.
All jobs retain 90-second gaps and zero retries; CPU success is neither device
correctness nor a speed verdict. No automatic promotion or chain runs.
