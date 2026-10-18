# Packet90 — prepare exact expert and HC candidates

CPU-only work started before packet86’s verdict. The diagnostic can separate
some decoding and repeated-read costs, but its table lookup test cannot identify
launch overhead and its old HC control differs from packet84’s current geometry.
The [preregistration](../experiments/own-xpu-runtime/stage2/packet90-expert-hc/PREREGISTRATION.md)
records every verdict, candidate order, expected budget and risk.

First choices: decode IQ2 gate/up half scales once at load; prepare exact FP32
HC gate weights once at load. Both keep the original ordered arithmetic and
have separate memory admission. Both host/device builds, GNU/Intel byte gates,
full-size startup, memory admission and all three view seals now pass. No device
code ran. Exact model outputs and speed remain pending coordinator screens.

The CPU fixture ran every view twice with each compiler: 28 full-shape/tail and
exception cases per run, plus exhaustive finite half-scale checks. All raw bytes
matched across both compilers and all views. Startup exercised both real rank
paths, including dispatch, capture, speculative banks and rank-1 draft setup.
Six positive paths passed; 12 malformed allocations, five malformed selections,
14 unsupported modes and the combined layout were refused. The native memory
plan agrees with actual allocation sizes. Rank-1 arena headroom is about 631 MB
for the expert view and 503 MB for HC; driver residency remains unmeasured.

The first startup fixture assumed 48 cached expert tensors per rank. Actual
rank-0 dispatch specializes 46; the test and memory plan were corrected, without
changing runtime selection. Other fixture corrections and the pre-seal review
are retained in the packet. The shared wrapper and legacy submission consumers
were tested: cached views remain screen-only. The real shared wrapper admitted
all four lane-A plans and both possible lane-B winner brackets. Proposed queue
files also passed planning on a temporary copy; the live queue was untouched.

`git pull --rebase` was attempted first and refused existing dirty live logs.
Read-only fetch confirmed HEAD and origin/main equal, so no stash/rebase or
foreign edit was needed. Existing packets, shared screen and live ops are frozen.
Only new proposed queue files may be written. No GPU/service/host-setting work.

[Coordinator handoff](../experiments/own-xpu-runtime/stage2/packet90-expert-hc/WINDOW.md), [CPU closeout](../experiments/own-xpu-runtime/stage2/packet90-expert-hc/CPU-PREPARATION-CLOSEOUT.md), and [retention/rebuild](../experiments/own-xpu-runtime/stage2/packet90-expert-hc/ARTIFACT-RETENTION.md) give the next steps. Build scratch stayed below 146 MB before fixture cleanup. Final independent review found no blocking issue and verified all four seals. The preregistration and all expected-saving ranges remain hypotheses until the coordinator measures them.
