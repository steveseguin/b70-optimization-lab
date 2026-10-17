# Packet 60: HC fusion, October 17

The arithmetic primitives build and their CPU byte comparison passes. The
engine is not integrated or sealed yet. No GPU ran. The owner's answer is
needed because one kernel per side cannot pass the full-vector dependencies
between independent workgroups using local storage alone.

The source order is norm → low/activation → gate → mix. Inject branches from
norm. Low reads all 10,240 values and gate reads all 320 activated values.
I proposed three kernels per side: norm, low plus inject, gate plus mix. That
would reduce fourteen HC launches per layer to six. The proposal preserves
the existing reduction trees, deterministic functions, casts and intermediate
bytes. The owner has not yet accepted this change to the requested launch count.

Packet46's source uses only four workgroups for norm and a serial upper tree;
its gate/mix serializes four independent projections per subgroup. Its saved
measurements show the norm regression. The proposed primitives use forty norm
workgroups and parallel stream gates. This is a source-based diagnosis, not a
new occupancy measurement.

The one CPU fixture compares 585,360 bytes in twelve random real-shape cases,
covering both sides and positions 127, 4094 and 4095. It compares all six BF16
outputs, norm and inject partials and the error word. These are synthetic
inputs; no real model data was read. The first fixture attempt compared
unmaterialized CPU norm scratch; it was corrected to call the production
stage bodies with explicit scratch. An initial SYCL compile placed the
host-only stride validator inside a kernel; stride computation now stays on
the host. Neither issue caused a device launch.

[Packet, sources and commands](../experiments/own-xpu-runtime/stage2/packet60-hc-fusion/README.md).
The initial `git pull --rebase` refused because packet59 was dirty. A read-only
fetch found no incoming commits. After the other job committed, the requested
pull succeeded. Its files and all other jobs were left alone. All compilation
and fixture work used nice19 and cores 8–15/24–31. No services, sudo, signals,
power, memory, swap, page-cache changes or reboot occurred. `CURRENT.md` was
left to the coordinator under the explicit own-folder scope.

Expected saving for the proposed three-stage design is 25–40 microseconds per
layer, an unmeasured planning estimate with regression risk. The integrated
binary, screen seal and exact runnable screen command remain pending the
topology decision. There is no speed or full-model exactness claim.
