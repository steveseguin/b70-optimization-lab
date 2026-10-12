# Independent epilogue identity review

Reviewer: harness agent, separate from the fusion implementation author.
Reviewed `fused.hpp` and `fused_sycl.hpp` against packet29 `kernels.hpp`,
`adapter.cpp`, p28 lane bodies and p33 `candidates.hpp`. This is source reasoning;
it does not replace CPU gates, generated assembly checks or device byte gates.

| Fusion | Independent source comparison |
| --- | --- |
| Expert gate/up activation | Both GEMV lane trees finish before BF16 conversion. Gate and up retain their raw BF16 outputs. Activation widens those bytes, evaluates `gate * sigmoid(gate)`, multiplies up, then rounds once. This matches `ng::activation` with `extra=1`. |
| Paired expert status-only | The same paired GEMV writes both gate/up BF16 outputs and both status arrays unconditionally. Only row zero of an invalid slot attempts atomic zero-to-one sticky update when active. No activation output is touched, so there is no cross-slot suppression requirement and no subgroup vote. The separate activation launch remains. Both original checks depend on the same route-validity predicates, so their final sticky bytes agree, including preexisting nonzero errors and inactive execution. No context-position guard is added. |
| Expert down status | Raw down output and slot status remain observable. Invalid route detection is integer-only. No routed sum or ten-expert mixture reduction is inserted into the GEMV. |
| HC low activation | Divide the widened BF16 low result by four before SiLU; round activation afterwards. Split-four low keeps `(part0+part1)+(part2+part3)` inside the original rows4 work-group, after its existing local-memory barrier, before BF16. |
| Shared gate/up activation | Previously computed gate is BF16, and up rounds to BF16 before the same product as `ng::activation`. Shared Q6 split-four must remain split-four; Q8 remains split-one. |
| Attention output/combine | Split-four projection finishes its original pairwise tree and BF16 store first. Each stream computes residual plus the rounded branch times `2 * sigmoid(inject / 4)`, then stores BF16. Four stream outputs are disjoint across row owners. |
| GDN QKV/convolution | Each dot rounds to BF16 before use. The original convolution adds four taps left-to-right from +0 with FP32 decoded weights; dilation-one has no BF16 accumulator round before SiLU. Candidate `row_tail` preserves that sequence, rounds the output once, shifts history bytes left and stores the raw QKV BF16 byte as newest history. One row owns its three state bytes and output, so no cross-row dependency or race is added. |
| Shared down/combine | Down rounds to BF16 first. The original `sum=0; sum=sum+mixture*1` expression, BF16 mixture round, separately rounded gated shared contribution, their sum and BF16 blend store all remain. Residual combine then consumes the rounded blend, never its unrounded accumulator. |

`ng::Args::bits` and `iq3::bf16_bits` have the same ties-to-even adjustment
and the same NaN quiet-bit expression. This confirms conversion spelling,
not arbitrary NaN arithmetic propagation: CPU tests found a payload-NaN
activation difference, so that case remains explicitly unqualified. The
native G4 check keeps nonfinite byte equality mandatory and will reject a
candidate if the original device tail and fused tail disagree.

For the full expert activation fusion the subgroup vote checks route validity without adding
a floating reduction. Invalid partial row counts retain the old raw NaN
outputs; a route that is structurally valid still follows the old activation
path. When any route is invalid, every row sees the same route-validity verdict,
so no row can write activation while another raises the sticky error. Atomic
compare/exchange changes only zero to one, preserving any preexisting nonzero
error and avoiding concurrent non-atomic same-address writes. Inactive work
retains the unconditional GEMV outputs and suppresses the tails, as before.

Integration must preserve the prerequisite gate/shared-gate/mixture buffers
and the documented trace-visible raw outputs. This review does not authorize
removing them. G4's unfused tiny kernels must be the actual runtime bodies and
geometries; the initial handwritten timing replicas were flagged and replaced
by the root agent's source-extracted original bodies.

The later position guard correction was also reviewed: `ng::group` checks signed
position before any convolution/activation/blend output. Candidate
`position_valid` retains that guard, while the standalone down-status and
attention-combine families keep their original no-position-check behavior.

Final device-control review: HC low and both shared-up formats now use the
actual `p28.dense.rows4` geometry. For Split4 there are 512 work items per
work-group (four rows times four SG32 parts), 64 local floats and the original
unconditional barrier; partials occupy row*8+part and the lane-zero part-zero
owner combines `(p0+p1)+(p2+p3)` in the same kernel. Split1 shared Q8 keeps the
original rows4 grouping and source barrier (which codegen removes when unused).
No extra finish event is counted for these three families. Attention remains
SG32 Split4 plus its separate finish event, whose epilogue replaces combine.
The unfused status tail uses the original Glue WG128 and 8192-float local
allocation. Activation/convolution/moe call the original `ng::group` and its
original WG/local geometry. Residual combine calls original `simple_body` with
a range launch. These bodies are source-extracted, not handwritten timing
replicas. All seven candidate families retain the raw and state bytes described
above; full activation and status-only expert candidates are mutually exclusive.

Final static selection contains seven accepted format rows, totaling 431
potentially removed launches per token: down status48, HC low97, shared up48,
attention combine48, shared down/combine96, IQ2_S paired checks94. Both full
expert activation formats add flag spills, both convolution formats grow a
GEMV scheduling loop, and IQ3_S status-only grows a scheduling loop. Those five
rows remain rejected even if their future device timing happens to look good.
This count is a candidate launch count, not a measured speed or adoption claim.
