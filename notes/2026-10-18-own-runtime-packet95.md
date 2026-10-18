# Packet95 — next exact expert decoding designs

E3 is built and sealed from copied packet90 sources. It reads the next IQ2
lookup-table word while the current tile's arithmetic runs. The FP32 values,
sum order and reduction trees stay unchanged. Production keeps packet84's
hc-wide, wide64, ordered and rec-parallel selection. No GPU or service ran.

E2's full scale cache does not fit either rank. Replacing packet90's cached
half-scales adds 9,043,968,000 bytes on rank 0 and 9,437,184,000 on rank 1;
rank 1 has 630,519,094 bytes spare. A bounded choice fits one rank-1 layer over
E1, or two over production, but existing samples cannot identify the hottest
layers. The [arithmetic closeout](../experiments/own-xpu-runtime/stage2/packet95-expert-dequant/E2-CLOSEOUT.md)
records both layouts and every limit. E5 was deferred within this time box.

The first two E3 forms spilled registers. Keeping only two raw table words live
removed the spills; reusing production's wide metadata then removed an early
wait. Linked code confirms that next-table reads remain outstanding during
current FP32 arithmetic. Final code uses 128 GRF, with zero scratch or flag
spills, 56 static loads versus production's 51, and 2,055 instructions versus
1,993. These are compiler observations, not speed measurements. All rejected
and superseded forms are retained in the [linked-code review](../experiments/own-xpu-runtime/stage2/packet95-expert-dequant/LINKED-CODE.md).

GNU and Intel pass both views twice: 28 cases per run, raw FP32 chains/trees,
BF16 outputs, routes/errors, exceptional activations, every finite half/scale
nibble and every grid/sign combination. All four real full-size startup and
arena checks pass. Eight malformed allocations and five malformed selections
are refused. E3 adds no modeled device allocation; rank 1 retains 945,091,894
bytes below its 30 GiB arena limit. Driver residency remains unmeasured.

All 90 Python tests pass. The seal binds the tested runner modules, actual
startup archives, linked assembly and retained fixture bytes. It caught a
coordinator restoration of a parent submission helper after testing; the tests
were rerun against the current hash. Both view seals pass. Final shared-wrapper
and temporary-queue planning are recorded in the packet's evidence files.
The [handoff](../experiments/own-xpu-runtime/stage2/packet95-expert-dequant/WINDOW.md)
lists eight proposed files: full and E3-only grids in either direction, each
with the other lane's winner-only confirmation. E2 has no fake executable or
queue row. No live queue or existing packet was edited.

`git pull --rebase` was attempted first and refused the dirty shared tree.
Read-only fetch confirmed local and remote main matched; no foreign work was
stashed or changed. Compiler work used packet94's current coordinator-patched
turn helper, nice 19, cores 8–15,24–31 and an 8 GiB address-space cap. Compiles
waited through the whole-host record window. Root began with 18.28 GB free;
the 12 GB stop and 1 GB build limit remained enforced. Fixture payload scratch
was archived and removed after gates; no existing evidence was deleted.

No packet86 pending verdict was read or used to tune the designs. Device
correctness, acceptance and speed remain for the coordinator's matched screens.
[Full closeout and evidence](../experiments/own-xpu-runtime/stage2/packet95-expert-dequant/CPU-PREPARATION-CLOSEOUT.md).
