# Packet51: second exact-order kernel round

Host and device-program compilation pass. All five operator runs pass 286,809
checks each; the admitted phase hashes agree under GNU, Intel and ASan/UBSan.
Two fresh full-layer CPU processes pass 5,472 byte comparisons each across
36 cases, with identical output hashes and safe teardown. The final seal binds
the preparation receipts; device exactness and speed remain pending. No device
program has run and no performance gain is claimed. See [ranking](RANKING.md), [preregistration](PREREGISTRATION.md),
[independent review](REVIEW.md), and [coordinator commands](WINDOW.md).

The inherited decoder selects a compiler-dependent NaN payload for an already
rejected nonfinite weight scale. All such scales still refuse before writes;
direct diagnostic hashes and exact same-compiler comparisons remain recorded.
See the [preparation closeout](PREPARATION-CLOSEOUT.md) and
[negative-result index](DO-NOT-REPEAT.md).

The control is packet45's actual Engine with p48b's accepted IQ2 gate/up and
IQ4 down kernels. QKV/Z use the original accepted engine choices; p48b's dense
candidates were not accepted. The candidate changes these kernels only:

| Class | Change | Arithmetic and memory kept |
|---|---|---|
| IQ2 gate/up | 2 KiB magnitude codebook instead of 8 KiB; separate gate/up subgroups, four output rows per workgroup | Same compact expert-weight bytes, lane chains, SG32 tree and BF16 outputs |
| HC low/gate | Vector loads and smaller low workgroups; gate uses eight output rows per workgroup | Low split-four tree, rounded low and activation, gate SG32 tree |
| Route | One exponential per lane with exact 16-value trees; shared rounded probabilities for rank comparisons | Four passes, all scratch bytes, deterministic exponentials, normalized ties and lower-index rule |
| QKV | Vector loads and eight output rows per workgroup | Original expanded Q6 bytes, ten serial tiles per lane, SG32 tree |
| Attention output/combine | Vector loads/grouped rows; share four exact injection factors within the finishing workgroup | Original split-four scratch, two passes, BF16 projection and ordered stream updates |

HC injection, mix/norm, recurrence, shared down, FFN combine, exceptional IQ3/Q8
layer and QSA attention are unchanged. The unselected F32 lane helper is tested
only as arithmetic diagnostic; it is not installed in the production fixture.
No larger routed-weight allocation or new FP reduction tree is introduced.

M=2 reports two independent changing rows through serial actual-engine calls.
Each row has separately restored state and all outputs checked. It is not a
joint kernel, a continuous recurrent two-token model run, or a weight-reuse
speed claim. Isolated gate tests additionally cover identical, shifted-five and
disjoint expert sets across two rows, invalid routes and sticky controls.

## CPU reproduction

The baseline packet45 build objects and checked mirrors must exist and match
its recorded closure. The build script proves them by byte-identical relinking,
then links this packet's independently authored adapter. Missing old artifacts
require rebuilding the pinned baseline; this is a research packet, not a
published portable recipe. Do not modify a sealed baseline or borrow unverified
objects. No model payload is used by these synthetic tests.

From the repository root, run each command to completion before the next:

```bash
P=experiments/own-xpu-runtime/stage2/packet51-round2
mkdir -p "$P/build"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/build.py" --kind host
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/candidate_gate.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/cpu_layer_gate.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/build.py" --kind device
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/python_gates.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/cleanup.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/seal.py"
```

The device command **compiles only**. Only the coordinator runs E1/E2/T1/T2.
CPU tests use at most two arithmetic workers; compilation stays serial. Build files remain local/ignored. The full-layer raw receipts and comparisons
are also retained in a checked compressed archive; see [retention](RETENTION.md).
Receipts bind every retained file. The build cap is 1.5 GB and CPU preparation reserves 18 GB free disk.
Cleanup removes only this packet's regenerable object files, not baseline
objects, sealed binaries or evidence. No service or host setting changes.

The bar is at least 40 microseconds per ordinary M=1 layer OR 1.5x expsgate,
in both fresh timing owners after E1/E2 pass. Full model and capacity gates are
still required separately before one-card or two-card integration.
