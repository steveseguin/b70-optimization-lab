# Packet 48 GEMV design and arithmetic contract

This packet changes weight layout and loading while retaining the current
per-output arithmetic. It contains no measured GPU improvement. The coordinator's
fresh exactness and timing windows decide whether it is useful. A 550 GB/s copy
reference is a comparison point, not a prediction that decoding reaches it.

## Current paths and source-level diagnosis

The frozen packet46 `dispatch-baseline.json` names `p28.paired.wg32` for routed
gate/up, `p33.down.bank` for down and `p33.dense.segment` for GDN QKV/Z. The
production plan's packet39 fusion can replace the named GEMV: the ordinary IQ2
gate/up plus checks uses `p39::gemv<...,expert_checks,true>` and down plus status
uses `p39::gemv<...,down_status,true>`. Their `p39::lanes` bodies call the paired
packet28 expert lane and **packet33 down mode 1 (select)**, respectively. Therefore
the dispatch string alone is insufficient to select a timing control.

Relevant read-only packet45 files are `p28/expert.hpp`, `p28/submit.cpp`,
`p33_candidates.hpp`, `p33_submit.cpp`, `p42_expert.hpp`, `p39_fused.hpp` and
`p39_sycl.hpp`. Packet48 calls the actual inherited packet39 GPU submission for
the ordinary IQ2 and down controls. Its supplementary IQ3 and dense controls wrap
the inherited arithmetic in the same one-row SG32 geometry; these are adapted
controls, not a byte-identical reuse of their production submission closures.
Full-runtime qualification remains necessary before integration or a speed claim.

| Mechanism | Observed source property | Packet48 response |
| --- | --- | --- |
| Output ownership | One SG32 subgroup computes a row; routed down creates 25,600 row groups for ten experts | Keep that ownership and adjacent reduction; M2 may calculate a second independent position in the same group |
| Packed weight alignment | IQ4 has 18-byte blocks, IQ2 has 82-byte blocks and IQ3 has 110-byte blocks; aligned allocation bases do not make their code fields uniformly word-aligned | Separate compact code and metadata planes with 16-byte plane and row alignment |
| Table reads | Packet28 reads IQ2/IQ3 grid magnitudes byte by byte for each group of eight weights | Read two 32-bit table words and extract bytes; this part was already explored by packet42 and is not claimed as a new technique |
| Load width | The selected down select and dense segment bodies spell most packed-code and input loads as individual scalar operations | Prove natural alignment, use two 32-bit code reads and an eight-element BF16 vector read |
| Dequantization | Gate metadata and lookup decoding recur for every row/input; dense Q6/Q8 already carry predecoded signed bytes and FP32 scales | Preserve compact expert codes; share eight decoded values across two independent inputs when the same row is needed |
| Dense retained metadata | Expanded dense rows retain original-format metadata after their codes and FP32 scales, although the selected dense lane does not read it | Omit the unused suffix when constructing the candidate row; preserve every consumed scale bit |
| Dependency chain | Each lane adds eight products in order, then advances 256 positions; gate/up maintain separate chains | Keep those chains; no new partial accumulators or reassociation |
| Atomics | No atomic accumulation is used; packet39's exceptional invalid-route path atomically sets a sticky error | Preserve the error/status contract; atomics are not presented as the normal bandwidth bottleneck |

The sources establish load and arithmetic structure. They do **not** establish
actual register pressure, occupancy, cache hit rate or spilling in the current
binary. Gate/up has two eight-value temporaries and two accumulators; M2 adds
live values and can reduce occupancy. The timing windows must test that risk.
B70's single compute engine gives no basis for claiming concurrent computation
of the two positions; the intended gains are shared weight decoding and fewer
submissions.

## Compact row layouts

Every candidate plane begins at a multiple of 16 bytes. A routed row offset is
an integer multiple of the 16-byte-aligned row stride, so a loaded expert ID
cannot destroy the proved alignment. The decoder uses naturally aligned
16/32-bit reads; BF16 activation groups contain eight contiguous values. This
explicit contract is required even when the compiler does not infer divisibility
from a value loaded from memory. Packet6/packet7's earlier audits record that they
could not locate the exact historical phrase about Triton loaded offsets; this
packet does not invent a source citation for that phrase.

| Format and production K | Original runtime bytes/row | Candidate bytes/row | Layout |
| --- | ---: | ---: | --- |
| IQ2_S, 2560 | 820 | 832 | Interleaved low-index/sign pairs, high-index bytes, packed scale bytes, FP16 block scales |
| IQ3_S, 2560 | 1100 | 1120 | Index bytes, signs, high-index bytes, packed scale bytes, FP16 block scales |
| IQ4_NL, 640 | 360 | 368 | Contiguous original packed nibbles, original FP16 block scales |
| Q6_K expanded, 2560 | 3380 | 3200 | Original expanded signed codes and exact FP32 scale bytes |
| Q8_0 expanded, 2560 | 3040 | 2880 | Original expanded signed codes and exact FP32 scale bytes |

The IQ3_XXS release name does not imply that every tensor uses IQ3_XXS storage.
The routed production tensors covered here use the IQ2_S/IQ3_S/IQ4_NL types in
the tensor census. No IQ3_XXS-specific kernel is silently substituted.

Repacking is an offline load-time transform into a distinct allocation. It does
not expand all experts into FP16/FP32 weights. For a fully resident 48-layer
model, the expert row padding alone adds 369,623,040 bytes for 47 IQ2 gate/up
layers, 13,107,200 bytes for one IQ3 gate/up layer and 503,316,480 bytes for down:
886,046,720 bytes total, before dense savings. Integration must replace old
allocations and prove the complete per-card reserve; keeping both full banks is
not proposed. The fixture deliberately retains old and new banks for comparison.
Q6 QKV/Z saves 180 bytes per row; other dense savings must be computed using the
actual tensor types and counts, not assumed from this one shape.

## Exact order and M2 scope

`gemv.hpp` leaves the reduction to the caller. For each output and original
split, lane `l` visits `begin + 8*l + 256*t`, then elements `j=0..7` in ascending
order. Each value multiplication, activation multiplication and accumulator add
retains its original order. The caller retains the adjacent SG32 tree with
widths 1, 2, 4, 8 and 16 and the final BF16 store. Ordinary GDN QKV/Z uses one
split. The extra CPU compatibility test also checks the original split-four
finish `(p0+p1)+(p2+p3)`; it does not redefine the ordinary GDN oracle.

IQ sign handling retains the exceptional-scale magnitude-then-sign expression.
Finite values retain the existing signed-magnitude integer conversion before
scaling. No NaN canonicalization, tolerance gate, FMA contraction or reduction
reassociation is introduced. Dense candidate scales are copied as bits from the
runtime's current expanded format.

`gate_lane` computes gate/up together with one activation load.
`lanes2` shares only decoded weights, then maintains independent ordered
accumulators for two different inputs. The native M2 optimization currently
recognizes equal expert-row addresses **at the same route slot**. It does not
search another slot for a match. Identical route order can reuse all ten experts;
a five-expert overlap shifted by five slots reuses none through this branch.
Therefore distinct-weight lower bounds and actual candidate weight reads must
be reported separately. There is no permission to report a 15-expert read for
that shifted-overlap case when this implementation still reads 20.

There is no oracle-changing arm in this packet. Splitting a lane's serial chain
into independent partial accumulators could reduce dependency latency, but it
changes rounding and needs a separately named arithmetic identity, a matching
CPU reference, fresh determinism/quality qualification and an explicit decision
before use. It is lower priority than the order-preserving work here.

## Prior failures and qualification limits

The packet25 negative index rules out repeating whole-row wide staging,
register-grid/SLM full decode and full expert expansion without a new mechanism.
Its historical register-grid decoder spilled 6 KiB; that is not evidence that
the present incumbent spills. Packet28 found earlier 64-bit code-word/shifting
variants slower. Packet48 uses 32-bit packed loads and compact planes rather
than those mechanisms. Packet45's failed dense fourparts case used an incorrect
expanded row stride, so the new CPU test exercises five adjacent real-stride
rows and independent peer rows rather than only row zero.

The generated CPU fixtures check every decoded FP32 bit, all lane results,
independent M2 inputs, paired gate/up, adjacent reductions and final BF16 bytes.
They include changing finite data, infinities and NaN scale/input payloads.
These are arithmetic gates, not device performance evidence. Device E1/E2,
fresh-process repetition and T1/T2 remain separate requirements. Synthetic
fixture timing is screening evidence and cannot promote a model throughput
headline.

Packet48's layout and kernel code were written independently for this lab.
Read-only earlier lab headers supply the existing oracle and normative format
tables, retaining their existing attribution. No external runtime kernel was
copied or ported; Intel SYCL is a platform dependency.
