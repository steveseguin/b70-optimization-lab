# Packet 52 source diagnosis before device work

2026-10-17. This is a source-based explanation and a set of testable
hypotheses. No packet52 GPU execution, occupancy counter, memory-latency
measurement, instruction trace or measured DRAM-traffic counter supports it
yet. The quoted timings are earlier packet receipts. Free-order timing must
separate arithmetic opportunities from layout and scheduling opportunities.
Changing an order does not itself prove that the previous order was the
bottleneck.

## Evidence and the actual control

Read together:

- [Packet48 byte census](../packet48-gemv/BYTE-CENSUS.md) and its
  [machine-readable shapes](../packet48-gemv/byte-census.json).
- [Packet48b retained timings](../packet48b-production/evidence-copy/p48b-a-summary.json),
  [production adapter](../packet48b-production/candidate.hpp), and
  [packed layouts and decoders](../packet48-gemv/gemv.hpp).
- [Packet51 ranking](../packet51-round2/RANKING.md),
  [candidate bodies](../packet51-round2/candidate.hpp),
  [retained two-owner timings](../packet51-round2/evidence-copy/p51-a-summary.json),
  and [negative index](../packet51-round2/DO-NOT-REPEAT.md).
- Packet45 [dense arithmetic](../packet45-merged3/p33_candidates.hpp),
  [dense launch](../packet45-merged3/p33_submit.cpp),
  [small shapes](../packet45-merged3/p30_small.hpp),
  [small launch](../packet45-merged3/p30_small.cpp),
  [fused launches](../packet45-merged3/p39_sycl.hpp), and
  [negative index](../packet45-merged3/DO-NOT-REPEAT.md).
- [Packet49c integration contract](../packet49c-round2/INTEGRATION.md).

The brief's 96.7-us QKV and 37.2-us Z are the packet48b *candidate* timings;
those replacements were not adopted. Packet51's matched current QKV/Z were
100.208/39.791 us in its first timing owner. A new comparison must time the
current implementation alongside each candidate; it must not present the
faster unselected p48b implementation as production. Packet49c adds the p51
route, both HC low/gate pairs, and attention winners to p49b's IQ2 gate/up
and IQ4 down. Its model qualification is a separate running campaign.

There are **ten selected experts**, each with 640 gate/up outputs, in the
production census and adapters (`count=10`). The brief's “8-expert scatter”
is therefore a mechanism to discuss, not permission to time only eight.
Eight would reduce work and useful bytes by 20%. The full timing shapes here
retain ten; an eight-expert case cannot contribute to the decision.

| Class | Actual ordinary shape / format | Brief timing us | Useful weights MB | Weight-only us at 550 GB/s |
| --- | --- | ---: | ---: | ---: |
| expsgate pair | 10 × two 640×2560 IQ2_S matrices | 77.3 | 10.496 | 19.084 |
| GDN QKV | 10240×2560 expanded Q6_K | 96.7, unselected p48b arm | 32.768 | 59.578 |
| expsdown | 10 × 2560×640 IQ4_NL | 54.4 | 9.216 | 16.756 |
| attention output/combine | 2560×6144 expanded Q6_K, four streams | about 45.8 | 19.661 | 35.747 |
| HC low+gate, both sides | two 320×10240 plus two 10240×320 expanded Q8_0 | about 55 | 14.746 | 26.810 |
| small FFN tuple | 512×2560 F32 router; two 640×2560 Q6_K; 1×2560 F32 shared gate | 27.5 | 9.349 | 16.998 |
| GDN Z | 6144×2560 expanded Q6_K | 37.2, unselected p48b arm | 19.661 | 35.747 |

These are **unique useful weight bytes**, not DRAM bytes. Dense Q6 already
uses signed-byte values with one FP32 scale per 16 values (1.25 bytes/value),
not native 210-byte Q6_K blocks. Expanded rows retain unused metadata in the
production stride. IQ2_S uses 82 bytes per 256 values; IQ4_NL uses 18 bytes per
32. Changing byte layout must preserve those decoded values and must account
for any expanded traffic. All floors omit activation reads, repeat loads,
transactions, decoding, reductions, scratch, epilogues and launch cost.

## Work in flight on the 32-Xe-core planning model

Little's law gives `bytes in flight = desired bytes/second × latency`.
At the owner's 550-GB/s reference, the following are **sensitivity examples**,
not measured B70 latency:

| Assumed effective memory latency | Required total bytes in flight | Per core, evenly divided over 32 |
| --- | ---: | ---: |
| 0.2 us | 110,000 | 3,438 |
| 0.5 us | 275,000 | 8,594 |
| 1.0 us | 550,000 | 17,188 |

One IQ2 pair subgroup consumes 164 distinct weight bytes per 256-column
step (82 per projection). One expanded Q6 subgroup consumes 320 distinct
bytes per step. At the illustrative 0.5-us point, the table corresponds to
about **53 IQ2 pair steps or 27 Q6 steps concurrently outstanding per core**
if a resident subgroup exposes only one such step at a time. At 0.2–1.0 us
the ranges are 21–105 and 11–54. These are useful-byte equivalents, not
predictions of cache-line requests, resident subgroup limits or occupancy.
Decode-table requests and cache hits make the physical numbers different.

Gate/up launches 6,400 SG32 workgroups; QKV launches 10,240, before any new
split. Both have far more total groups than 32 cores. “Too few groups in the
grid” is therefore not a sufficient diagnosis. The relevant unknown is how
many *ready independent memory operations* the resident subgroups expose:
register footprint, workgroup admission, dependent table reads, decode issue
rate and short in-order sum chains can limit that number. More groups can
help only if they improve this ready work, and can hurt through launch,
scratch or scheduling overhead.

The fixed sum does not forbid prefetching or overlapping independent loads.
It forbids replacing one ordered sum by several independent sums followed
by a new reduction. That distinction matters: arithmetic v3 tests the latter;
vector loads and table placement can be tested without claiming a new sum
order is inherently required.

## IQ2_S expert gate/up: about 135.8 useful GB/s

The p48b control is one SG32 workgroup per expert/output row, computing gate
and up together. Each lane handles eight adjacent columns, then advances by
256; K2560 means ten steps and **80 ordered FP32 additions per projection**.
It carries two accumulators, shares the BF16 activation load between them,
then performs the same five-level adjacent SG32 tree for each output.

The p48 layout already puts each index/sign pair in an aligned 16-bit word:
32 lanes cover a contiguous 64-byte plane for each 256-column block. The
high-index bits, nibble scales and half scale live in separate aligned
planes. Their expressions repeat across lanes: four lanes share each
high-index byte, pairs share a nibble scale, and all 32 share the half scale.
Thus the main index stream is coalesced at the source-address level;
“uncoalesced weights” alone is an incomplete explanation. Each lane still
issues several tiny metadata expressions and two data-dependent 32-bit
codebook lookups for each projection. The 1024×8-byte IQ2 codebook is a
compile-time read-only array (`p42expert::iq2_words`), not an explicitly staged
local-memory table. Source alone cannot establish which cache or register
representation the compiler actually chose.

Each eight-value decode constructs a 10-bit index, gathers eight magnitude
bytes, extracts eight sign bits, widens signed values, derives the half/nibble
scale, multiplies eight weights and then multiplies/adds eight activations.
At 32.768 million products for the full pair, the 10.496-MB weight numerator
is only 0.3203 useful weight bytes/product. Decode and address work per
useful byte is consequently much greater than Q6. Registers for both decoded
vectors and the ordered pair can reduce latency hiding, but no register-count
measurement is available.

Scatter is at **expert slab boundaries**, not arbitrary per-lane addresses.
A subgroup shares one expert ID and reads a contiguous row in that expert;
640 adjacent rows amortize the route choice. Ten selected expert slabs are
far apart in the 512-expert bank, so inter-expert locality/TLB/cache behavior
can differ from a contiguous ten-expert fixture. At M1 each weight serves one
activation row; there is no GEMM-like token reuse. Down uses a different
activation vector per expert slot. Reducing expert count, using duplicate
expert IDs, or substituting contiguous selected slabs without documenting
it would hide part of the production cost.

**Verdict:** source evidence points to decode/dependent-read/issue cost plus
limited ready work per resident subgroup, with the fixed 80-add chains a
credible contributor. It does not prove DRAM saturation or identify a single
hardware bottleneck. P51's compact 2-KiB magnitude codes plus separate gate/up
subgroups did not improve timing (about 1.00x); it closes that exact-order
combination, not all table-placement or arithmetic variants. Free-order
multi-accumulator / split-K variants directly test the serial chain; fewer
lanes per row and several rows per subgroup test residency versus longer
chains; vector/table placement arms test decode issue independently. Preserve
the full pair, routes, invalid-route behavior and output rounding.

## GDN QKV: about 339 useful GB/s in the p48b arm

The production `p33.dense.segment` Q6 path has 10,240 rows, SG32, K2560,
ten eight-value steps per lane, **80 ordered FP32 additions**, and a five-level
adjacent tree. Expanded codes are contiguous signed bytes. A neighboring lane
pair requests the same FP32 scale because each scale covers 16 columns and
each lane handles eight. The code reads the retained expanded row stride,
not the packed GGUF stride. There is no IQ2-style codebook gather or sign-grid
lookup, only widening, scale multiply, activation multiply and add.

At one scalar code expression across lanes, addresses are eight bytes apart;
across the eight expressions the whole 256-byte span is covered. Explicit
wide loads can reduce source load/issue count while preserving the same
addresses. P48's aligned code/scale layout and p51's vector loads/grouping did
not produce a large gain, so byte alignment is not a compelling sole cause.
There is abundant grid parallelism but still only one accumulation chain per
lane. QKV's expanded numerator is 32.768 MB; dividing its 21.504-MB GGUF
storage by time would misdiagnose bandwidth.

**Verdict:** a mixture of memory supply and scalar decode/ordered-sum issue is
plausible; the current evidence cannot apportion it. The fixed order rules out
independent column accumulators and a new split tree, which are the biggest
new mechanisms to probe. Extra split-K stages must include their scratch,
second launch and deterministic final reduction in the timed total. Production
Z is an instructive same-format comparison but has different output shape and
row count and traffic footprint; both QKV and Z retain the unsplit SG32
order. Its higher useful rate does not establish that QKV must reach it.

## Remaining five classes

**IQ4_NL down.** Ten 2560×640 matrices; 25,600 output SG32 groups. K640 gives
three eight-value steps in lanes 0–15 and two in lanes 16–31: at most 24 ordered
adds, so its long-chain opportunity is smaller than gate/up. The p48 repack
already isolates half scales and nibble bytes. Opposite nibble halves share
packed bytes, while the 16-level nonlinear table uses integer bank selection
(`p33::level_bank`), not the IQ2 global codebook. Many short groups, repeated
scale/nibble expressions, uneven final-step activity and routing/output cost
can depress its useful rate (~169 GB/s). More rows per subgroup and vector
nibble decode are credible; split-K can easily cost more than it saves. The
fixed order restricts new row/lane mappings and accumulators, not nibble
extraction itself. P48b's earlier 1.68x gain is already in the control.

**Attention output/combine.** The 2560×6144 Q6 projection has four existing
column splits, FP32 global partials and a second finish/combine launch. Each
split covers six 256-column steps, or 48 additions per lane; the full row has
24 steps but no single production lane walks all 24. The rounded BF16
projection then updates four streams. P51 already shares the four exact
sigmoid factors across rows, removing the earlier repeated nonlinear work.
At ~45.8 us versus the 35.7-us weight-only reference, remaining M1 headroom
is only about 10 us before unavoidable work. Free-order candidates can change
per-split chain length or split count, but cannot erase the BF16 boundary or
omit combine. This is output projection, **not QSA attention**; packet47's
split32 QSA remains outside this probe.

**HC low+gate.** Both sides use Q8 low 320×10240 split4, then gate
10240×320 split1. P49c's low is one 128-item workgroup per row (four SG32
partials and a fixed `(p0+p1)+(p2+p3)` local reduction), with 80 additions per
lane per split. The 320 low rows give ten groups/core on an even division,
much less grid slack than QKV. Low rounds to BF16 and applies the existing
activation before gate, which is a real data dependency. Gate has one full
256-column step plus 64 columns: only eight lanes work in the tail, and most
lanes execute eight additions versus sixteen for the first eight. Q8 scales
repeat across four eight-value lanes. Low can benefit from more parallel
partials; gate can benefit from fewer lanes/row and more rows/subgroup. Low
and gate must both be timed on both sides with their dependency and activation,
not replaced by a bandwidth-only bulk kernel. The ~55-us subtotal includes
unequal row geometry and nonlinear work; 26.8 us is only a weight floor.

**Small FFN tuple.** This is mixed F32/Q6, not just the two shared Q6 matrices.
The one production tuple launch covers 1,793 output rows: router512,
shared gate640, shared up640, scalar gate1. It assigns an SG32 to each row,
with four original parts evaluated **sequentially inside that subgroup**, each
having its own adjacent tree; the four partials then use the fixed tree.
The selected rows4 local size groups four output rows, not four independent
K splits. Different member types branch by subgroup and have different byte
costs. Separating K work into parallel partials changes order or scheduling
and adds scratch/reduction overhead; grouping more rows can amortize launch
and improve useful work. Preserve all four members and BF16 boundaries when
comparing the 27.5-us class. The singleton gate is not a reason to charge the
whole tuple as a tiny-grid kernel.

**GDN Z.** This is 6144×2560 expanded Q6, with the existing unsplit
SG32 order (`dispatch_variant` 2, expanded variant 6). It is already near the
550-GB/s *useful-weight* reference in the unselected 37.2-us p48b arm; the
matched production timing is nearer 39.8 us. The plausible M1 gain is small,
so a bounded comparator is justified and a long sweep is not. New splits or
row packing may reduce overhead, but a changed sum cannot beat the weight
supply cost merely by shortening its chain. M2 could make reuse
valuable only with a separately integrated joint-token path.

## M2, determinism and what this probe can decide

The current engine executes M2 as **two serial production calls on independent
changing rows**, not a shared-weight two-token GEMM. Every listed shape is
therefore run twice and both event totals are counted. Dense/HC unique
weights remain one set but logical reads double. Routed selections can
intersect in 0–10 expert IDs; their union has 10–20 experts, but a serial
implementation still processes ten per row. No invented reuse saving enters
the arithmetic-v3 decision.

A deterministic free order requires explicit lane assignment, per-lane
product/add sequence, partial indexing and reduction tree, separate FP32
multiply/add (no accidental contraction), BF16 boundaries, tail treatment,
and exceptional-value policy. No unordered atomic floating-point reduction
is admissible. Each variant's own CPU mirror and fresh-process device byte
agreement are required; distance from the old order is information only.
A new CPU oracle is not generated in packet52. Device measurements and the
preregistered 120-us ordinary-layer rule decide whether the combined new
identity is worth that later cost.
