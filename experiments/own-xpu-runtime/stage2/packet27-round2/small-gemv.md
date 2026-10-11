# Compile-time sibling GEMVs

These are candidates, with no device execution or speed claim in this packet.
The measured packet26 class times identify work to target; they do not measure
any packet27 implementation. K2 compares the sum of the actual incumbent R5
member submissions with one new tuple submission. Admission requires every
production format workload exact and the candidate median below 0.9x the sum.

| Class / dispatch key | Measured member time per layer | Candidate | Hypothesis, microseconds |
| --- | ---: | --- | ---: |
| hc.a / hc.f low + inject; `small.hc` | about 37–39 us per pair | `(Q8_0,320,10240,expanded_split4)` + `(F32,4,10240,constant_split4)` | 22–27 |
| gdn.a + gdn.b; `small.gdn.ab` | about 19 us per pair | two `(F32,48,2560,constant_split4)` members | 8–12 |
| router + shexpgate + shexpup + shared_gate; `small.ffn` | about 61 us total | router `(F32,512,2560,constant_split4)`, gate/up `(Q6_K,640,2560,expanded_split4)` or `(Q8_0,640,2560,expanded_sg32)`, shared gate `(F32,1,2560,constant_split4)` | 34–42 |
| hc.a / hc.f gate | about 29.5 us | existing single GEMV; low → activation → gate dependency prevents including it in the low tuple | unchanged hypothesis |
| shexpdown | about 16 us | existing single GEMV; gate/up → product → down dependency prevents including it in the upstream tuple | unchanged hypothesis |

Those hypotheses suggest roughly 2–3 ms/token of savings, depending on the
formats and measured launch counts. They do **not** establish the requested
11 → 5 ms goal. That goal remains a card measurement question; subtracting
launch overhead alone cannot establish it. K2 and W2c must determine where the
remaining time goes before more work-group changes are admitted.

The admitted model plan was checked directly: all96 HC low/inject pairs use
Q8_0/F32; all36 GDN a/b pairs use F32; shared gate/up use Q6_K in47 layers
and Q8_0 in layer2. Router and shared scalar gate are F32 in all48 layers.
The seven tuple instantiations therefore cover the actual small-GEMV schedule
as well as mini. No mixed gate/up format pair is silently accepted.

## Structure and available inputs

HC executes norm, low, activation, gate, mix, inject. The tuple moves inject
up to low; both consume the completed HC norm. Gate and mix stay after low's
activation. Each HC stream pair is selected independently by schedule location,
with the same concrete template shared by attention and FFN sites.

GDN executes qkv, z, a, b, convolution, recurrence, gated norm, output. The tuple
executes a and b where a previously ran; qkv and z remain ordered before it,
and recurrence remains after it. Both consume the completed attention norm.

FFN executes router, route/gather, routed expert projections, shared gate/up,
shared activation, shared down, shared scalar gate, combine. The tuple executes
router, shared gate/up and shared scalar gate where router previously ran.
All four consume the same completed FFN norm; route still follows router,
shared activation follows both shared projections, and combine follows down.
Moving independent shared work earlier does not move any dependent operator.

The runtime retains the original plan for the oracle. It prepares a host-only
map from the first site to its members and skips those members' later device
submissions. Construction checks exact input labels, same card, registered
format/rows/columns/arithmetic, followers after the first site, and no
intervening input overwrite, output overwrite, or early output consumption.
Allocation validation also rejects aliases involving any writable output.
Two-card matrices retain their existing lifetime; the one-card loader keeps
all members in the already-staged current layer. No allocation, copy, or wait
was added inside the device kernel.

## Fixed tuple arithmetic

`small_gemv.cpp` instantiates each member's type, rows, columns and arithmetic
variant as C++ template parameters. Each tuple captures only typed pointers
and row-byte strides by value. A workgroup selects one member once from its
group index; each member invokes its own compile-time body. There is no device
descriptor table, runtime format switch or type dispatch inside its row loop.
The member dispatch branch is uniform across every lane of that workgroup.

For SG32 arithmetic, each lane still accumulates the eight adjacent products
starting at `tile + lane*8`, with tile advance 256, in exactly the original
order. It then uses adjacent width 1,2,4,8,16 reductions. Expanded members use
the R5 expanded weight equation, with no new precision or expansion. F32
members use the existing constant decoder, same products and accumulation.

For split4, the original tile-boundary partition stays unchanged. The four
subgroups compute the original four parts. One local barrier combines exactly
`(part0+part1)+(part2+part3)`. Keeping the final four-part reduction in this
workgroup removes the incumbent's separate split-finalize launch for F32
members; it does not move any arithmetic addition. BF16 output conversion
happens only after the same complete row result. Every row has one writer.
The only local scratch contains four disjoint subgroup partials, read after
the barrier. A short final SG32 workgroup masks incomplete rows; split4 tuples
allocate exactly one workgroup per complete row. The single shared-gate row
uses all four subgroups across its four existing arithmetic partitions.

The observed 15–30 us classes exceed the measured 3.4–5 us minimum launch cost.
Launch removal alone therefore cannot explain all class time. Small F32 row
counts underfill the card, split finalize costs another launch, and the
incumbent four-subgroup launch can leave subgroup slots idle. Combining
sibling work offers more ready groups under one submission. It does not prove
that memory bandwidth, register occupancy, or compiler overhead has improved.

## Gates

Seven literal tuples cover production HC, GDN, Q6 shared FFN, Q8 shared FFN,
and the three mini-model equivalents. K1 uses all seven at full tuple geometry,
with finite varied, signed zero, finite subnormal and finite extreme inputs.
Each runs the R5 members and the tuple against independently computed frozen
CPU row arithmetic. Shape, column, route, writable alias and arithmetic
mutation checks run before device entry. Host twins call the same per-lane
functions and tree. K2 uses all four production tuples; it continues after
an individual candidate fails, reporting the sum-member identity explicitly.
K1 output bytes, check totals, and fresh-owner repetition are reported by the
shared fixture driver. Device argument validation invokes every tuple on the
host without submitting a device job.
