# Packet82b recurrence round 2 — October 18

The combination was already present: packet82's rec-parallel includes its
gate split. The requested rec-both view therefore uses the same kernel as
production and is a control, never a possible winner. The control is copied
from packet84 with wide HC and ordered cleanup enabled.

The new rec-both-plus view removes one preparation barrier. It keeps the full
arithmetic loop unchanged, including every BF16 state round trip. Offline
assembly confirms one fewer barrier and no scratch spills. This is a candidate
for a later device screen, not a measured speed improvement.

Both compilers pass every state/output byte check twice. Each run covers 260
full comparisons and 416 token steps, including consecutive tokens and separate
or shared state buffers. Existing GNU/Intel NaN payload differences remain
separately recorded; every candidate matches its own compiler's production.
All six full-size startup paths and 87 Python checks pass. Three seals, both
lanes' full grids and opposite-lane confirmations pass planning. Four proposed
queue files were checked on temporary copies.

No GPU, service or live queue ran. Existing packet, screen and ops files remain
untouched. The initial pull refused other work in progress; fetch showed main
already matched origin/main. No files were stashed. Build storage is about 212 MB
and peak compiler RSS about714 MiB, within the requested limits. All compiles
ran one at a time at nice 19 on CPUs 8–15/24–31 with an 8 GiB address-space bound.

The coordinator next runs the chosen lane's grid. Only the new candidate can
qualify, and it must beat both production controls and the identical rec-both
control with exact output before the other lane confirms it. Actual device
correctness, acceptance and speed remain pending.

[Analysis](../experiments/own-xpu-runtime/stage2/packet82b-recurrence2/ANALYSIS.md),
[CPU closeout and evidence](../experiments/own-xpu-runtime/stage2/packet82b-recurrence2/CPU-PREPARATION-CLOSEOUT.md),
[proposed screens](../experiments/own-xpu-runtime/stage2/packet82b-recurrence2/WINDOW.md).
