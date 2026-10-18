# Packet 93: packed target-head decode diagnosis

CPU source audit of frozen packets 74 and 84, October 18 brief. This is a
mechanism diagnosis and preregistration, not a measured attribution of GPU
stalls. No device work was performed for this audit.

## Evidence and production identity

The production target head is `logits: p33.dense.segment` in packet 84
[`dispatch-speed6.json`](../packet84-record-bundle/dispatch-speed6.json).
[`p33_candidates.hpp`](../packet84-record-bundle/p33_candidates.hpp),
`p33::dense_lane<Q6_K,2560>`, reads the expanded signed codes and already
computed FP32 subscales. `p33::Kernel` in
[`p33_submit.cpp`](../packet84-record-bundle/p33_submit.cpp) uses SG32, one
32-work-item workgroup per row for this unsplit head. Each lane visits eight
consecutive elements at `lane*8`, then advances by 256. It accumulates the
eight products in order and uses the adjacent SG32 tree (widths 1,2,4,8,16).
Only after that reduction does it round the logit to BF16. Keeping a different
but mathematically equivalent dot-product order would fail this identity.

Packet 84 also includes `p49c::dense_lane` and `DenseKernel`, but
`p49c::dense_submit` admits Q8 K10240, Q8 K320 and Q6 K6144, not the Q6 K2560
target head. Its existence is not evidence that it is the production head.
Packet 74 packed heads use that `DenseKernel` with `Packed=true`, whose SG32
head workgroups have 256 work-items, eight rows per workgroup. This geometry
difference must remain explicit when reproducing packet 74.

Packet 74 [`p74_packed.hpp`](../packet74-packed-dense/p74_packed.hpp),
`load8`, `decode8<Q6_K>` and `lane<Q6_K,2560>`, contains the failed decode
mechanism. Its [`microbench.cpp`](../packet74-packed-dense/microbench.cpp)
compares the full 248320 by 2560 shape with alternating ordering, GPU event
timing, and a separate FP32 equality pass. Its production arm uses p33 WG32;
its packed arm uses WG256, matching the two actual head geometries. The only
retained microbenchmark evidence found is
[`microbench-build.json`](../packet74-packed-dense/evidence/microbench-build.json),
which explicitly says `device_executed=false`. There is no isolated-head
measured timing in that evidence to quote.

The actual failure is the lane-A engine screen: 13/13 exact, head-packed
53.674 tok/s against the two-control mean 54.09 tok/s, about -0.8%.
[`Packet 74 note`](../../../../notes/2026-10-17-own-runtime-packet74.md) and
[`DO-NOT-REPEAT`](../packet74-packed-dense/DO-NOT-REPEAT.md) close that mechanism
unless decode changes. The historical staging bursts, barriers and serial
unpack described there refer to packet 7; packet 74 itself has no SLM staging
or barriers in its SG32 head loop. Do not attribute those old barriers to it.

## What the source establishes

1. **Packing saves unique bytes but adds requested loads.** For every group of
   eight weights, packet 74 requests eight ql bytes and eight qh bytes. Across
   the 32 lanes of one block, ql bytes are requested twice and qh bytes four
   times: 512 requested code bytes for 192 unique code bytes. Its scale byte
   and half are requested by every lane. On an aligned block that is 608
   source-requested bytes including metadata; on the alternate block the two
   `load8` calls each add an alignment-repair word, raising this to 864.
   Production requests eight signed codes and one FP32 scale per lane: 384
   requested bytes, with 320 unique useful bytes. These are source requests,
   not DRAM transactions: cache/coalescing/broadcast can merge duplicates.

2. **The 210-byte block stride adds repair instructions.** Blocks alternate
   modulo four. `load8` aligns the address down and loads two words; the
   two-byte phase also loads a third word and shifts/ORs the results. The
   block-phase branch is uniform within the subgroup, not proven divergent.
   Its cost and compiler lowering still need assembly evidence. The head
   row is 2100 bytes, so row starts preserve the modulo-four phase.

3. **Plane decode is repeated per output element.** Each element extracts a
   byte from ql and qh, selects a nibble and a two-bit plane, combines them,
   subtracts 32, and converts to FP32. Section-dependent shifts depend on
   lane identity. The eight element decode expressions are independent; it
   would be incorrect to claim they form one necessarily serial chain.
   Each decoded weight does, however, depend on both plane loads and their
   repairs before it can enter the existing serial accumulator chain.

4. **Scale conversion moved back onto the device.** `iq3::half` in
   [`math.hpp`](../packet2/kernels/math.hpp) has normal, zero, nonfinite and
   subnormal paths, including a normalization loop for subnormals. Packet 74
   calls it per lane per block and multiplies by the signed subscale.
   Production loads this exact FP32 product, computed at load time by
   [`expanded.hpp`](../packet10-kopt5/expanded.hpp). The half is the same for
   all lanes within the block; source repetition is established, emitted
   redundancy and its measured cost are not. Preserve the exact product
   rounding and signed-zero behavior when changing this step.

5. **More live temporaries can raise register demand.** Packet 74 carries
   four plane words, alignment temporaries, decoded values, input values and
   scale work around the accumulator. Register pressure, spilling and lower
   occupancy are plausible consequences, not measured facts. A C++ `v[8]`
   alone does not establish actual register allocation or a spill. The
   different workgroup size is another possible contributor.

No retained SPIR-V, LLVM IR, vISA or assembly dumps were found in packet 74
or packet 84 build trees during this audit. Consequently the source explains
new work sufficient to make a loss plausible; it does not isolate which
hardware bottleneck caused the observed -0.8%. Offline compiler output was a
remaining diagnosis gate at this point; the addendum below closes that gate. Any new assembly findings must identify the exact
compiler flags, kernel and artifact, and must distinguish static operations
from device latency/occupancy measurements.

## New mechanisms

**Head-plane: four-byte parallel bit extraction.** Retain the original 210
bytes and replace eight scalar plane extractions with two four-byte integer
operations. For each four-element word pair, form
`((ql >> nibble_shift) & 0x0f0f0f0f) |
 (((qh >> plane_shift) & 0x03030303) << 4)`.
Then extract each byte, subtract 32, convert and apply the unchanged FP32
operations in the original eight-element order. The per-byte masks prevent
cross-byte contamination. This changes the integer decode schedule, while
retaining alignment repair, duplicate requests and scale conversion. It is a
small, separately falsifiable mechanism; static instruction reduction alone
is not a speed claim.

**Head-transpose: lane-contiguous codes in separate packed planes.** Repack
at load time, retaining exactly 210 bytes per 256 weights. For N blocks use
128N low-nibble bytes, 64N high-two-bit bytes, 16N scale bytes and 2N half
bytes, at offsets 0,128N,192N,208N. Within each code plane a lane owns eight
consecutive elements: one aligned u32 of eight low nibbles and one aligned
u16 of eight two-bit fields. These contain the same six-bit codes, and the
original byte layout can be reconstructed exactly. Each lane requests six
code bytes instead of sixteen. Separate plane strides eliminate the
alternating 210-byte word-alignment repair. Constant shifts recover the
codes, and the production FP32 expression and reduction follow unchanged.

This is a storage transform, not a quantization. Metadata remains the same
16 signed scale bytes and half. A six-byte-per-lane payload cannot honestly
promise a separate 16-byte-aligned 16-byte load per lane without duplication
or padding. The useful alignment is aligned word/halfword lane loads and
contiguous subgroup plane accesses. No padding is included in the 210N count.

**Cooperative original-block decode, deferred design option.** Subgroup
lanes cooperatively load unique ql/qh words and broadcast the required words
and half through subgroup shuffles, then decode into the original lane-owned
slots. This avoids repeated global requests without a whole-row SLM buffer
or per-element staging barriers. It adds shuffle latency, needs explicit
handling of the two-byte alignment phase, and preserves no guaranteed
advantage over the two simpler arms. If built later, its CPU emulation must
cover the donor mapping and each alignment phase. It is not a measured or
implemented arm merely because it is described here.

All candidates must retain `scale = half(d) * float(signed_scale)`, then
`weight = scale * float(code)`, `product = weight * input`, and the original
`sum = sum + product` order, without FMA contraction or integer dot products.
Tests must compare raw FP32 lane/logit bytes, BF16 logits and argmax, rather
than allowing BF16 rounding to hide FP32 differences.

## Size of the opportunity and stopping rule

Packet 85 reports 794.624 MB of useful expanded head traffic and 1.404 ms.
Packed code and metadata occupy 521.472 MB, a 34.375% reduction. Holding
bandwidth fixed gives 0.921375 ms, a conditional saving of 0.482625 ms.
Using its +0.293 tok/s per 0.1 ms local sensitivity gives about +1.414 tok/s
(about 2.6% of 53.984 tok/s); rounding to 0.48 ms gives +1.406 tok/s. These
are conditional budgets, not measured speedups, and packet 85 requires the
full max/overlap model once a real component delta exists.

The new microbenchmark admits a candidate to engine screens only when it
is at least 15% faster than the measured production control under the same
full-shape timing definition. The conservative registered definition is at least 15% lower event time:
`candidate_time <= 0.85 * production_time`, not merely 15% fewer bytes. A failed gate
closes that candidate without an engine screen. An isolated win remains
screening evidence; it must survive both lane orders in the engine before
any performance conclusion. Production remains the default.

## Offline assembly addendum

[`inspect_decode.py`](inspect_decode.py) compiled
[`offline_decode.cpp`](offline_decode.cpp) using icpx 2026.0, LLVM-to-SPIR-V
translation, and `ocloc compile -device bmg-g31`. This never enumerates a
card or runs a kernel. The shared compiler-turn lock covered all three
stages; peak child RSS was 309828 KiB. The probe emits all four kernels at
248320 by 2560, SG32 and WG32, with the same reduction/output operations.
This deliberately controls geometry for diagnosis; it does not claim that
packet 74 shipped WG32. Strict FP32 compiler flags, exact source hashes,
commands, load lines, opcode counts and compressed assembly hashes are in
[`evidence/offline/report.json`](evidence/offline/report.json).

| Head path | Whole-kernel static instructions | Static load sites | Configured GRFs | Scratch instructions |
| --- | ---: | ---: | ---: | ---: |
| Production p33 | 234 | 8 | 128 | 0 observed |
| Packet 74 packed | 381 | 11 | 128 | 0 observed |
| Head-plane | 366 | 11 | 128 | 0 observed |
| Head-transpose | 314 | 9 | 128 | 0 observed |

The instruction column is IGC `//.instCount`, not a count of only predicated
assembly lines. Load-site counts include one common kernel-argument payload
load and four common input u32 loads. They count static sites, including
branches, not dynamic instructions or DRAM transactions. No explicit spill
metadata appears in these dumps; no scratch memory messages occur. All four
request the same 128-GRF mode. These probes therefore provide no evidence
that packet 74 loses through spilling or a larger configured GRF allocation.
They do not measure live occupancy in the full engine.

The assembly directly confirms the extra mechanism work. Packet 74 emits
`load.ugm.d32x2.a64` for each plane, then a conditional `goto` around an extra
`load.ugm.d32.a64` and shift/OR repairs, followed by `join`. Although IGC
marks these blocks as divergent control flow, the alignment predicate is
uniform across lanes for this valid shape; the annotation does not prove
real lane divergence. The half conversion still emits exponent/mantissa
branches and its subnormal normalization loop. Compared with production,
packet 74 has 14 versus 6 `goto` sites and 77 versus 22 combined `shl`/`shr`
sites. Thus more address/decode/control work is emitted even with matching
geometry. Its 381 instructions versus 234 is consistent with a latency/ALU
cost that can erase the byte saving, while still not isolating the measured
stall cause.

Head-plane lowers that total to 366 and shifts to 57, but retains all 11
load sites and the alignment control flow. It is a modest decode change,
not evidence that the unpack overhead has disappeared. Head-transpose lowers
the total to 314, shifts to 53 and load sites to 9. Its two code loads are
aligned d32 and d16; the 210-byte alignment repair paths are absent. It still
pays half conversion and subscale multiplication, and remains larger than
production. The transpose arm is therefore the stronger source/assembly
hypothesis, subject to the same 15%-lower-event-time microbenchmark gate.
Neither static reduction predicts a speed result.

The compressed dumps retain the full emitted assembly. `--report-only`
recomputes their metrics from this packet-owned offline build without
compiling again; the original compile logs and memory receipt remain.
