# Packet 60: exact HC fusion primitives — integration pending

CPU preparation only. This folder does **not** yet contain a screenable engine
or a screen seal. No GPU, model payload, service, host setting or other packet
was touched. The original one-kernel-per-side requirement needs a design
decision before integration. The question was sent to the owner on October 17.

The production dependency graph is:

```text
4 × 2560 streams → norm → low (320 × 10240) → BF16 → activation → BF16
                       ↘ inject (4 × 10240) → BF16
activation → gate (10240 × 320) → BF16 → mix with norm → BF16
```

See [the production builder](../packet3/step/plan.hpp:99). It is not
norm → mix → gate → low → inject. Each low row needs the whole normalized
vector; each gate row needs the whole activated low vector. Workgroup-local
memory cannot carry either dependency between independent workgroups.
A one-kernel implementation would need a grid barrier, repeated low projections
per output tile, or one workgroup for the side. The last choice contradicts the
brief. A spinning grid barrier has no scheduler-independent progress guarantee;
duplicating the whole low matrix per output tile defeats the saving.

Proposed topology, awaiting the owner's answer: **three kernels per side**,
six HC kernels per layer instead of fourteen:

1. Norm: forty workgroups, ten output tiles for each stream. Repeat only the
   small norm reduction per tile. Preserve all eighty 32-leaf partials per
   stream, the adjacent upper tree, FP32 division and deterministic rsqrt,
   unit-zero addition, and BF16 result. Original global partials have one writer.
2. Low/activation plus independent inject: 324 workgroups, four subgroups for
   each original split-four dot. Keep the four partials and final
   `(p0+p1)+(p2+p3)`, both low/activation BF16 boundaries, and inject workspace.
3. Gate/mix: 1,280 workgroups, two hidden coordinates per workgroup. All four
   stream gates run in separate subgroups, then their BF16 values pass through
   local memory. Mix retains the ordered `0 + stream0 + stream1 + stream2 +
   stream3` products and division by four. All original BF16 intermediates remain.

The functions are original lab code using packet56's arithmetic helpers. There
is no imported external implementation, changed precision, changed target,
compressed KV, prompt reuse or oracle rebase.

## Why packet 46 lost time

[Packet46's source](../packet46-specialized/specialized.hpp:74) launches only
four 128-thread workgroups for norm. Eighty lanes each execute a private
32-leaf reduction; one lane then computes the entire upper tree while its
workgroup waits. It also requires global/local synchronization before output.
Its gate/mix computes four gate rows serially in each subgroup.
[Its device result](../../../../notes/2026-10-17-own-runtime-packet46-device-result.md)
records norms increasing from 19.3 to 35.7 microseconds and gate/mix remaining
at 57.5 microseconds. Low parallelism and the serial upper reduction explain
the structural risk; no new device profile has proved their individual costs.
Packet60 increases norm workgroups and computes independent stream gates in
parallel. It does not reuse packet46's fusion body.

## Lean preparation

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet60-hc-fusion/build.py
```

This compiles the three SYCL submission bodies without executing them and
runs one CPU byte fixture against production norm and dense bodies. The
fixture covers random finite weights and inputs at the real shapes, both
HC sides, and the M=1/serial-M=2 positions 127, 4094 and 4095: twelve cases,
585,360 compared bytes. It retains expected/actual norm, low, activation,
gate, mix, inject, norm scratch, inject partial scratch and error bytes.
These are synthetic values, not captured model tensors or device exactness.
The candidate remains unintegrated; controller coverage is not claimed.

The build uses packet56's existing checked header mirror read-only. Restore
that parent build first if absent. Only the small primitive object and fixture
executable are built here. Commands, compiler dependency hashes and byte
receipts are retained. The ignored `build/` folder is regenerable by the command.

## Integration and screen still required

If the three-kernel boundary is accepted, hook the primitive submissions into
the same target engine path for M=1 and each serial M=2 row, preserve the
existing residual/next-norm relationship and layer-end hooks, link against
hash-bound unchanged packet56 objects, and create the diagnostic screen seal.
The inherited target/draft/controller, 23/25 split, vocabulary prefix, memory
plan and packet49 oracle must stay unchanged.

An exact runnable screen command cannot be supplied yet: there is no integrated
binary or screen seal. After integration it will use the `tp2` packet56 profile
with this lineage and its new screen seal; the coordinator alone supplies the
reviewed journal boundary, device admission and fresh output directory.

Planning estimate for the proposed topology: **25–40 microseconds per layer**
saved, not measured. The original approximately 110 microseconds contains
roughly 24 microseconds of inject launches, 16–18 of mix, and 15 of norm.
Low+inject and gate+mix retain their arithmetic but remove separate launches;
the repeated norm reductions and changed workgroup occupancy can eat the gain.
The saving may be zero or negative. No one-kernel saving is claimed. Only the
coordinator's every-token packet49 screen and matched packet56 A/B can decide.
