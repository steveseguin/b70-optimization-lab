# Packet108: current step budget and the next exact micro

Started 07:33 UTC, with a 2.5-hour limit. CPU only, nice19, CPUs8–15/24–31,
8 GiB address space, closed stdin and packet94's shared serial compiler turn.
No GPU, service, sudo, power/memory/swap/page-cache change or reboot is allowed.
Build cap: 300 MB. Existing packet/screen/ops trees and live queues stay frozen;
only a new proposed queue file may be added.

`git pull --rebase` refused unrelated dirty orchestration files. Fetch confirmed
main and origin/main both at `8bd199660d7d2c0f1355cc536a5d2366581fbcb0`.
Packet103 sources have landed and were copied locally. The source-origin map
records every copied file and hash; no parent source or binary is modified.

The fresh screens have complete command hit/miss timing but empty per-class
device event files. The budget therefore separates fresh command measurements
from historical sampled class estimates. It does not invent current class,
launch-gap or pure-idle times, or a compute roofline unsupported by evidence.

The selected micro groups draft INT8 raw loads while preserving mtp36's original
WG128/SG32 geometry and every FP operation. Packet59 already supplied this load
technique, but combined it with other changes. This is the isolated test.
Both gate/up and DOWN replay all packet100b target routes as a clearly labeled
draft proxy, alternating sample order and retaining the 15% per-stratum gate.

The compiler waited for the shared whole-host hold to release, then compiled
the two-arm micro successfully. It did not execute the device binary. The new
build occupies 491,486 bytes, and all 13 timing-protocol tests pass. The new
`ops/lane-queue/proposed-p108-micro-B.txt` is shipped and passes the actual
planner on a temporary queue. No live queue was changed.

The [budget](../experiments/own-xpu-runtime/stage2/packet108-attribution/BUDGET.md)
covers twelve existing runs and 559 hashed inputs. Its extraction reproduces
byte-for-byte. The current lane-A conditional first-99 means are 15.173 ms hit
and 26.089 ms miss, with about 1.777 ms of drafting on the hit path. The
per-class GPU costs remain unavailable in these runs. The ranked alternatives
are IQ4 subgroup lookup and shared gate/up group ordering, with uncertainty
and prior negative boundaries recorded explicitly.

Full GNU/Intel byte checks, every-window engine startup/host-reference paths,
VRAM checks, seals and B/A model grids remain conditional on a measured micro
win. No speed, device-exactness or qualified integration result is claimed.

## CPU handoff verified

Milestone `5c2624f7d` shipped the budget and compiled proposal and was pushed
immediately. A final static audit confirms the baseline is the copied packet103
mtp36 body, and that only the candidate's INT8 raw-load function differs; launch
geometry, reduction, output stores and status handling are unchanged. This is
source verification, not a numerical byte gate.

The direct plan, private queue plan and 13 protocol tests pass. The budget
extractor reproduces all twelve runs and 559 input pins byte-for-byte. Build
size is **491,486 bytes**, with **386,860 KiB** peak compiler child RSS. The
46,080-byte real-route payload is explicitly retained despite the repository's
generic binary ignore rule. The [final receipt](../experiments/own-xpu-runtime/stage2/packet108-draft-loads/evidence/final-verification.json)
and [CPU closeout](../experiments/own-xpu-runtime/stage2/packet108-draft-loads/CPU-PREPARATION-CLOSEOUT.md)
record all remaining gates and the rebuild path.

The next authorized device action belongs to the coordinator: the new B micro
proposal. No device was used, no process was killed, and no service, live queue,
frozen packet, screen, or host setting was changed by packet108 preparation.
