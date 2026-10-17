# Packet83 preregistration

Engine sources are copied from packet75; all older packet/screen/ops files stay frozen.
Target arithmetic, full target head, controller, BF16 KV and draft rank1 stay fixed.

A: symmetric signed Q4, groups32, FP32 per-group scale (1600 bytes per2560-column row),
nearest-even rounding, max(abs)/7, zero group scale1. Separate draft-only head
prefix91392; derive deterministically from the existing authenticated Unsloth Q6_K
GGUF head. This is a further quantization of that release, not original BF16 weights.
No download; no target weight replacement. Q4 changes only proposals.

B: two points, the smallest multiple256 covering99.0% and98.5% in the frozen
packet56 independent-text histogram, respectively. Same fixed five whole sources,
weighted by token count. Do not inspect benchmark tokens to choose N. No combinations
of A/B in this screen. Freeze N before any performance/acceptance observation.
Coverage ratios give a conditional acceptance proxy0.787*coverage/new-old;
actual acceptance may differ. Q4 numerical acceptance cannot be inferred from coverage.

Grid: production, Q4, prefix99, prefix985, production. Either lane may run the
complete grid; the other runs the exact best improving candidate between two controls.
Require all screen tokens equal packet49, valid cold zero-cache requests, and acceptance
reported for every screen. No improvement means no confirmation job. No retry.
These are diagnostic128-token screens, never the final512-token promotion gate.

CPU gates: unchanged target-source/object identity and miniature target bytes;
two fresh draft CPU repeats; complete production-shape allocation/capture/startup
with payload-only mock, rank1 memory census, negative extent checks; source seals.
CPU-only build uses the task-specific below1GB disk budget and below8GB process limit.
The general50GiB free-space check refused (about19GiB available); this task's explicit
bounded build budget is recorded separately, with no cleanup of other work.
