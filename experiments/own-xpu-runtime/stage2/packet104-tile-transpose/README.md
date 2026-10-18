# Packet104 tile16 extension

Micro-first preparation from copied packet100 sources. See the
[work note](../../../../notes/2026-10-18-own-runtime-packet104.md).

The native micro compiles; device correctness and speed are pending. Nine
candidate kernels retain their source operations and change only weight
addresses. `p104_layout.hpp` transposes complete 16-row tiles without adding
weight bytes. No full model view is admitted until the 15% micro gate passes.
Draft timings on packet100b's **target** routes remain proxy diagnostics.
The [access census](ACCESS-CENSUS.md) covers the target shared tuple and
explains why the selected attention paths do not match.

The coordinator owns `ops/lane-queue/proposed-p104-micro-B.txt` (relative to
the runtime experiment root). This task created a proposal only.

CPU preparation uses `nice -n 19 taskset -c 8-15,24-31 python3 -B`, stdin
`/dev/null`, 8 GiB address space and one compiler through `compile_turn.py`.
`derive.py` regenerates address-only derivatives; `build_microbench.py`
creates the checked include mirror and pins the actual compilation closure.
No parent orchestration receipt is pinned. Build budget: 300 MB.

All other copied C++ files are packet100 source context, not a claim that
packet104 has a runnable or qualified full model engine.
