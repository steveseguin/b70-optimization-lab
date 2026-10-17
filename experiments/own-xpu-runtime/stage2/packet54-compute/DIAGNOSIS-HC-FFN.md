# Packet54 HC and FFN source diagnosis

This is a source-level bound, not a device measurement. It uses the packet49c
production dispatch and arithmetic, with packet45/51 ancestry. M=2 means two
serial M=1 rows with state carried between rows. All timings below are prior
measurements supplied in the brief or the linked packet46 receipt. No device
program ran during this diagnosis.

## HC inject: keep the production control

Both `blk.L.hc.a.inject` and `blk.L.hc.f.inject` multiply four F32 rows of
length 10,240 by a BF16 input. The first uses `p33.dense.segment`, the second
`p28.dense.wg32`. `packet9-kopt4/dispatch.hpp` selects arithmetic variant 4
for `(F32,4,10240,1)` in both cases: four partitions of K=2,560, each with 32
logical lanes. Every lane retains 80 ordered product/add pairs, in eight-value
tiles separated by 256 elements. A five-level adjacent tree combines the
32 lanes. The finish retains `(p0+p1)+(p2+p3)` and the BF16 cast.

The sources are `packet49c-round2/p33_submit.cpp:47` and
`packet49c-round2/p33_candidates.hpp:76` for attention-side injection, and
`packet49c-round2/p28/submit.cpp:68` plus `p28/dense.hpp:9` for FFN-side
injection. Each side has 16 WG32 jobs and a four-element finish kernel.
There is no transcendental. The sum's 80 dependent additions and the small
workgroup census matter more than streaming bandwidth. The p28 source also
declares its small local partial allocation although WG32 writes split
partials to global memory; neither path uses a local reduction tree.

Each side needs at least 163,840 weight bytes, 20,480 unique input bytes and
eight output bytes (about 184 KB). At the brief's roughly 550 GB/s dense
streaming reference, that is only 0.34 microseconds, versus about 12–13
microseconds measured. This is an optimistic byte floor; it is not an
attainable timing prediction for sixteen small workgroups. There are 40,960
products and 40,960 lane additions per side, plus 496 tree additions and 12
split-combine additions. No honest cycle lower bound follows without device
instruction/occupancy evidence. More split partitions would change the tree;
combining the sides would violate their intervening dependencies. Injection
stays in both controls and both HC candidates without claiming a saving.

## HC norm: duplicated upper trees are the substantial lever

The two plain HC norms are `specialised::submit_class<ng::norm,2560,4>` in
`packet49c-round2/specialised_submit.cpp:38`. `adapter.cpp:287` binds BF16
input/output and F32 gains; `specialised.hpp:101` defines both stages.

Stage 0 launches 320 independent items: 80 consecutive 32-element subtrees
for each of four streams. Each item computes the exact private tree and
writes one FP32 partial. Stage 1 launches 2,560 items, each producing four
output elements. Every item independently reloads all 80 partials, performs
the exact upper tree, calls packet17 `detmath::rsqrt`, then applies the two
ordered multiplications and BF16 output cast. Both stages use `range`, so
their physical WG shape is compiler-selected. There is no workgroup barrier
or explicit local allocation in this control; private arrays can become
register pressure or spills, which source inspection alone cannot quantify.

Per norm this is 10,240 squares and 9,920 first-level additions; then 207,360
upper additions (81 per item, including original odd-tail `+0` sites), 2,560
deterministic square-root/reciprocal calls, and 20,480 output multiplies. The
upper tree and rsqrt are identical across every output tile of one stream.
The unavoidable unique input/gain/output traffic is about 82 KB including
the partials: 0.15 microseconds at 550 GB/s. Literal scalar-source loads are
about 0.92 MB because of repeated partial reads, or 1.68 microseconds at that
rate if nothing were cached. Cache residency invalidates treating the latter
as a DRAM floor. The measured two norms total about 19.3 microseconds in
packet46's ordinary-layer control. The source supports a compute/occupancy
diagnosis, not a precise predicted time.

Packet46's `Norm` collapsed each stream into one WG128: just four workgroups.
Only 80 items initially computed subtrees, then lane zero serially reduced
80 partials and evaluated rsqrt while its other 127 lanes waited. Its four
explicit barriers include a global/local fence. It reduced redundant math
but sharply reduced parallelism; the measured norm total rose from 19.272
to 35.6765 microseconds. This is the retained reason not to repeat its fusion.
See `packet46-specialized/specialized.hpp:74` and
`packet46-specialized/evidence/p46-a-summary.json`.

The rejected proposal `norm-subgroup128` keeps stage 0 and all 320 FP32 partials (1280 bytes).
Stage 1 has 80 subgroups in 20 WG128, each producing 128 outputs. Each lane
first combines four consecutive partial leaves. The subgroup then executes
the remaining exact adjacent levels over 20 values, including the same
conditional right-tail additions. Lane zero calls the unchanged rsqrt and
broadcasts its bits; each lane writes four elements. This is 6,480 upper
additions and 80 rsqrts per norm, with no local allocation or workgroup
barrier. The dependency tree is unchanged; ownership and repeated evaluations
change. More WGs than packet46 and fewer repeated computations than the
control are the hypothesis. Device E1/E2 and T1/T2 must decide it.

## HC mix: independent vector dimensions, unchanged ordered streams

`adapter.cpp:289` maps each mix to `ng::mix`; `kernels.hpp:156` performs four
ordered `sum = sum + sigmoid(gate[h,k])*norm[h,k]` terms, then `/4` and BF16.
One norm/gate pair consumes 40,960 bytes and produces 5,120: a 46 KB byte
floor (0.084 microseconds at 550 GB/s) per side. The control has twenty
WG128, two guard barriers per workgroup, no data-dependent reduction barrier,
and 10,240 deterministic exp calls, because each sigmoid uses packet17 exp.
Each ordinary finite exp has twelve double-single Horner multiply/add stages
after range reduction; it is not a native one-instruction exponential. Thus
the two mixes' roughly 19 microseconds cannot be understood as a byte-copy
problem.

`mix-vector4` assigns four contiguous dimensions to each of 640 independent
items. Four live sums retain the stream-0,1,2,3 order and all BF16 boundaries;
the compiler can interleave independent exp chains and contiguous accesses.
It does not reduce the 10,240 sigmoid calls or change their implementation.
No local allocation or barrier is introduced. Possible increased register
pressure and reduced workitem count are risks. This is a small scheduling
screen, not a fusion of gate, mix and norm. The HC class has two registered
original choices: `norm-subgroup128` and `norm-mix-vector4`. Both are now
closed after actual-production exceptional parity failed. The final eligible
arm is `mix-vector4`, with production normalization and injection.

## FFN combine: share an identical factor across adjacent outputs

`adapter.cpp:274` sends standalone `Op::hc_combine` to
`simple_new_submit`; the arithmetic leaf is `adapter.cpp:206`. This is the
four-stream residual injection after the separately retained MoE blend, not
the MoE expert reduction. For every stream element it evaluates
`residual + branch * (2 * sigmoid(inject/4))`, then writes BF16. Its factor
is identical for all 2,560 elements within a stream. The packet49c control
has 10,240 scalar items, implementation 11 using WG32 (320 workgroups), or
the same range leaf for specialised implementation 1. There is no barrier,
local memory, or cross-element sum. The source invokes 10,240 exp/sigmoid
calls unless the compiler proves and hoists a uniform factor; disassembly
is required to establish how much such hoisting already happens.

The irreducible traffic is 20,480 residual bytes + 5,120 unique branch bytes
+ eight injection bytes + 20,480 output bytes, about 46 KB, or 0.084
microseconds at the bandwidth reference. Literal source branch loads raise
this to about 61 KB before caches. The existing 11.2-microsecond timing is
dominated by non-memory work. No precise compute floor is claimed without
actual generated code.

`combine-vector4` uses 2,560 items. Each reads the deterministic factor once
and writes four adjacent BF16 values. It preserves the residual-plus-product
expression, all output casts, and the exact active/sticky guard. In
particular the standalone production combine does **not** check position;
the candidate must not silently add that check. It reduces source-level
sigmoid calls to 2,560, subject to the control compiler's existing hoisting.
It does not fuse norm, alter the separate MoE blend or introduce fast math.

## Exact integration sites and admission

Replace only `blk.L.hc.a.norm` and `blk.L.hc.f.norm` using
`p54hc::submit_norm(device, prepared.spec, prepared.bindings)`; optional
`blk.L.hc.a.mix` / `hc.f.mix` use `submit_mix` with the same ABI. The proposed replacement of standalone `blk.L.ffn.combine` using
`submit_combine` is closed; retain production. `main.cpp:1246`
marks the latter as the layer-end boundary; preserve it and its dependencies.
Inputs, outputs, weights, scratch, error, position, active and rope retain
their prepared binding order. The norm capture includes its exact 1,280-byte
scratch prefix. Full M=2 tests invoke these M=1 kernels twice serially; they
do not create a cross-row reduction. Fused `combine_norm` descriptors are
explicitly refused rather than silently interpreted as plain norm.

`hc_ffn_test.hpp` exercises the actual production specialised norm body and
ng mix CPU helper, plus the exact adapter combine leaf. It includes the
80-leaf tree's zero/nonfinite cases, nonlinear signed-zero/Inf/NaN cases,
inactive and sticky controls, invalid position, complete shape output and
partial bytes, and serial M=2 state transitions. Device identity and timing
remain coordinator work. No per-class saving is inferred from CPU gates.

## Exceptional qualification and closed FFN arm

The first GNU small proof found a NaN-payload difference when residual, branch
and injection were all NaNs. A noinline scalar exceptional fallback repaired
that handwritten comparison but failed the actual compiled-production check:
production wrote BF16 `0x7fc0`, candidate `0x7fc1`. The source is retained as a
failed arm, excluded from the manifest and all device selections. No payload
canonicalization or tolerance is accepted. See
[evidence](evidence-cpu/full-diagnostic-2/receipt.json).

The norm cooperative upper tree also exposed compiler-dependent exceptional
payload selection. On nonfinite partials its subgroup-uniform branch calls
the unchanged specialised norm stage1 body; finite values retain cooperative
sharing. Small checks keep exact control/candidate bytes within each compiler.
Finite proof bytes must also match between GNU and Intel. The raw diagnostic
byte map records which NaN payloads the two control compilers choose; it does
not permit candidate differences within either compiler.

The full CPU fixture and each E window compare the norm exceptional case
through actual compiled production, including partials and controls. This is
same-backend parity; no new cross-backend NaN identity is claimed. Timing uses
the registered finite fixtures with the exceptional guard still in the kernel.

## Final preparation decision

Actual compiled production rejected the norm exceptional fixture too:
output byte4098 was `0xc1` in production, `0xc5` in the candidate. The copied
specialised fallback is not equivalent to preserving the actual compiled
kernel's operand choice. Both norm arms are closed; see
[failed receipt](evidence-cpu/full-diagnostic-3/receipt.json).
`mix-vector4` is the only eligible HC arm. Its full-shape finite and
exceptional actual-production checks pass; norm and injection stay unchanged.
Earlier proposed norm descriptions above document the rejected mechanism.
