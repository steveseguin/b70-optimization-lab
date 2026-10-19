# Packet157: draft device-time decomposition

CPU preparation in progress. No device has run; no timing ranking or overhead
has been measured. The 58.798 record is unchanged.

This is a vendored packet136 bundle8 runtime with packet154's one-load harness
and host clocks. Packet154's duplicate work is disabled. The only new runtime
behavior is observing existing draft events at existing retirement boundaries,
with host issue clocks around each prepared kernel group. Nothing is added
inside capture; no barrier, reduction, proposal or model operation changes.
The 80,128-row prefix, BF16 KV and `iq3-p49-split32-v1` arithmetic stay fixed.

The one-load bracket is control / timed / control / timed / control. Each view
runs the fixed twelve prompts plus incident64. Both target outputs and every
draft proposal and acceptance count must match across views. The smoke runs
the same analyzer after its first request, without a wall-clock shortcut.

The eight groups are input norms/embedding mix, attention projections,
attention, routed experts, shared expert, final norm/HC, head GEMV and
argmax/publication. The analyzer requires a complete group census for every
included decode draft. Device execution and host submission overlap, so their
sums are reported separately against draft_issue, never added as elapsed time.
The two largest measured device groups select the next levers. Closed designs
remain excluded; see DO-NOT-REPEAT.md and the analyzer's per-group guidance.

Both lane A and B proposals will be planned on temporary copies; lane A first.
No queue edits or launches are part of CPU qualification. Final readiness is
written last. CPU preparation stops below 27 GB root free. Device admission
keeps the 25 GB floor plus planned writes. The 145 MB/view bound (725 MB total)
is below three times packet150's measured 243 MB; the approximate 250 MB/view
request would exceed that total cap, so the stricter bound is retained.
