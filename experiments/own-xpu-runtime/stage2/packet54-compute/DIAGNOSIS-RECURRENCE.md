# Packet54 recurrence diagnosis

## Production identity and where time goes

The active packet49c SPEED6 dispatch selects `round2` for `gdn.recurrence`:
[`dispatch-speed6.json`](../packet49c-round2/dispatch-speed6.json),
[`adapter.cpp`](../packet49c-round2/adapter.cpp),
[`round2_submit.cpp`](../packet49c-round2/round2_submit.cpp).
The token1-only p42 implementation is an available historical implementation,
not this control. Packet45's `round2.hpp` is byte-identical to packet49c's;
packet54 uses that existing shared include to avoid defining two runtime type
universes in the benchmark. The sealed packet49c implementation remains the
control execution path. The measured starting value is **35.938 microseconds**
in [packet51's ranking](../packet51-round2/RANKING.md), not a new measurement.

One M=1 invocation launches 6,144 workgroups of 32 work-items, each exactly one
32-lane subgroup. There are 48 value heads, 128 state rows per head, and 128
BF16 state elements per row. Each lane owns four consecutive state elements
in registers. Occupancy is therefore not constrained by too few workgroups;
there are thousands. Registers, SIMD instruction issue and scalar dependency
chains can constrain achieved residency/throughput, but occupancy and register
allocation require compiler/device receipts. We do not invent an occupancy
percentage from geometry alone.

Each workgroup independently repeats two query/key norm dots and the same
head-dependent decay and beta. The subgroup-private dots have four ordered
multiply/add steps per lane, followed by a five-level adjacent 32-leaf tree.
The prediction dot must finish before delta; delta must finish before state
update; state update must finish before the output dot. Those two dependent
dots are unavoidable under the registered arithmetic. Query and key norm dots
are independent and can be interleaved without changing either tree.

The original kernel uses subgroup shuffles, **no local-memory scratch**, and
one subgroup/device-scope barrier after each token, including M=1. Registers
already hold four state elements per lane; “make state register resident” alone
is not a new lever. A wider register-resident row per lane would change the
32-leaf tree unless it emulates its original leaves explicitly; that is not
registered here. The four scalar BF16 state loads/stores can instead use one
four-element vector without changing element order or rounding.

For the production flags (stored FP32 decay coefficient), each row's source
computes `exp(gate)`, `log(1+exp(gate))` when gate is below 20, `exp(av*sp)`,
and sigmoid's `exp(-beta_input)`. Thus the ordinary branch has **three exp
calls and one log call**, plus two normalization square roots and the constant
`sqrt(128)`. Calls occur redundantly in all 32 work-items at source level:
589,824 exp and 196,608 log evaluations per M=1 invocation before any compiler
uniform-value optimization. These are source invocation counts, **not ISA or
cycle counts**. The gate>=20 branch skips its exp/log; a non-stored coefficient
adds another exp. Constant `sqrt(128)` can be folded exactly by the compiler.

The math comes from [packet17 detmath](../packet17-detmath/detmath.hpp).
Its exp is a range reduction plus a 13-coefficient,12-step compensated polynomial, with
explicit FMA residuals; log uses a compensated quotient and 11-term odd-series
polynomial. Replacing either with native/fast math is out of scope. Even when
executed as SIMD, repeating these long chains for every state row is a material
compute lever. No measured issue-rate/cycle model exists for these compensated
operations, so there is no defensible numerical compute-time floor yet.

## Byte and compute bounds

The state requires exactly `48*128*128*2*2 = 3,145,728` bytes read plus written
per token. Outputs add 12,288 bytes; unique QKV inputs add 20,480 bytes and head
inputs/weights only a few hundred bytes. A cold-state streaming lower bound
is therefore approximately 3.18 MB / bandwidth. Using the prior dense controls'
555–570 GB/s as a **conditional reference**, this is about **5.6–5.7 us**, or
roughly 6 us rounded. This is not a measured recurrence bandwidth ceiling:
cache residency, vector efficiency and scheduling can change it. Serial M=2
still rounds, stores and reloads BF16 state between rows.

For one row, four dots each use 128 multiplies, 128 lane additions (including
addition from +0) and 31 tree additions: 1,148 arithmetic operations. Decay,
state update, delta and norm epsilons bring the basic add/multiply count to
about 1,536 per row, or 9.44 million per layer, before transcendental internals.
The row also has 384 query/key normalization divisions at source level. These
counts explain why the byte floor is not a prediction of actual runtime. They
are useful work counts, not a claim that the GPU retires precisely that many
instructions; scalar broadcasts and constant folding can remove redundancy.

At the 35.938-us starting value, the most optimistic byte-only opportunity is
about 30 us. A candidate saving 10–20 us would already materially contribute to
the packet's 25-us bar and the banked integration threshold. Larger workgroups
without shared math would mostly retile already abundant work, so that arm is
not registered separately.

## Registered candidates and exactness argument

`rows4-shared` uses 1,536 workgroups of 128 work-items, four SG32s.
`rows8-shared` uses 768 workgroups of 256 work-items, eight SG32s.
Every group stays within one value head; 128 state rows divide both tile sizes.
One subgroup computes the unchanged four-term query/key leaves, advances the
independent norm trees together, applies the unchanged divisions, and publishes
256 normalized FP32 elements. One lane computes the unchanged head scalars and
publishes decay/beta. All row subgroups then run their original prediction,
delta, state update and output trees. This removes repeated identical
expressions, not arithmetic sites from any output's dependency graph.

The group uses **1,036 bytes** of local memory: 256 normalized elements, two
head scalars and one entry guard. There is one guard barrier and one shared
input barrier per token, plus a global/local barrier between serial tokens.
State remains four FP32 values per lane during the update, vector BF16 I/O
retains every BF16 cast site, and the next token reads the actual BF16 bytes.
M=1 has no final barrier because no following consumer exists in the kernel.

The tile sharing reduces head scalar evaluations to 1,536 or 768 per M=1
invocation. It reduces query/key normalization from 6,144 independent rows to
1,536/768 tiles. Workgroup-local traffic is newly introduced: roughly 1 KB of
shared writes per tile and 1 KB of shared reads per state row (plus scalars).
Actual bank conflicts, shared-memory broadcasts, compiler register pressure,
and time spent with the other subgroups waiting on the producer are unknown.
The wider tile may lose occupancy or wait longer; only two tiles are registered
rather than an open geometry sweep.

Inactive requests and existing sticky errors return without changing any
output/state byte. Invalid positions set the same sticky error. The production
`ng::Args::bits` conversion, detmath implementation, every reduction tree and
state read-after-BF16-store boundary remain unchanged. The candidate does not
change model weights, cache precision or oracle identity. CPU proof includes
both head mappings, both weight formats, stored/derived decay, serial M=2,
in-place state, capacity edges and preserved controls. Device E1/E2 must still
prove output **and state** bytes against both CPU and the production control.

## Integration map

Packet49c labels `blk.<layer>.gdn.recurrence` as `integrated::Op::gdn`. Its prepared
binding order is four inputs, two outputs, two weights, then scratch/error/
position/active and the existing tail binding. Adapter slot remapping is in
`adapter.cpp` around its `case Op::gdn` block and the `s.implementation==2`
round2 dispatch. `p54::recurrence_bindings(spec, bindings)` expresses precisely
that mapping into the 19-slot non-GEMV ABI. `RecurrenceKernel<4>` or `<8>` can
replace only that selected recurrence submission; the surrounding control
buffers and dependency chain remain production-owned. Host mirrors and the
unchanged `recurrence_control` oracle remain callable from the device build on
downloaded buffers. A packet49d integration must keep the normal allocation,
lifetime, alias and shape admission before issuing this operation.
