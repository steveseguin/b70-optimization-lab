# Prefetch-distance co-tune: premise dead at stage 0, no GPU spent

Date: 2026-07-28 America/Toronto

Status: **closed at stage 0.** The proposed sweep was never run. Screening cost
about nine minutes of CPU and saved roughly 105 minutes of exclusive 4-card
GPU.

## The proposal

Re-sweep `VLLM_XPU_LAGUNA_PREFETCH_DIST` now that `VLLM_XPU_LAGUNA_SCALE_VEC=1`
is on, on the premise that SCALE_VEC freed register pressure and the optimum
may therefore have moved off the incumbent distance of 6. Attractive because it
needs no new code and the binary is already installed. Three arms at n=5 and
seven minutes a leg is about 105 minutes.

## Why it does not hold

**The distance never reaches the compiler.** `laguna_int4_prefetch_dist()`
(`csrc/xpu/grouped_gemm/xe_2/grouped_gemm_xe2_interface.hpp:103`) returns a
runtime `int` against a literal 3/6/12 allowlist. It is threaded down as a
function argument — `gemm_xe2.hpp:631` `int prefetch_dist_override = 6`, then
`gemm_xe2.hpp:687` `const int prefetch_dist = prefetch_dist_override`. There is
no `PrefetchDist` template parameter anywhere in the grouped-GEMM path; the
only one in the tree is `csrc/xpu/mhc/xe_2/mhc_pre.cpp:106`, a different
kernel. Contrast `ScaleVec`, which **is** a template `bool` at
`gemm_xe2.hpp:801` with five instantiations.

**Per-distance template instantiations: zero.** Distances 3, 6 and 12 all
execute the same compiled kernel. The mainloop is identical at every distance —
166 instructions at VEC=0 and 133 at VEC=1, with the opcode and exec-size
sequence matching byte for byte. The single semantic difference across all
three is one immediate, `32 * prefetch_dist`:

```text
pd=3    (W) add (1|M0) r4.10<1>:d  r4.9<0;1,0>:d   96:w
pd=6    (W) add (1|M0) r4.10<1>:d  r4.9<0;1,0>:d  192:w
pd=12   (W) add (1|M0) r4.10<1>:d  r4.9<0;1,0>:d  384:w
```

**Register pressure was never the binding constraint.** SCALE_VEC=1 does free
about 32 GRFs at distance 6 — 126 distinct falling to 94, max r138 to r105,
exactly the 32 removed `mov (16|M0)` destinations. But across all eight builds
measured: **spill+fill is 0**, `numGRF` is 256, and `HWThreadNumberPerEU` is 4.
Occupancy is bit-identical. The GRF mode is pinned by the explicit
`intelex::grf_size<256>` property in the launcher, not chosen from pressure, so
freeing 32 registers buys exactly zero occupancy. Worst case anywhere is max
r144 of 256 — 111 registers of headroom.

Mechanically there was never a coupling to find: Xe2 block prefetch is a
null-destination send, `load_block2d.ugm.d16.a64.ca.ca (1|M0) null:0 [r60:1]`.
It writes no GRF at all. Prefetch depth consumes cache and MSHR occupancy, not
registers.

Both halves of the premise fail independently. The registers were not scarce,
and the allocator never sees the distance anyway.

## Probe validity

The screen's own build reproduced the recorded `422 -> 389` instruction counts
for VEC=0 to VEC=1 at distance 6, matching the comment at
`grouped_gemm_xe2_interface.hpp:162-163`. The probe was measuring the real
kernel, not a lookalike.

## A lead this turned up, deliberately not promoted

Because the distance is a runtime value, the shipped kernel carries a prologue
loop that a distance-specialized build does not: 522 instructions versus 422 at
VEC=0, about 100 instructions and a 147-instruction loop with 24 load/prefetch
ops. Making the distance a template parameter would remove it.

**This does not clear the stage-1 bar.** That prologue runs once per workgroup
against a mainloop that runs K/32 times. At the down-projection's K=1024 that
is 32 iterations x 133 = 4,256 instructions, so the prologue is about 2.3%; at
the gate/up projection's K=3072 it is about 0.8%. Both sit under the ~5%
stage-1 threshold and the smaller one sits under this host's 1.63% noise floor.
Recorded as a lead, not a candidate. If the ranked targets are exhausted it
deserves a real quantification against the true decode shapes rather than this
estimate.

## What this closes and what it does not

Closed: re-sweeping the runtime prefetch distance under any scale
configuration. There is no codegen for the sweep to find. The earlier result
that "control equalled or beat 3 and 12" is now explained rather than merely
observed — those arms differed only in one immediate operand.

Not closed: prefetch behaviour as such. A change that alters what is prefetched
or when, rather than how far ahead a runtime counter points, is untouched by
this.

## Lesson

A selector being cheap to flip is not evidence that flipping it can do
anything. Before buying arms on a knob, check that the knob is wired to
something the compiler can act on. Nine minutes of reading the plumbing beat
105 minutes of measuring noise.
