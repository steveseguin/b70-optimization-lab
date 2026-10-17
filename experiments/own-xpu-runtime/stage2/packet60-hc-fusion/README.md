# Packet 60: three-stage target HC fusion

The coordinator accepted **three kernels per side** on October 17, under the
owner's standing instruction to decide and proceed. This supersedes the earlier
one-kernel proposal. The target engine copy is `main.cpp`; its unchanged
implementation dependencies come from the hash-bound packet56 checked mirror.
The MTP draft, target head, controller, oracle and 23/25 split remain packet56.
No GPU or model payload is used by the preparation commands below.

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

Accepted topology: **three kernels per side**,
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

## Integration

The actual `Engine::execute_site` hook handles both HC sides of every numbered
target layer. Ordinary M=1 and both serial M=2 rows use the same hook. It retains
one prepared-command slot per plan operation: norm, low and gate each capture
one command; absorbed act, mix and inject slots capture none. Final HC and MTP
labels are excluded. The existing BF16 intermediates, scratch and sticky error
bindings remain present; no allocation budget is added.

The earlier residual-combine-plus-next-norm rewrite is disabled only for target
HC norms. The residual combine still runs in the same order, and its next norm
is the first packet60 stage. Layer-end hooks retain their original labels.
The production dispatch and selection files remain byte-identical to packet56.

## Lean CPU preparation

```bash
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B \
  experiments/own-xpu-runtime/stage2/packet60-hc-fusion/build_engine.py
nice -n 19 taskset -c 8-15,24-31 env OMP_NUM_THREADS=2 python3 -B \
  experiments/own-xpu-runtime/stage2/packet60-hc-fusion/cpu_gate.py
```

The builder reruns the existing 585,360-byte production-shape primitive fixture,
compiles the host and SYCL engines, and never executes a device binary. Parent
object files were reclaimed, so missing link inputs are compiled inside this
folder using packet56's exact compiler commands and verified source mirror.
The parent is read-only. Its external build symlink requires byte-identical
compiler-input snapshots inside this packet; see [retention](RETENTION.md).
Build logs, commands and source/object hashes are kept;
the ignored build tree is reproducible with this command while unsealed.

The integrated fixture drives the actual target engine hook and capture/issue
path at production HC shapes, both sides and positions 127, 4094 and 4095.
It checks all six BF16 outputs, norm/inject scratch and the error word against
packet56's production stage bodies. It also checks three commands per side,
empty absorbed slots, all 48 target-layer labels, and exclusion of draft/final
HC. The retained mini pipeline separately compares 96 target layer fixtures
and 24 generated tokens against packet56. These are synthetic CPU checks;
full-model device equality remains the coordinator's screen gate.

The final gates pass: **878,040 compared bytes**, **96 target layer fixtures**,
and **24 tokens** equal packet56. The integrated capture has three commands
per side, and the production plan has 96 HC sides / 288 commands per row.
Both builds and diagnostic seal admission pass. See the
[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md).

## Coordinator screen

See [WINDOW.md](WINDOW.md) for the exact seal, plan and screen commands.
`screen-seal.json` is diagnostic admission only. It does not qualify a record,
replace the full sealed chain or assert measured speed.

Planning estimate: **25–40 microseconds per layer** saved, not measured. The
original approximately 110 microseconds contains roughly 24 microseconds of
inject launches, 16–18 of mix, and 15 of norm. The changed occupancy and repeated
norm reductions can erase the saving. Only the coordinator's every-token
packet49 screen and matched packet56 A/B can decide.
