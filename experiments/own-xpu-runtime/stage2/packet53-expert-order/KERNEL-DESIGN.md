# Packet53 expert scheduling design

This packet changes where the work runs, while retaining each production
multiply, add, and BF16 output conversion. Device byte checks remain required.
No host test establishes device equivalence or speed.

Every arm uses 256 work-items per workgroup and SG32. Persistent arms launch
64 workgroups, intended as two groups per B70 Xe core under the registered
32-core topology. This is a fixed launch choice, not a device discovery call.
The other arms launch enough groups to cover their rows once. There is no
dynamic task queue, atomic work allocation, or dependence between output rows.

## Registered mechanisms

| Arm | Gate/up | Down | Logical lanes per physical lane | Workgroups | Codebook |
| --- | --- | --- | --- | --- | --- |
| persistent-global | yes | no | 1 | 64 | production global table |
| persistent-slm | yes | no | 1 | 64 | 8 KiB staged once per group |
| virtual2-global | yes | yes | 2 | cover rows once | production global table |
| virtual4-global | yes | yes | 4 | cover rows once | production global table |
| persistent-virtual2-global | no | yes | 2 | 64 | not used by IQ4_NL |
| persistent-virtual2-slm | yes | no | 2 | 64 | 8 KiB staged once per group |

Persistent global and SLM gate/up arms otherwise have identical work
assignment, paired input reuse, and arithmetic. Their difference measures
the table location with the fill amortized over several rows. Gate/up keeps
both streams in the same physical lane and loads their shared input once.
The combined SLM/virtual2 arm is registered before sealing rather than chosen
after seeing timings.

## Why the order is preserved

For virtualization factor `V`, physical lane `p` owns logical lanes
`V*p ... V*p+V-1`. Each has its own FP32 accumulator. Its input index is
`256*t + 8*(V*p+v) + j`, with `t` increasing and then `j=0..7` increasing.
There is no alternating accumulator or reassociated sum within a logical lane.

The first `log2(V)` levels of the original adjacent SG32 tree execute locally:
`(lane0+lane1)` for V=2, and `(lane0+lane1)+(lane2+lane3)` for V=4.
The remaining levels execute over groups of `32/V` physical lanes with
the same adjacent left-plus-right operands. Each subgroup therefore computes
V independent output rows. This is the identical expression tree, with nodes
assigned to different physical lanes.

IQ4_NL K=640 uses three eight-value steps for logical lanes 0–15 and two for
16–31. The check against K happens separately for each virtual chain, so
neither padding nor an extra floating-point zero add changes those chains.

For persistent workgroups, subgroup `s` in group `g` computes rows
`(8*g+s)*V+r + iteration*(64*8*V)`, for `r=0..V-1`. This is a bijection over
the bounded output-row domain. Subgroup loops use the first row as their
condition; padded physical lane groups still execute every shuffle. The
single SLM initialization barrier is reached by every work-item before that
loop, with no later cross-subgroup barrier.

## Codebook and bank-conflict question

The SLM arm stages the production 2,048 uint32 words without changing their
representation. Each eight-value decode still reads words `2*index` and
`2*index+1`, uses the original signed-magnitude and scale operations, and
retains the exceptional-scale fallback expression. The supported repack
continues to reject nonfinite model scales.

The consecutive-word layout can concentrate each individual gather on half
of the bank residues when banks are selected by low word-address bits. Route
and codebook indices vary across the fixture. No bank-count assertion or
conflict-free claim is needed for correctness. This round measures the
global/SLM pair; a conflict count would require a later separately authorized
profile. It deliberately does not introduce a bank-layout sweep, duplicate
tables, or table compression into this small first round.

## Production contract

The ten-pointer binding matches the matched production adapter: weight,
peer weight, input, output, peer output, routes, status, peer status, sticky
error, active. IQ4_NL input advances by routed slot times K; IQ2_S gate/up
shares the input across routes. Invalid or out-of-range route rows write the
same canonical NaN BF16. Slot status is written on output row zero; invalid
routes set sticky error only when active, preserving an earlier error value.
The M=2 benchmark issues two serial rows with their own input/routes, exactly
as the production engine does; the kernel does not fuse those calls.
