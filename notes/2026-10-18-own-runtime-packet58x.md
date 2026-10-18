# Packet58x: larger one-card cache, October 18

CPU admission passes: 21.553 GB cache, 3.553 GB above the 18 GB control.
All original device transient allowances remain, plus 512 MiB for driver
overhead and the unchanged 1.5 GB reserve. Host admission is 98.990 GB with
the measured floor, full backing for the added cache, 4 GiB margin and 8 GiB
reserve. Independent route replay projects +2.20% from reduced fill copies
alone; this is a conditional estimate, not a measured speed.

Evidence and reproduction: [admission](../experiments/own-xpu-runtime/stage2/packet58x-cache-capacity/ADMISSION.md).
The next step is a private packet58v copy with a single maximum-size allocation
and a quiescent 18 GB / maximum switch, followed by CPU gates and unqueued
lane-A proposals. Maintenance defaults to serial unless a completed packet58v
bracket proves overlap exact and faster. No GPU or service is authorized here.

Started at 17:51 UTC with 33.2 GB root free. `git pull --rebase` refused unrelated
dirty orchestration files; fetch confirmed HEAD equals origin/main. Those edits
and all frozen packet trees remain protected. The task's stop floor is 25 GB,
build cap 300 MB, CPU memory cap 4 GB, nice 19 and cores 8–15/24–31.
