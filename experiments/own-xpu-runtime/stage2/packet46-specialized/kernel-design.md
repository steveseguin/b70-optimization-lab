# Packet 46 specialized ordinary layers

Preparation only until the coordinator supplies device receipts. The two
microbenchmarks are the complete ordinary GDN layer 4 and QSA layer 3 from
packet45-merged3, using its SPEED6 rank-0 dispatch and arithmetic-v2. They do
not cover PLE, exceptional layer-2 IQ3_S experts, another rank's dispatch,
multiple tokens, a complete model, or a model speed claim.

The integration bar is **at least 80 microseconds saved per layer**, separately
for GDN and QSA, in each of two fresh timing processes. Exactness and speed are
independent requirements. Fewer launches do not qualify the candidate.

## Composition

The planner, original kernel submissions, quantization decoding, deterministic
math, BF16 stores and scalar shapes come from the lab's current packet45 source.
No Strata code was read, copied or ported. This is independently written lab
composition of its existing arithmetic helpers, with template types fixing
shape, format, split count and operation. There is no descriptor-interpreting
kernel and no serial whole-layer workgroup.

| Site | Current | Specialized | Preserved observable arithmetic |
| --- | ---: | ---: | --- |
| HC attention and FFN normalization | 2 each | 1 each | Eighty ordered 32-leaf subtrees per stream; identical upper tree, rsqrt, FP32 partial stores, unit-zero addition and BF16 output |
| HC gate and mix, attention and FFN | 2 each | 1 each | Four independent Q8 K320 dot rows per hidden coordinate; each gate is BF16 before sigmoid; stream sum stays 0,1,2,3 |
| GDN QKV and Z | 2 | 1 | Separate Q6 K2560 SG32 accumulators and output rows, ordinary split-one identity |
| QSA Q, K, V, index Q and index K | 6 | 1 | Q6 Q is split-one; Q6 K/V and BF16 index Q/K keep the four original partials and `(p0+p1)+(p2+p3)` finish |
| Ordered expert mixture, shared blend, FFN residual | 3 | 1 | Ten original route slots in order, BF16 mixture, original `0 + mixture*1` expression, separate BF16 shared product, BF16 MoE output, original residual injection |
| Every remaining site | unchanged | unchanged | Exact packet45 submit path |

Expected native counts are **35 to 28** for GDN and **41 to 30** for QSA.
The harness requires the current counts to be exactly 35/41, the candidate
counts to be smaller, and records actual physical event counts. The current
CPU lowering omits some native split-finish events; it is not a launch census.
The native count assertion can reject this expectation. No device has verified
these counts during preparation.

GDN QKV/Z use many independent subgroups. The QSA tuple partitions subgroup
rows among five compile-time bodies, with all member boundaries aligned to
four-row workgroups. Every split retains its own accumulator. It trades the
older small projection's parallel split subgroups for serial independent
partials within a subgroup; that is exact arithmetic but an open speed risk.

The norm uses four workgroups with 128 lanes each. Eighty lanes write the
original FP32 subtree partials. A workgroup barrier makes those stores visible;
one lane computes the unchanged upper tree and inverse, and the workgroup
writes the same output elements. Error control is snapshotted uniformly before
barriers. Sticky error accesses are atomic on the device.

## Every intermediate and state

Each exactness attempt starts both arms from an identical snapshot of every
mutable allocation. Inputs change between attempts. Positions are 0, 127 and
4095, followed by inactive, poisoned-error and out-of-range-position cases.
All tensor output bytes are captured at producer-group boundaries, including
the gate output and mixture that a faster implementation might otherwise omit.
Each full layer then compares every logical tensor and every complete mutable
allocation, including controls, status, scratch, workspaces and padding, without
masking bytes. A failure names the first differing byte and buffer.

| Removed boundary | FP32 evidence retained |
| --- | --- |
| Norm stage 0/1 | Original `4*80` FP32 partials stored to original operator scratch; raw-byte comparison at the producer boundary |
| QSA index-K split/finish | Original 128 rows, eight FP32 scratch slots/row with four populated split slots; stores kept at their original offsets and full byte range compared |
| QSA K/V and index-Q row-group finish | Original partials are local to the workgroup, not public tensors; the CPU leaf gate compares every lane accumulator, split partial and final FP32 result against existing P28 arithmetic before BF16 |
| GDN projection tuple and HC gate | Original split-one FP32 lane/tree order, checked in the CPU leaf gate; every original BF16 row remains materialized |
| Mixture/shared/residual | All three original BF16 intermediates remain materialized and are compared at the producer boundary |

No discarded global scratch write is silently excluded. Tuple index-K keeps
the native original's materialized split workspace; CPU mirrors preserve the
original host lowering, which does not materialize those native-only split
partials. CPU and GPU compare their own current paths; CPU scratch contents
are not mislabeled as native scratch evidence.

The exact gate requires at least two different sorted expert sets per layer;
a reordered identical set is insufficient. The capture manifest fixes the
complete ordered set of producer/final allocation comparisons, including sizes,
input case and position. The same manifest must appear in fresh processes.
A SHA256 of all comparison rows binds the raw-byte output identity. The code
also checks each pair of timing arms across all 210 timing inputs, including
every mutable byte and sticky error, outside the timing interval.

## Fixture and timing

No model payload is opened. Tensor dimensions/formats come from packet34's
tracked `directory.tsv`; finite packed bytes use packet34's deterministic
32-block fixture generator with the actual layer's name as its seed. Immutable
weights are generated/uploaded in at most 4 MiB chunks, including actual expanded
Q6/Q8 metadata strides. No full floating-point weight shadow or disk weight
artifact is created. Each complete expert bank retains all 512 synthetic
experts, so actual changing route IDs address the full bank.

One layer is resident at a time, approximately 1.1 GB synthetic weights plus
bounded scratch, streams and state. The CPU mock uses those same full shapes,
not tiny shapes, and can take minutes. Source/object reuse keeps build storage
small: only packet46 translation units are compiled, while dependencies are
read-only packet45 objects. Before accepting those objects, the unchanged
parent link command must reproduce the pinned parent binary byte-for-byte in
a new packet46 output path. Original sources, generated mirror bytes, compile
commands, link command and every reused object are hash-bound, checked before
and after compilation. If the relink differs, reuse is refused.

Timing is M=1, capacity 4096 and position 4095: all 4096 K/V/index slots have
nonzero synthetic data, and the newly appended slot is included. They are
synthetic states, not a measured natural prefill. No estimate from shorter
context is substituted. The benchmark changes inputs, restores original state,
and alternates AB/BA order. Ten iterations initialize kernels; 200 pairs are
measured per layer. Each event's start/end timestamp and class is recorded;
the metric is summed GPU event execution time, as in packets20/34/45. Host
setup, state uploads/readbacks, exact comparison and queue submission wall time
are outside the metric. This is an operator microbenchmark, never a headline
model decoding rate.

Only the coordinator may execute the native binary, on physical card 0. The
program refuses another card or missing explicit window authorization. SIGINT
and SIGTERM request cooperative stop. Owned events drain and allocations,
queues and contexts retire through packet45's existing owner. Unsafe teardown
retains the owner for the coordinator; no hard kill or driver reset is added.
