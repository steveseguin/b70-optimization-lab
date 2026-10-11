# Packet 7 — GEMV optimization round 2

CPU preparation only. No device executable was run in this task. The coordinator
owns card 3. Packets 2 and 6 remain unchanged baselines; these new kernels are
selected by name. Device exactness, the attainable ceiling and speed are pending.
This packet makes no model-quality, losslessness-versus-the-certified-model or
headline performance claim.

## Start with the measured fused result

The [round-1 native receipt](../packet6-kopt/receipts-card3-20261011/timing/layer0/native.json)
measured **0.261771 ms fused versus 0.323229 ms separate**, a **1.234777×**
ratio, for SG16 injection + alpha + beta + HC down. That diagnostic still costs
262 microseconds; it is not a 17-microsecond fused layer. The whole ordinary
GDN GEMV sequence took **2.520469 ms SG16 versus 2.4144795 ms baseline**:
SG16 was 4.39% slower there. These are 20-sample warm event medians.

That same receipt already batches all ten selected experts in **one routed
launch per matrix, three per MoE block**, using a device route table. Thirty
launches describes a naive per-expert loop, not the measured packet-6 control.
Round 2 preserves the three-launch comparison and adds a one-launch diagnostic.

## First stage: measure this card's ceiling

Both coordinator commands begin with [ceiling.cpp](tests/ceiling.cpp), before
any GEMV in that command. It allocates **64, 128 and 256 MiB device buffers**
and runs:

- `stream16_sum_u64_v1`: 32,768 work-items, 128/group, SG32. Each reads an
  aligned `sycl::vec<uint32_t,4>` (16 B) per iteration, stepping by 32,768
  vectors. Four uint32 values contribute to a uint64 sum written per work-item.
  The unsigned sum is deterministic, exact and cannot be optimized away.
- `device_memcpy`: the same owned queue copies the full device buffer to a
  second device allocation. This uses SYCL memcpy through the owner's tracked
  compute operation, allowing a single 256 MiB **device-to-device** event;
  host staging still uses the existing bounded 8 MiB CopyEngine transfers.

Every size runs two different index-dependent patterns. Every copied byte and
every streaming sum is read back and checked. One untimed warmup and 20 queued
SYCL event intervals match the GEMV timing method. Allocations, upload, CPU
checks and readback are outside the timed interval. Peak explicitly owned
memory is **512.25 MiB device + 8 MiB pinned host**; driver shadows remain
unknown. The buffers are released before the next owner session.

Read GB/s counts input bytes/time. Copy reports **payload GB/s** and separately
**read + write GB/s = 2 × payload GB/s**. These are distinct metrics. Fixed
resident buffers may benefit from caches; the 64→256 MiB size ladder makes that
visible, without host cache drops. The attained streaming result includes its
sum instruction cost and 256 KiB of output, whose bytes are excluded from the
read numerator. It is an access-pattern ceiling, not a universal DRAM maximum.

The receipt adds cache-line size and Level Zero EU/subslice/slice/thread
properties from the already-owned queue. It creates no extra device owner.
Once measured, regenerate the forecasts with:

```bash
nice -n 19 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet7-kopt2/analysis.py --ceiling experiments/own-xpu-runtime/stage2/packet7-kopt2/build/timing-card3/ceiling/native.json --output experiments/own-xpu-runtime/stage2/packet7-kopt2/build/measured-ceiling-analysis.json
```

The scalar C then becomes the median of the two 256 MiB streaming medians.
All individual sizes, patterns and copy rates remain in the native receipt.
No fastest-size selection is used.

## What occupancy can and cannot explain

Round 1 records **256 SYCL compute units**, **131,072 B local memory**,
**1,024 maximum work-items/group**, and subgroup sizes **16 and 32**. It
explicitly says occupancy was not measured. It contains **no cache-line size,
Xe-core mapping, hardware threads/EU, register usage or resident-group count**.
The maximum group size is a per-group legality bound, not a device-wide
occupancy number. Those missing facts cannot honestly be recovered from this
JSON. [analysis.py](analysis.py) and [analysis.json](analysis.json) retain the
missing fields and distinguish recorded inputs from assumptions.

For a transparent planning calculation, assume those 256 units are vector
engines arranged as **32 Xe-core-like subslices × 8 EUs**, with **8 hardware
thread slots/EU** and SIMD16 execution. This is a **conditional capacity
model**, to be checked against the new properties, not an observed B70
occupancy measurement. It gives 2,048 hardware thread slots, 32,768 logical
lanes, 1,024 SG32 subgroups or 256 groups of 128 work-items before register,
SLM and scheduler limits. Each SG32 occupies two SIMD16 contexts in this model.

| Rows | Round-1 SG32 groups (4 rows/group) | Total work-items | Conditional waves of 256 groups | Split2 / split4 groups | Wide two-row groups |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 5,120 | 1,280 | 163,840 | 5 | 2,560 / 5,120 | 640 |
| 10,240 | 2,560 | 327,680 | 10 | 5,120 / 10,240 | 1,280 |
| 17,408 | 4,352 | 557,056 | 17 | 8,704 / 17,408 | 2,176 |

These are **scheduled totals**, not threads simultaneously in flight. The
large rows already supply several waves. Split-K cannot be justified simply
by calling that global grid too small. At one outstanding 16 B vector per
logical lane, the conditional full device has **524,288 B in flight**
(256 B per SIMD16 hardware thread). At 507 GB/s that covers about **1.03 µs**
of latency; actual outstanding loads, latency and occupancy are unknown.

A 5,120-column **IQ3_S** row is exactly **2,200 B**: 68.75 B/lane averaged
over SG32, or **4.297 16-byte loads/lane**, roughly 4–5 staging iterations
plus scalar alignment edges. IQ3_XXS is 1,960 B, 61.25 B/lane, about 3–4
iterations; the two formats must not be conflated. The measured Q6 QKV row
(K=2,560) is 2,100 B, 65.625 B/lane, also roughly 4–5 iterations. IQ2 expert
rows are just 820 B, about 1–2 staging loads/lane; IQ4 down rows are 360 B,
less than one vector per lane on average. These short bursts offer little
per-thread memory-level parallelism, followed by a barrier and serial unpack /
FP32 work (80 products/lane at K=2,560, 160 at K=5,120). They are plausible
latency/issue bottlenecks, not proof that latency alone caused the 17% rate.

SLM is another concrete limit: Q6 QKV uses **8,448 B/group** in round 1,
allowing 15 groups by a 128 KiB SLM-only bound. Long Q8 HC down uses
**43,520 B/group**, allowing only **3**; under the conditional 32-core model
that caps it at 96 groups / 384 SG32 subgroups / 12,288 lanes, 37.5% of the
thread-only bound. Registers and scheduling can lower this further. Its wide
variant uses **87,040 B/group**, only one SLM-resident group/core: wider loads
can regress this case. Split-K removes whole-row SLM entirely.

## New kernel identities and arithmetic

[kernels.cpp](kernels.cpp) is original lab SYCL; [reference.hpp](reference.hpp)
is its separately callable CPU arithmetic contract. Packet 6's own decode8
helpers and packet 2's normative tables retain their existing attribution.

- **`splitk2_v1`, `splitk4_v1`**: each output row has S=2 or 4 subgroups,
  four independent `(row, split)` tasks per 128-item group. Split the
  `ceil(K/256)` contiguous tiles at `floor(tiles*s/S)`. Each subgroup reads
  only its K range directly from global packed memory, reusing decode8 scales
  and signs. No whole-row staging or work-group barrier is needed. It writes
  `workspace[logical_row*S+s]` as FP32. A second **owned** event reduces S
  partials per output in fixed order, then casts once. Workspace is
  `count*span*S*4` bytes (409,600 B for 25,600 routed rows at S=4).
- **`rows2_vec32_v1`, `rows2_vec64_v1`**: four SG32 subgroups/group, each
  handles **two rows**, with distinct accumulators and the existing SG32
  arithmetic. Packed row interiors use `sycl::vec<uint32_t,8/16>` loads,
  unrolled byte unpack and unrolled eight-product loops. Bases are checked
  aligned64; each actual 32/64-byte vector address is aligned after a bounded
  scalar prefix. No packed-block alignment is assumed; tails never overread.
  Raw formats bypass SLM, with direct 32 B F32 / 16 B F16-BF16 vector groups
  where aligned, and bounded scalar fallbacks.
- The same descriptor kernel accepts up to eight independent matrices and
  resident route tables. The routed diagnostic covers all **ten experts ×
  three matrices** with group selection by matrix, expert slot and row block.
  SG32 controls and wide variants also keep the valid **three-launch** path.
- Six small projections (`hc_attn_inject`, `hc_ffn_inject`, `ssm_alpha`,
  `ssm_beta`, `ffn_gate_inp`, `ffn_gate_inp_shexp`) are measured in one launch
  against six separate launches with the **same wide variant**. Both vector
  widths are tested. This avoids giving the tiny raw groups the HC-down SLM
  reservation that burdened round 1's fused test.

Within split s, lane l starts at +0 and visits columns
`begin_s + 8*l + 256*n`, increasing n, then j=0..7. Decode expressions retain
packet-2 multiplication boundaries. FP32 multiply and add round separately;
FMA, fast math and reassociation are disabled. The lane tree joins adjacent
pairs at widths 1,2,4,8,16. The second pass loads partials in increasing s,
then uses the adjacent-pair S tree: S2 is `p0+p1`; S4 is
`(p0+p1)+(p2+p3)`. Empty partitions are +0. This order is versioned **v1**,
including the positive-zero behavior. FP32 bytes and final BF16/F16 bytes
are both compared; CPU tests independently decode scalar elements and use
recursive trees. Invalid routes/tails retain canonical NaN and error status
without dereferencing invalid weights or activations.

The wide variants preserve packet-6 SG32 order. Split-K changes the arithmetic
identity, as authorized for this experiment. New-oracle parity is not parity
to the certified full-model output. No variant is enabled in model execution.

**Fusion is an independent-input diagnostic.** Real expert down depends on
activation(gate, up); the one-launch three-matrix test supplies prepared down
inputs and does not compute that dependency. Likewise the six small matrices
are not necessarily ready together in a real layer. The existing three-launch
expert form is useful directly; one-launch model MoE needs separately designed
nonlinearity and cross-work-group dependency handling. No barrier across
work-groups is invented here.

## Predicted GB/s — hypotheses, not measurements

The [analysis artifact](analysis.json) lists **all 79 kernels** with row bytes,
loads/lane, old/new SLM and predictions for both variant classes. Until the
ceiling run, **C=507 GB/s is only a historical scenario**. Forecast each
kernel as `GB/s = W / (passes*17,000 ns + W/(C*f))`, where W is packed active
weight bytes. Passes is one for wide, two for split-K. The 17 µs value is the
observed small-operation floor, not an isolated measured launch cost; adding
it is deliberately a rough cost model. Neither these ranges nor the efficiency
fractions f are confidence intervals or guaranteed lower/upper bounds.

Hypothesized stream fractions: Q6 30–50%, Q8 40–65%, IQ2 22–40%, IQ3_S
25–45%, IQ4 35–60%, raw 40–70%. Wider issue and scale reuse motivate trying
these fractions, but no occupancy equation establishes them. Raw injection
still has only a handful of groups; the prediction is especially optimistic.
SLM pressure, decode dependencies and a second launch can make any arm slower.

| Layer-0 kernel | Wide prediction GB/s | Split-K prediction GB/s |
| --- | ---: | ---: |
| hc_attn_down | 101.9–126.3 | 68.0–78.1 |
| hc_attn_up | 101.9–126.3 | 68.0–78.1 |
| hc_attn_inject | 9.2–9.4 | 4.7–4.8 |
| attn_qkv | 135.8–211.2 | 122.6–181.0 |
| attn_gate | 126.7–190.0 | 108.6–152.0 |
| ssm_alpha | 25.3–26.7 | 13.5–13.9 |
| ssm_beta | 25.3–26.7 | 13.5–13.9 |
| ssm_out | 126.7–190.0 | 108.6–152.0 |
| hc_ffn_down | 101.9–126.3 | 68.0–78.1 |
| hc_ffn_up | 101.9–126.3 | 68.0–78.1 |
| hc_ffn_inject | 9.2–9.4 | 4.7–4.8 |
| ffn_gate_inp | 122.3–165.0 | 87.6–107.5 |
| ffn_gate_exps | 81.9–122.4 | 64.7–87.6 |
| ffn_up_exps | 81.9–122.4 | 64.7–87.6 |
| ffn_down_exps | 133.7–194.9 | 107.2–143.3 |
| ffn_gate_shexp | 52.0–60.3 | 31.4–34.2 |
| ffn_up_shexp | 52.0–60.3 | 31.4–34.2 |
| ffn_down_shexp | 68.0–78.1 | 40.9–44.3 |
| ffn_gate_inp_shexp | 0.6–0.6 | 0.3–0.3 |

For the ceiling kernels themselves there is no defensible new numeric prediction:
the historical 507–537 GB/s came from other workloads. Their purpose is to
replace that assumption. Stream and copy can disagree because their execution
engines, stores and instruction costs differ.

## Tests, timing receipts and the two commands

The CPU-only [validator](validate.py) builds with installed icpx 2026.0.0,
`-fsycl`, C++20, `-fno-fast-math -ffp-contract=off -fdenormal-fp-math=ieee`.
Only `host-tests` and Python stdlib tests execute. ELF dependency inspection
refuses a host executable linked to SYCL, Level Zero, UR or OpenCL. No GPU
binary is invoked, even for help/version. Builds use nice19, OMP=2 and two jobs;
all output lives in this packet's ignored `build/` and is deleted by default.
The [build receipt](build-receipt.json) retains exact commands, source/binary
hashes, CPU results and cleanup status. Final checks passed: **16 Python
protocol tests, 207,360 scalar-vs-bundled decode values, 2,832 independent
row comparisons plus 200 long-row comparisons, 1,056 vector-footprint
checks and 196,608 streaming lane checks**, with one fresh CPU-process repeat.
The original-size fixtures differ from packet 2 in 264 FP32 accumulators
and zero final 16-bit outputs; that does not establish full-model parity.
All three SYCL executables compiled, and the build scratch was removed.

CPU tests cover all ten stored formats, both activation/output formats,
activation-sign changes and signed zeros, odd raw tails, long K up to 17,408,
empty/uneven split partitions, separate FP32 checks, all 32/64-byte alignment
residues and byte guards. The host output includes counts and a fingerprint,
repeated in a fresh CPU process. The prepared device gate has **494 cases**:
54 each for the SG32 control and four new variants, plus 112 each for the two
fused wide variants. These include changed expert IDs/spans, invalid routes,
three-matrix ten-slot routing, five mixed matrix types, output tails and
FP32/final-16-bit byte comparisons. An additional **12 ceiling checks** cover
both patterns, both operations and all three sizes. Device passes remain
pending; a CPU comparison does not prove a compiled shader is bit-exact.

Timing requires a matching successful, hash-bound exactness receipt. Each
kernel gets one untimed warmup and 20 events; split-K records **both native
pass intervals plus their inclusive first-start → second-end span**. The
validator rejects a result missing either pass or omitting the inter-pass gap.
All real layer shapes use resident full-sized banks with bounded real packed
sample rows tiled through them, as in packet 6. They are operator diagnostics,
not a complete checkpoint execution or cold-prompt benchmark.

Six bounded timing owner sessions prevent the 4,096-event ledger overflowing:
ceiling, four separate layer kernel sessions, then the layer-0 sequence/fused
session. The grouped session reloads the same full resident layer; weights are
never shrunk to the ten chosen experts. Four groups compare 6→1 small launches
and 3→1 expert launches at both vector widths. Whole-sequence control and wide32
remain sequential, independent-input GEMV diagnostics. Variant order is fixed
SG32 → split2 → split4 → wide32 → wide64, not balanced; cache/order effects and
single-window drift preclude a speed verdict or promotion.

The watcher reuses packet 2's journal boundary, specific fault signatures,
one cooperative stop, five-second postflight, refusal latch and safe owned
teardown. No retry, reset, reboot, hard kill, server, Docker or systemd action
is introduced. The coordinator must admit card 3 independently; these commands
do not override host health or ownership decisions. All allocations are device
memory except bounded pinned transfer slabs; driver host shadows are unknown.

Because preparation deletes its own scratch, first rebuild CPU inputs (no GPU)
in the installed oneAPI environment:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet7-kopt2/validate.py --keep-build
```

Then the coordinator runs these **two commands in order**, once each, after
card-3 admission. Output directories must be new:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet7-kopt2/tests/device_window.py --authorized-device-window --card 3 --output experiments/own-xpu-runtime/stage2/packet7-kopt2/build/exactness-card3
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet7-kopt2/tests/device_timing.py --authorized-device-window --card 3 --exactness experiments/own-xpu-runtime/stage2/packet7-kopt2/build/exactness-card3/window.json --output experiments/own-xpu-runtime/stage2/packet7-kopt2/build/timing-card3
```

## Credit and next decision

Our kernel code builds on our packets 2 and 6 and the stage-1 packet-3 owner.
Conceptual credit follows the exact pins in [IDEAS.md](../../IDEAS.md):
llama.cpp / ggml-org and ik_llama.cpp / ikawrakow for block-local unpack reuse,
exllamav3 / turboderp for register-prefetch/tile scheduling and fixed final
reductions. No external runtime kernel code was copied or used as a base.
Intel SYCL and Level Zero are platform dependencies.

The [Flash memory-class note](../../../qwen38-flash-next-fp8-b70/notes/2026-09-05-day-summary.md)
shows that whole-bank residency can dominate isolated timings; preserve it.
[Q4 subgroup evidence](../../../../notes/2026-05-06-q4-gemv-corrected-subgroups.md)
and [Q8 geometry negatives](../../../../notes/2026-08-10-q8-vdr2-c1-shape-subgroups.md)
warn against assuming wider vectors or more subgroups guarantee speed.
The [LTX diagnosis](../../../ltx25-b70/notes/dispatch-bound-diagnosis-01.md)
credits the historical copy roofline, while the
[later correction](../../../../notes/2026-10-10-sampler-feasibility.md)
explains why it cannot determine this workload's ceiling. Searches for
“Triton loaded offsets” found no exact note; “Triton loaded” in the June 16
handoff instead concerns a SYCL/UR library mismatch, not alignment. This
packet states and tests its own vector-address alignment contract.

Next is the coordinator's ceiling → exactness → timing window. Compare measured
whole-operation spans, including both split passes, to SG32. If split-K loses
on already well-populated grids, retain that evidence and pursue decode issue
cost / register pressure instead. If wide rows lose on HC down, the explicit
SLM bound gives the next lever: smaller tiles or direct block reads. No lane
is declared finished, and no changed arithmetic is silently adopted.

## Device results — card 3, 2026-10-11 04:3x UTC (boot 13858eef)

Exactness: all 494 device cases PASS (kopt_sg32 54, splitk2 54, splitk4 54,
rows2_vec32 54, rows2_vec64 54, fused_rows2_vec32 112, fused_rows2_vec64 112),
zero kernel fault lines. Receipts: [receipts-card3-20261011/](receipts-card3-20261011/).

**Attainable ceiling on this card** (64 MiB, 16-byte streaming read with a
deterministic u64 sum): **589-593 GB/s** payload; device memcpy 271 GB/s one way
(542 GB/s read+write). So the practical target is ~590 GB/s, not 507.

| Weight (layer 0/3) | MB | kopt_sg32 GB/s | splitk2 | splitk4 | rows2_vec32 | best |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| ffn_gate_inp (F16 router) | 5.24 | **289** | 217 | 210 | 95 | sg32 |
| attn_qkv (Q6) | 21.50 | **88** | 78 | 59 | 40 | sg32 |
| attn_gate | 12.90 | **78** | 77 | 59 | 34 | sg32 |
| attn_q (layer 3) | 25.80 | **93** | - | 59 | - | sg32 |
| ssm_out / attn_output | 12.90 | 61 | 77 | **81** | 20 | splitk4 (1.33x) |
| hc_attn_down / hc_ffn_down | 3.48 | 40 | 62 | **101** | 10 | splitk4 (2.5x) |
| hc_attn_up / hc_ffn_up | 3.48 | **81** | 40 | 22 | 55 | sg32 |
| ffn_*_exps (10 experts, IQ2_S/IQ3_S) | 5.25-9.22 | **50-68** | - | 19-26 | - | sg32 |
| ffn_*_shexp | 1.34-1.74 | **51-73** | - | 35-38 | - | sg32 |
| hc_*_inject (0.16 MB) | 0.16 | 2.7 | 3.0 | **5.3** | 0.9 | splitk4 (launch floor) |
| ssm_alpha / ssm_beta | 0.49 | 28 | 26 | **33** | 9 | splitk4 |

Reading: the plain F16 router matrix reaches 289 GB/s with the same GEMV
framework, so the framework can stream at half the ceiling; the quantized grids
stall at 50-100 GB/s because the per-weight **decode** (codebook lookups,
sign bits, scales) is the bottleneck, not the loads. Split-K helps the
"down"-shaped matrices (large K, few rows) 1.3-2.5x and hurts the "up"-shaped
ones; the two-rows-per-subgroup wide-load variants are worse everywhere and are
dropped. The fused and sequence entries were not populated in this run.
Round 3 targets the decode path itself and a shape-aware variant table.
