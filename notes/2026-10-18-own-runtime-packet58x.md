# Packet58x: larger one-card cache, October 18

CPU admission passes: 21.553 GB cache, 3.553 GB above the 18 GB control.
All original device transient allowances remain, plus 512 MiB for driver
overhead and the unchanged 1.5 GB reserve. Host admission is 98.990 GB with
the measured floor, full backing for the added cache, 4 GiB margin and 8 GiB
reserve. Independent route replay projects +2.26% from reduced fill copies
alone; this is a conditional estimate, not a measured speed.

Evidence and reproduction: [admission](../experiments/own-xpu-runtime/stage2/packet58x-cache-capacity/ADMISSION.md).
The private packet58v copy now has one maximum-size allocation and a quiescent
18 GB / maximum switch. CPU gates and both temporary lane-A plans pass. The
next step is the coordinator's 12 × 64 smoke, then the one-load five-view
12 × 128 bracket only after an exact, cleanly drained smoke. Neither is queued.
Serial maintenance is the default: packet58v's completed bracket is exact and
overlap is faster, but its controls drifted 14.73%, above its registered 3%
limit. Overlap remains selectable. No GPU or service ran in this preparation.

Started at 17:51 UTC with 33.2 GB root free. `git pull --rebase` refused unrelated
dirty orchestration files; fetch confirmed HEAD equals origin/main. Those edits
and all frozen packet trees remain protected. The task's stop floor is 25 GB,
build cap 300 MB, CPU memory cap 4 GB, nice 19 and cores 8–15/24–31.

The admission milestone was committed and pushed as `7cc07d7be`. It projected
+2.2023% using the mean fill cost. The final analysis uses each prompt's own
99 charged intervals and recomputes the six-class statistic: **26.821731 tok/s,
+2.2614%**, still only a conditional projection. The newly finished packet58v
bracket raised the host accounted peak by 57,344 bytes; final admission is
**98,989,727,744 bytes**. No reserve or live shadow stop was reduced.

The implementation's literal sweep found the old native 26.409 GB allocator
limit and updated it together with planning and Python admission. Read-only
review caught direct-launch cap handling and missing continuous device
occupancy checks; both are fixed. Actual startup reaches native execution with
the proposal's lanequeue-derived service name and recorded oneAPI library path.
The original oracle binding, drain fix, memory fence and getrlimit refusal stay.

Both builds, K1 mixed-source bytes, repeated capacity/race checks, full-shape
allocation and switching, miniature exact repeats, two parser paths with eight
negative cases, six entry probes, 96 Python tests, seal verification and two
temporary queue plans pass. The build is about 80.6 MB; peak compiler RSS is
below 0.73 GB, and the full-shape mock uses about 30 MB RSS. Compilation waited
for the existing whole-host hold through the shared compiler-turn gate.

[CPU closeout and retained evidence](../experiments/own-xpu-runtime/stage2/packet58x-cache-capacity/CPU-PREPARATION-CLOSEOUT.md).
The final readiness marker is written only after the implementation commit and
proposal hashes are fixed, then committed separately. It is the task's last
content write. Device fit, quality and speed remain pending.
