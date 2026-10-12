# Packet 30 and model-shaped attention integration

This packet copies the specific packet30 attention and small-GEMV arithmetic
and launch bodies into local files. Packet30 remains read-only. The adaptation
adds packet37 owner allocations and prepared submission capture; each GPU
stage is separately owned, timed, bounded and retained until completion.
No device ran and no new device speed is claimed.

`p30.attention.sg32` issues score, softmax, then value; the score-softmax variant
fuses the first two. Compile-time parameters are the subgroup width 32,
24 query heads, two KV heads, head width 256, and the stage integer (0/1/2/3).
Capacity, selection budget, admitted-slot upper bound and current position are
runtime shape/control data. The captured admitted bound is min(capacity,
budget+3), so replay does not capture the first request's position. Capacity256,
budget2048 and one decode token are covered by the new gates. No compressed KV
is introduced. The arithmetic preserves the original adjacent reduction tree,
selected-slot order, BF16 output rounding and deterministic exp/sqrt.

`p33.qsa.shape` now has separate compile-time capacity128 and capacity256
instantiations, both with compile-time budget2048 and tokens1. Other admitted
shapes use the original round2 body. K2 compares the incumbent, round2,
p33.qsa.shape, p30.attention.sg32 and p30.attention.score_softmax for every
timed context lengths 88, 104, 120, 136, 152 and 256. K1 retains every
length 88 through 152 and 256 for exactness. Length N means device position N-1.
All use capacity256, budget2048, one query token and reversed selected IDs to
exercise selected-order arithmetic. Every workload must pass exactness and
beat the same-run incumbent by more than10% before a global attention choice
can be selected. The capacity-limit point cannot be hidden by a shorter point.

`p30.small.rows4` is registered for HC gates, shared-expert down, small.hc and
small.ffn fusion tuples. Type, rows, columns and original split are compile-time
members. HC gate is Q8_0 R10240 K320 split1; shared down Q8_0 R2560 K640 split1;
HC low Q8_0 R320 K10240 split4 plus inject F32 R4 K10240 split4; FFN is router
F32 R512 K2560 split4, two shared projections R640 K2560 (Q6_K split4 or Q8_0
split1), and shared gate F32 R1 K2560 split4. Each subgroup computes one row,
with four subgroups per128-thread workgroup. The split4 sum remains
(part0+part1)+(part2+part3). Mini geometries retain their existing kernels.

CPU identity receipts: `p30-attention-cpu.json` and `p30-small-cpu.json`.
Attention checks the arithmetic-v2 Core, incumbent outputs, error status,
every admitted score/probability, all odd-tail tree sizes1..2051, malformed
arguments, stable selection ties, and the original explicitly documented
empty-selection discrepancy between the Core and incumbent. Empty selection
is diagnostic only. Small GEMV compares the expanded arithmetic with an
independent packed-byte oracle, preserving all original shape instantiations.
K1 additionally exercises the actual owner-backed dispatch wrappers. K2 adds
both p30 fusion candidates and the HC-gate/shared-down candidates; fusion
selection compares costs at both HC sites and every FFN quantization.

The packet39 expert epilogue remains an external dispatch extension point;
no packet39 code or timing is adopted here.

The integrated wrapper also preserves the full incumbent scratch contract: every
unselected score through capacity is written as negative infinity, including an
empty selection. The packet30 standalone gate now compares full score and
probability arrays, in addition to emitted BF16 values and status (1,016,167
checks). This closes the full-fixture mismatch caught before any card execution.

CPU K2 receipt rehearsal runs the actual summary on zero-timestamp host events;
it must reject device timing. Full summary bytes are preserved losslessly in
`evidence/window-cpu-k2-summary.json.gz` (gzip decompress to restore JSON),
with compressed/original SHA256 in `window-cpu-fixtures.json`. Repeated missing
timing rows are summarized by count in that small receipt, not presented as a
device pass.
