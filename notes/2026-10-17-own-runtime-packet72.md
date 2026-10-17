# Packet72: bandwidth first

CPU-only preparation. The initial `git pull --rebase` refused the live packet70
log's unstaged change. A fetch confirmed HEAD equals origin/main; that log was
left untouched. Root has 30 GB free. Builds are limited to 8 GiB address space,
one compiler at a time, nice19 and cores8–15,24–31, with no device execution.

[Bandwidth audit](../experiments/own-xpu-runtime/stage2/packet72-occupancy/BANDWIDTH.md)
recomputes complete site-call times from packet64's raw lane-B events. Real
runtime Q6/Q8 representations matter: these dense weights are expanded codes
and scales. QKV, Z and Q-gate fail the requested0.3 ms/half headroom threshold.
Attention output qualifies narrowly on rank1 (0.310 ms); rank0 is0.260 ms.
It is one shared kernel class across GDN and QSA layers, including its finishing
kernel. Those are occurrence-scaled sampled-layer estimates, not new measured
whole-half times or promised speedups.

The timestamps do not contain DRAM transaction counters. The report explicitly
uses distinct runtime read bytes divided by engine time, and leaves actual
DRAM bandwidth unknown. Unsampled layer timings remain null. Packet67's
negative HC/recurrence mechanisms remain closed; route is outside the proposed
raw-code/scale sharing mechanism, and experts are already wide64 in packet70.

Next: copy packet70's sources and implement attention-output sharing of adjacent
logical chains without changing their arithmetic. GNU/Intel operator checks,
offline compiler reports and seals precede the coordinator's lane-A grid.
No model, GPU, service or host setting was touched.
