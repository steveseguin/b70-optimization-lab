# Packet 6 — first packed GEMV optimization round

CPU-prepared on October 11, 2026. **Device exactness and performance are
pending.** This is our original kernel code, selected explicitly by name.
Packet 2's kernels, reference order and historical receipts remain unchanged.
There is no integration into the model decode path or performance promotion.

## What the measured baseline says

The [card-3 receipt](../packet2/timing-card3-20261011/timing.json) measures
warm fixed-input M=1 operators with resident device allocations, one untimed
warmup and 20 SYCL event intervals. Effective GB/s counts packed active weights,
not measured DRAM transactions. The [roofline](../packet2/roofline.json)
uses historical 507/537 GB/s bandwidth references, not guaranteed rates for
these kernels. Activations, codebooks, unpack work and local-memory traffic
are outside that byte numerator.

Representative layer-0 measurements (decimal MB):

| Matrix | Format | Rows × columns | MB/launch | Old products/work-item | Median ms | GB/s |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| attn_qkv | Q6_K | 10240 × 2560 | 21.504 | 80 | 0.347500 | 61.88 |
| attn_gate | Q6_K | 6144 × 2560 | 12.9024 | 80 | 0.216042 | 59.72 |
| hc_attn_up | Q8_0 | 10240 × 320 | 3.4816 | 10 | 0.045000 | 77.37 |
| hc_attn_down | Q8_0 | 320 × 10240 | 3.4816 | 320 | 0.119584 | 29.11 |
| hc_attn_inject | F32 | 4 × 10240 | 0.16384 | 320 | 0.086562 | 1.89 |
| ssm_alpha / beta | F32 | 48 × 2560 | 0.49152 each | 80 | 0.0239065 / 0.023646 | 20.56 / 20.79 |
| expert gate / up | IQ2_S | 10 × 640 × 2560 | 5.248 each | 80 | 0.253021 / 0.254635 | 20.74 / 20.61 |
| expert down | IQ4_NL | 10 × 2560 × 640 | 9.216 | 20 | 0.202396 | 45.53 |

Layer-2 IQ3_S expert gate/up instead read 7.04 MB each and reach
23.00/23.56 GB/s. Its Q8 QKV/gate reach 96.65/97.44 GB/s; do not mix these
with layer 0's Q6 formats.

The baseline has 32 work-items per row: two SG16 subgroups or one SG32,
one work-group per row. Each work-item does K/32 products, and reads scalar
packed bytes through `element`. Approximate source-level byte accesses per
product are Q8/IQ4: 3, Q6: 5, IQ2/IQ3_S: 6 plus grid lookup. These repeated
scale/index/sign loads may hit cache; they are **not DRAM traffic counts**.
There are six work-group barriers per row. No explicit vector load/alignment
contract exists in the old source; compiler-generated vectorization is unknown.

The whole ordinary GDN GEMV sequence reads 91,939,840 bytes in 19 launches:
**2.4194275 ms / 38.0007 GB/s**. Kernel sums are 2.416874 ms, while median
queue gaps total only 0.002398 ms. Host submission (0.147387 ms) overlaps
execution. The small-kernel floor is roughly 0.02–0.09 ms **including useful
work and underfill**; it does not isolate launch cost. In particular the
four-row injection has only four old work-groups with 320 products per lane.
No empty-launch cost has been measured or subtracted.

The receipt records device name and driver, not compute units, vector engines,
register usage or occupancy. We therefore do not infer occupancy from a
presumed Xe-core-to-SYCL-unit mapping. During the coordinator's run the new
submission records `sycl::info::device::{max_compute_units, local_mem_size,
max_work_group_size, sub_group_sizes}` from the already-owned queue. No extra
queue or enumeration is created. Actual register/resident-wave occupancy
remains unknown even with those properties.

## New kernels

[kernels.cpp](kernels.cpp) and [reference.hpp](reference.hpp) implement:

- **kopt_sg16 / kopt_sg32:** four independent row-owning subgroups per
  work-group, 64/128 work-items. A packed row is staged once into local memory
  through coalesced consecutive **16-byte `sycl::vec<uint32_t,4>` loads**.
  Packed blocks are *not* aligned16: their 18/34/82/98/110/210-byte sizes make
  that assertion false. Allocations must be aligned16; each row has a bounded
  scalar prefix/tail around its aligned interior, with no overread or repack.
  Adjacent lanes stage adjacent 16-byte segments. Local row stride is rounded
  to 16 bytes; arithmetic never reads padding. One work-group barrier follows
  staging; the reduction uses subgroup shuffles only.
- **Block reuse:** each lane decodes eight consecutive columns at a time.
  IQ2 shares one grid/sign/scale across eight weights; IQ3_S shares two grids
  and one sign/scale; Q6 shares a scale across eight weights; Q8 and IQ4 share
  their scale. Other formats retain their existing per-element equations.
  No weight rounding, FMA contraction, quantization change or cache compression.
- **Raw F32/F16/BF16:** aligned direct 32-/16-byte weight loads and 16-byte
  activation loads bypass local memory. Scalar fallback covers unaligned or
  short tails; this avoids staging 40 KiB per injection row.
- **kopt_fused_sg16:** one submission for up to four independent matrices,
  with per-matrix shape/type/input/output descriptors. The prepared comparison
  combines injection + alpha + beta + HC down. This is a fixed-input diagnostic:
  their actual model dependencies do not establish that all four inputs are
  simultaneously ready. It is not a valid fused model layer yet.

The 5120–17408-row range yields 1280–4352 groups; measured QKV yields 2560,
IQ2's ten experts 1600 and IQ4's ten experts 6400. Injection still has only
one group. More groups alone do not prove occupancy. The largest measured
packed row is Q8 HC down: 10880 B, or **43520 B local memory/work-group**.
Fused raw groups inherit that maximum reservation; this can reduce occupancy
and regress speed. Device resource limits are checked before submission.

All bindings remain device Arena handles, with checked extents, disjoint
allocations, tracked dependencies and original orderly shutdown. Invalid
routes emit canonical NaN and status 1 without reading weights or activations.
Tail rows participate in the barrier/shuffles but cannot write out of bounds.

Explicit vectors and alignment were checked in source. CPU-only attempts to
emit device LLVM with installed icpx/clang returned `IR output is not
supported`; final ISA load lowering remains unverified. No GPU binary was
run to inspect it.

## Deterministic arithmetic contract

Kernel name pins subgroup S=16 or 32. For lane l, start at positive zero and
visit chunks `8*l + n*(8*S)` in ascending n; within each chunk visit j=0..7,
skipping columns outside K. Each decoded weight preserves packet 2's exact
multiply boundaries. Round `weight * activation` to FP32, then round the
addition to the lane accumulator separately. No FMA or reassociation.

The tree stages have widths 1,2,4,...,S/2. At each width, lane l divisible by
2*width adds its accumulator to the **pre-stage** accumulator at l+width.
All subgroup lanes perform the shuffle; only the left roots add. Lane 0 then
casts once to BF16/F16. CPU uses the identical adjacent-pair tree. A separate
recursive-tree CPU test evaluates scalar `element` values independently of
`decode8` and the new lane helper.

This is a **new arithmetic identity**, not proof of equality to the old
strided-32 tree or the certified model. CPU receipts report old-tree FP32 and
final-output differences separately. Any changed output is not adopted into
the unchanged model path. The owner's requested same-tree device/CPU gate
must pass before timing; full-model oracle parity and fresh-process device
repeats remain later gates under [Determinism is an interface](../../DESIGN.md#determinism-is-an-interface).

## Expected gains: arithmetic targets, not measured results

For the same packed bytes, a 2×/4× time improvement gives exactly 2×/4×
effective GB/s. These are preregistered **working target scenarios**, not
predictions or a new benchmark. Reuse reduces source-level scale/grid loads
by up to eightfold, but products, cache effects, SLM and occupancy remain.
The coordinator's measurements can reject any target, including regression.

| Class / representative matrix | 2–4× target GB/s | Mechanism and limit |
| --- | ---: | --- |
| Q6 QKV / gate | 124–248 / 119–239 | Vector staging, eight-weight scale reuse, 6→1 barriers |
| Q8 HC up | 155–309 | Vector staging and eight-weight scale reuse |
| Q8 HC down | 58–116 | Same changes; high SLM and few rows may dominate |
| IQ2 expert gate / up | 41–83 | One grid lookup per eight weights; routes unchanged |
| IQ3_S expert gate / up | 46–94 | Two grid lookups per eight weights |
| IQ4 expert down | 91–182 | Scale reuse and subgroup tree |
| Raw tiny projections | no credible standalone bandwidth prediction | Vector loads; sparse row count remains |

QKV's weight-only floor is 0.042414 ms at 507 GB/s, versus 0.347500 ms
measured. The four fused candidates total 4,628,480 B and sum to 0.2536985 ms
in the old isolated timings. An optimistic perfect-overlap model taking the
slowest old component (0.119584 ms) gives **2.12× / 38.70 GB/s**. Shared
resources and real activation dependencies make this an illustrative upper
opportunity, not an expected measured saving. The new harness directly compares
fused events with four separate optimized event spans instead of subtracting
an invented launch constant.

## CPU preparation and the two card-3 commands

[validate.py](validate.py) compiles the native targets and executes only the
host executable and mocked Python checks. [build receipt](build-receipt.json)
retains commands, source/binary hashes, CPU checks and compiler flags. It
removes its own scratch by default. This preparation passed **10 protocol tests**,
**207,360 scalar-vs-bundled decode values** and **1,416 independent-tree CPU
row comparisons**, with 27 fixture hashes matching packet 2 and one fresh
process repeat (two executions). The CPU comparison recorded **134 FP32
accumulator differences from the old tree and zero final 16-bit differences**
on these fixtures; this is limited fixture evidence, not full-model parity.
The prepared device window contains **272 cases**: old 108, SG16 54, SG32 54,
fused 56. These device cases have not run. To prepare new ignored build inputs for
the coordinator, from the repository root:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet6-kopt/validate.py --keep-build
```

Use the installed oneAPI environment (`source /opt/intel/oneapi/setvars.sh`)
in the coordinator's shell. After card-3 health/window admission, run these
**two commands in order**, once each. Output directories must be new:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet6-kopt/tests/device_window.py --authorized-device-window --card 3 --output experiments/own-xpu-runtime/stage2/packet6-kopt/build/exactness-card3
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet6-kopt/tests/device_timing.py --authorized-device-window --card 3 --exactness experiments/own-xpu-runtime/stage2/packet6-kopt/build/exactness-card3/window.json --output experiments/own-xpu-runtime/stage2/packet6-kopt/build/timing-card3
```

The new [exactness wrapper](tests/device_window.py) extends the packet-2
fixture protocol with named kernels and reuses its journal fault watcher.
It preserves baseline dequant/GEMV/routed checks, adds both optimized subgroups
and fused outputs, verifies FP32 bytes and final 16-bit bytes, and mutates
activation signs and route IDs/spans. The [timing wrapper](tests/device_timing.py)
requires the matching hash-bound successful exactness receipt. It measures
all four layers' real shapes baseline/SG16/SG32 side by side, the old/new
ordinary-layer GEMV sequence and the fused diagnostic. Each timing row reports
packed bytes, 20 events, median/min ms, GB/s and baseline/candidate ratio.
Variant order is fixed baseline→SG16→SG32 for each shape; cache/order effects
are not balanced, so the results remain screening diagnostics. Four bounded
owner sessions (one per layer) avoid overflowing the 4096-event
ledger. All layer weights remain device-resident together as in packet 2.
Samples are bounded real packed rows tiled to real shapes, not full payloads.

One cooperative signal on a fault/deadline, no retry or hard kill, five-second
postflight journal tail, refusal latch and safe owner teardown remain in force.
The coordinator still owns independent external idle/health confirmation.
Warm operator timings cannot qualify a cold-prompt benchmark or predict tok/s.

## Credit and retained lessons

Conceptual credit: [IDEAS.md](../../IDEAS.md) pins llama.cpp/ik_llama.cpp
MMVQ unpack reuse and exllamav3 tile scheduling. No external kernel code was
copied, adapted or linked; normative GGUF tables retain packet 2's format
credit. Intel SYCL is a platform dependency.

The [Q4 subgroup correction](../../../../notes/2026-05-06-q4-gemv-corrected-subgroups.md)
and [Q8 subgroup negative result](../../../../notes/2026-08-10-q8-vdr2-c1-shape-subgroups.md)
show why geometry alone is not a speed guarantee. The [memory/step lesson](../../../qwen38-flash-next-fp8-b70/notes/2026-09-05-day-summary.md)
requires preserving allocation class and resident footprint while timing.
The exact phrase “Triton loaded offsets need alignment” was not found in the
searched notes; this implementation instead asserts and handles alignment
explicitly at each load boundary.
