# Q6 GDN-QKV source and CPU preparation

The single proposed change is the22 Q6_K `gdn.qkv` sites, N10240/K2560,
using unchanged p33 variant6/split1 and expanded storage. Selection is fixed by
actual model descriptors and graph labels; no Q5_K, Q4_K, IQ4_XS, GDN-z, expert,
attention or head dispatch is changed here. No full Engine candidate is built.

The old profile measured1,811.757ms for the whole QKV class:22Q6,10Q5,2Q4,2IQ4_XS.
Its rank1 aggregate was higher despite fewer Q6 layers, so neither byte share nor
layer count establishes Q6's share of elapsed time. GDN-z's1,210.228ms similarly
mixes14Q6,4Q5,10Q4,8IQ4_XS. These are whole-request event sums including prefill,
not decode-only or concurrent critical-path time. This proposal chooses the
largest already-supported Q6 subset, not a measured Q6 bottleneck claim.

The selected existing p6 `decode8<Q6_K>` computes binary16 block scale times
signed8 group scale, then signed6 code. p33's unchanged load-time expansion stores
that same FP32 product and signed code; `dense_lane<Q6_K,2560>` multiplies it by
the same BF16 input and retains eight-element lane order, stride256, adjacent
SG32 tree, and final BF16 conversion. No split4, changed precision or reassociation.
The kernel already exists for the current full Q6 head, but different weights and
shapes still need exact qualification. Moving scale multiplication to CPU can
expose exceptional-value/compiler operand-priority differences. No NaN tolerance,
canonicalization or output waiver is permitted.

Benefit is removal of packed decode work, four-row SLM staging and its barrier.
It does NOT reduce kernel count or global weight bytes: packed row2100 bytes
becomes3380 stored bytes (kernel consumes codes plus FP32 scales). The22-site
allocation increase is288,358,400 bytes:rank0 fourteen sites183,500,800 and rank1
eight sites104,857,600. Including already-expanded attention, source forecasts are
30,947,490,698 and29,824,495,508 device bytes. They remain forecasts, not observed
allocation/capacity qualification.

`fixture.cpp` uses the exact extracted p33 scalar body versus unchanged p6
reference arithmetic and expansion. It covers all65,536 half patterns, all signed
scale/code patterns, an explicit16exceptional-half ×256signed-scale matrix with
all64 Q6 codes, a full10,240-row shape,16 exceptional full rows, and a numerical
zero/+1 negative control. Full FP32 and BF16 bits must match. A failed exceptional
case remains a failure. `build_cpu.py` runs only this synthetic GNU proof under
nice19/helper cores, threads2, AS4GiB, strict FP flags and32MiB write forecast;
no native owner, real weights or device code is invoked.

The planned one-owner micro retains the reviewed attention micro lifecycle and
fixed balanced84pair/168kernel schedule. Cases are layers0,24,40 by fixed position.
Both full native outputs must match the recorded full QKV output. The76,800bytes
of inputs/outputs come from closed independently audited `profile-a` prompt00;
each file's hash also equals the original baseline index. Unique graph writers
and actual named scratch allocation semantics are bound in `selection.json`.
The original baseline raw bins now live in verified archives; no archive restore
is needed for these profile fixtures. Only these tiny state files were copied.

Three full packed+expanded matrices, inputs, separate outputs and workspace need
169,466,880 device bytes (161.616MiB), plus1MiB pinned slab; transfers cap192MiB.
Micro source is generated with geometry-only changes from the reviewed runner.
After the completion audit closed, one approved read authenticated the header
prefix and only three fixed Q6 tensors (64,512,000 payload bytes). Their hashes
and finite half-scale census now bind `micro/fixed.hpp`; most sampled half scales
are subnormal binary16 values, preserved as ordinary FP32 values by the decoder.
This is not an all22-weight census. A full22-site Engine integration would require
its own remaining weight authority and memory/exactness review. Native micro
compilation may proceed under the reviewed64MiB reservation; no device invocation
is authorized by the build helper.
The small CPU proof does not establish GPU equivalence, full-model acceptance,
or speed. Root alone owns subsequent operational admission.

Synthetic GNU proof passed17,915,939 exact comparisons with zero mismatches;
no native owner was involved. Four preparation tests also check fixed selection,
full per-rank/micro memory sums, fixture bytes and the unchanged selected body.
