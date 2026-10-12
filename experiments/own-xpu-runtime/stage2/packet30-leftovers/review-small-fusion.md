# Independent small GEMV and fusion review

Reviewer: packet30 route-family agent. Sources read directly: small.hpp/.cpp,
fusion.hpp/.cpp, packet28 dense.hpp, packet27 arithmetic.hpp/kernels.hpp/
core_v2.hpp/specialised.hpp, packet9 dispatch.hpp. No device run.

Small GEMV member geometry agrees with the frozen dispatch table: hc gate and
shared-expert down use SG32; low/inject, router, Q6 gate/up and shared scalar
use four split intervals; Q8 gate/up use one interval. Member::lane retains
packet28’s original lane-strided eight-element sequential product accumulation.
The new shuffle loop calculates precisely tree32’s adjacent levels. Only
lane0 consumes each split root, and split4 combines as `(p0+p1)+(p2+p3)` before
the sole output BF16 conversion. Each subgroup owns one matrix row. Concatenated
member row ranges are disjoint and branch-uniform within each subgroup.
Padded rows neither read nor write matrix data. The launch clamps row strides
to exact matrix bytes so oversized allocation padding cannot change addressing.

Fusion combine computes BF16(residual + addition*(2*sigmoid(gate/4))) before
squaring for the norm. It reuses this identical rounded value for the saved
combine output and normalized output. The sum is the original adjacent square
tree, followed by division by width, +1e-6, detmath rsqrt, `(x*inv)*(gain+unit)`
and output BF16. Aligned subtree decomposition and every odd-tail +0 agree
with Core::tree; partial80 covers width2560. The tiled variant repeats the
same entire norm tree per tile rather than merging partials in a new order.
Tiles write disjoint 256-element ranges. Mix retains the sequential h=0..3
sigmoid-weighted sum and final /4 before BF16. These changes preserve every
intermediate BF16 point from Core::hc_combine/norm/hc_mix.

No arithmetic-order or output-write ownership defect found. The error flag
uses atomics on device and the invalid-position writer is unique. Compile/link
precision flags and native equality are still necessary to establish the
compiled implementation’s behavior.

Guard review found missing alignment checks in small and fusion APIs and
missing overflow checks before pointer-end arithmetic. These were reported to
the author for repair and poison tests. This review is conditional on the
recorded repairs below; it is not an approval of the earlier unchecked APIs.

Repair follow-up: directly reread small.hpp and fusion.hpp after changes.
The used spans now reject pointer-end overflow and typed misalignment before
submission. Fusion treats sticky error slot15 as writable, rejecting aliases
with either input or output spans. The author added shifted-pointer, overflow
and sticky-error alias poison tests, then reran g++ and icpx twice. These
source repairs resolve the findings above. No outstanding source-level finding
remains; this remains CPU-only review, not native acceptance.
