# Packet160 — what could shorten the two-card serial chain

The CPU study reproduced all 1,188 record intervals and the exact 58.798 tok/s
result. A 3% gain needs about 0.628 ms less draft time on hits, or 0.496 ms less
B time on every interval. It also replayed all 3,780 intervals from packet154's
five views, checking their tokens and draft proposals against the record.

Starting rank0's next half earlier does not help by itself: rank1's B half
finishes last in every record interval. The draft head is too small to yield
3%, even if its full cost disappeared. Sharing B's expert work makes rank0
busier; even perfect balancing with free transfers gives only 1.89% in this
model. Perfectly halving every draft kernel gives 3.31% before communication,
but even one exchange at packet149's measured average reduces that to 2.91%.
These are calculated limits under stated assumptions, not new speed results.

Packet149's direct timer gives 7.685–7.697 ms for 96 exchanges. Dividing by the
count gives about 80 microseconds each. That helps price a smaller design, but
does not measure its latency. The study keeps that uncertainty explicit.

No candidate supports a new ≥3% build brief, so no device-ready marker or
queue proposal was created. A useful next investigation must show a different
dependency: for example a provably exact early target winner, or a measured
early signal that also advances B and pays for wrong guesses. Earlier A alone,
another head split, or relabeled depth-two work does not meet that requirement.

All 223 existing negative-result indexes were searched first. The record and
scope replays and 18 real-parent/corruption tests pass. Work stayed CPU-only,
under nice19, the requested CPU mask, Python `-B`, closed stdin and a 2 GB cap.
No existing packet, screen, ops file, live queue, runtime, GPU job, service,
model/GGUF, privilege or host setting was touched. CURRENT.md was left unchanged
because no live state changed and the task's write scope is packet160 plus this
note. Other workers' dirty files were preserved.

[Plan, mechanisms, costs and evidence](../experiments/own-xpu-runtime/stage2/packet160-critical-path/PLAN.md).
[Closeout and reopening conditions](../experiments/own-xpu-runtime/stage2/packet160-critical-path/CLOSEOUT.md).
