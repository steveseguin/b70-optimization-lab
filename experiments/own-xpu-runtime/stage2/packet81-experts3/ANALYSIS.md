# Packet81: production expert decode analysis

CPU-only analysis, 2026-10-17. Target: `iq3-p49-split32-v1`, compact IQ2_S
gate/up and IQ4_NL down, production wide64. No GPU opened, no service started.
This first milestone precedes candidate work.

## Fresh BMG-G31 offline compilation

`inspect_registers.py production` uses Intel 2026.0, strict FP32 flags, the
required linked device libraries, SPIR-V translation and CPU-only ocloc.
The production driver instantiates the actual wide64 kernels. Packet70 reuses
packet65's binary: the five directly relevant source headers were checked
byte-identical, and the established packet65 checked include mirror supplies
the owner ABI remapping. A first raw include attempt failed on duplicate owner
ABI definitions; its compiler diagnostic is retained, not a device failure.
The production driver also instantiates two inherited kernels through bind;
only the two p65 wide64 entries below belong to this comparison.

[Compiler commands, library hashes, assemblies](register-report-production.json),
[instruction mix](evidence/instruction-mix.json). Counts are static assembly,
including alternate exceptional paths. They are **not dynamic operation counts**.
The ALU column counts compiler ALU-pipe annotations, including moves/conversions.

| Kernel | Instructions | Loads | Integer ALU annotations | Float ALU annotations | Math | Configured GRFs | Spills / SLM loads |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| IQ2_S gate/up | 1993 | 51 | 1084 | 595 | 1 | 128 | 0 / 0 |
| IQ4_NL down | 2955 | 79 | 2102 | 639 | 1 | 128 | 0 / 0 |

The loop body has 849 integer + 554 float annotations per 64 weights for
IQ2, or 21.922 static annotations/weight; IQ4 has 1912 + 584 per 128 weights,
or 19.500/weight. These envelopes include mutually exclusive half-conversion,
NaN and route-tail paths; multiplying them into an executed-instruction claim
would be wrong. Half subnormal normalization also has a data-dependent loop.
The final reduction uses two subgroup selects for gate/up and one for down;
SIMD32 lowering uses respectively four and two indirect register moves.
Local V8/V16 trees preserve 7/15 adds per physical lane, outside the K loop.
Reduction shuffles are therefore a small, once-per-row cost.

IQ2 has an 8192-byte constant grid (1024 entries of eight magnitudes). The
compiler already combines the two source words into one `load.ugm.d32x2.a64`
per eight decoded weights: eight such grid loads in the 64-weight loop.
It is constant data addressed through UGM, **not SLM**, and its cache hit rate
is unknown. Four raw code/metadata loads serve 64 weights. Each eight BF16
inputs lowers to four scalar d32 UGM loads: **32 activation loads** per loop.
IQ4's sixteen signed levels already live in four immediate register banks
(`p33::level_bank`): no memory LUT access. Four raw code vectors plus four
halves serve 128 weights; **64 activation loads** serve their inputs.
There is substantial integer extraction, selection, conversion and address
work in both kernels, beyond the three FP32 multiply/multiply/add operations
per ordinary weight. IQ2 also has dependent grid addressing and sign work.

## Bounds and limiter

Packet77's raw event samples give approximately 61.54 / 52.19 microseconds
per gate/down call on rank0, and 62.12 / 52.64 on rank1. Per-half 1.4769 /
1.2525 ms are sampled-call estimates times 24, not fully measured half sums.
Useful packed weights per call are 10,496,000 / 9,216,000 bytes, corresponding
to 32,768,000 / 16,384,000 weights. At the supplied 555 GB/s reference the
weight-only times would be 18.91 / 16.61 us. That is an optimistic reference,
not an achievable bound: activation transactions, grid loads, instruction
issue, latency and occupancy are omitted. Packet77 includes a small amount
of additional useful input traffic in its reported effective bandwidth.

A compute bound must use **executed** operations and effective issue capacity:
`t >= max(B_effective / BW_effective, Nweights * ops_per_weight / R_effective)`.
The three ordinary FP32 operations require 98.304 / 49.152 million operations
per call, or 1.597 / 0.942 TOP/s at the measured times. A deliberately loose
all-static-path envelope is 718.336 / 319.488 million ALU annotations, requiring
11.673 / 6.122 trillion scalar-lane annotations/s at those times. SIMD widths,
masking, integer/float issue sharing and branches prevent equating those
annotations to peak FP32 FLOPs. At an explicitly hypothetical effective
10 trillion annotations/s, that envelope costs 71.83 / 31.95 us; at 20 it
costs 35.92 / 15.97 us. These are sensitivity estimates, **not hardware rates
or performance predictions**. CPU-only assembly cannot provide the actual
ops/time roof or cache latency. No unsupported numeric occupancy is invented.

The supported working diagnosis is **decode/issue latency: sign/scale and
level unpack plus fragmented activation loads**, with dependent IQ2 table
lookup latency secondary. It is not proven DRAM saturation. Both kernels use
128 configured GRFs, no scratch spills, and WG64/SG32. Gate has 800 workgroups
and down 800, each with two subgroups. These are scheduled totals; resident
occupancy and stall reasons remain unmeasured. Prior WG64/WG128, prefetch and
experts2 failures do not support another occupancy-only geometry sweep.

## Decision before candidates

- SLM grid staging: closed by packets52/53, including persistent staging;
  same fill/barrier mechanism is not reopened without a distinct benefit.
- Multiweight grid lookup: already eight weights per packed 64-bit lookup.
  A second adjacent code has an independent index; it cannot share that lookup.
- Gate/up shared scales: separate weight tensors have independent halves,
  scale nibbles, codes and signs. Only the activation input is shared.
- Register IQ4 LUT: already implemented; do not relabel it as a new candidate.
- SIMD16: defer. It changes physical mapping without removing the decode
  sequence, and configured GRFs alone do not establish a residency benefit.
- **Test explicit packed activation loads**, separately gate and down, then
  combined if both survive. Load four uint32 words for eight BF16 inputs,
  unpack their original bits and keep every chain, product, sum and rounding.
  All input bases are device allocations and offsets are multiples of eight
  BF16 elements; no extra reads, new padding or decoded-weight buffer.
  This can remove 24/48 static load messages from the respective hot loops,
  unlike packet73's raw-weight-only load reduction. Require actual offline
  evidence of the reduction and no spills before admitting an engine screen.

Packet65's wide64 cut raw loads and gained about 5% end-to-end. Packet73's
experts2-a/b reportedly lost 0.98%/0.63% despite B reducing static raw loads;
that warning rules out treating instruction reduction as a speed result.
GNU/Intel byte fixtures, full production-shape post-load startup, sealed
shared-v4 plans and coordinator device gates still apply to any surviving arm.

## Resource and repository boundary

The requested pull --rebase refused unrelated unstaged orchestration files;
fetch then showed HEAD equal to origin/main. Nothing was stashed or changed.
Root has about 22 GiB free, below CURRENT's historical 50 GiB reserve. This
explicitly authorized bounded packet keeps additional build below 1 GB,
uses nice19, CPUs8-15/24-31 and an 8 GiB address-space ceiling. No cleanup or
host settings changed. Compiles are serial and foreign compiler processes
are checked before subsequent stages. All existing packet/screen/ops trees
remain read-only.
