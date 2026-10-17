# Five named variants, seven production classes

The same bounded family is applied to every class; this is35 candidate/class
combinations, not a geometry grid. The manifest fixes the inventory and event
counts. Each candidate is separately compiled by arithmetic order and by
format/K family. The mixed small-FFN tuple retains its four-member dispatch.

| Name | Lanes per row | Rows per SG32 | Tile accumulators per lane | K parts | Purpose |
| --- | ---: | ---: | ---: | ---: | --- |
| row16-v8 | 16 | 2 | 1 | 1 | More rows in each subgroup; test work supply against longer chains |
| row8-dual-v8 | 8 | 4 | 2 | 1 | More rows with two independent tile chains |
| split4-row16-v8 | 16 | 2 row-parts | 1 | 4 | Shorter chains and more independent groups; include scratch and second launch |
| row16-dual-local | 16 | 2 | 2 | 1 | Independent chains; stage the compact IQ2 magnitude table locally |
| row32-quad-v8 | 32 | 1 | 4 | 1 | Shorten chains without a second launch; explicit four-accumulator tree |

Every tile contains eight consecutive values. Successive tiles assigned to a
lane alternate among its accumulators. A2 ends with `a0+a1`; A4 ends with
`(a0+a1)+(a2+a3)`. The lane reduction uses the adjacent binary tree. Split4
partitions whole eight-value tiles, then merges four FP32 partials with the
same adjacent four-part tree. K2560 has ten tiles per SG32 lane, so the quad
arm has24/24/16/16 additions in its chains, compared with80 in the old order.
All products and adds remain separate FP32 operations; final BF16 boundaries
and nonlinear epilogues are preserved.

Eight-activation vector loads and aligned code loads address issue overhead.
IQ2 local-table placement has no numerical effect; for other formats the
local table is not staged. These arms combine mechanisms deliberately; this
screen does not claim factorial attribution of a measured gain. Source-level
variants do not establish which machine instructions the compiler emits.

The controls use actual production kernels: accepted compact IQ2/IQ4, current
HC/attention winners, and unchanged dense QKV/Z and mixed small-FFN tuple.
All ten routed experts use distinct scattered IDs in a512-expert bank. E
covers two deterministic finite fixtures at M1 and both serial M2 rows,
including full output/status captures and split partials. The valid-active
probe does not qualify invalid routes, sticky errors or exceptional inputs.

Numerical distances to the old order are informational. `elements` counts
captured16-bit words, including unchanged zero status words; it is not a
model-error fraction. Device byte equality is against each candidate's own
CPU mirror. Fresh model/oracle equality remains later work.
