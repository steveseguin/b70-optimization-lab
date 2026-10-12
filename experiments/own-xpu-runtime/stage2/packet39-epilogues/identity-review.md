# Independent epilogue identity review

This review was performed by the chain/host-gate agent, independently of the
kernel author's conclusions. It read packet29's Builder, main binding and
plan transformations, core_v2, p28 submit/dense/expert, packet33 candidates,
packet29 runtime/simple and non-GEMV bodies, and packet39 fused.hpp and
fused_sycl.hpp. No device executable was run.

## Row arithmetic

| Fusion | Independent arithmetic assessment |
| --- | --- |
| Paired expert gate/up -> activation and checks | Dot body calls p28 expert_lane with Shared=false, Paired=true. Every lane keeps eight consecutive products and original + accumulation, then width=1,2,4,8,16 adjacent tree. Gate and up are **separately** converted to BF16 before widening into `silu(gate)*up`; result gets its own BF16 conversion. Gate/up and both statuses remain materialized. |
| Paired expert gate/up -> checks only (fallback) | Both paired sums/trees, y/py B stores and both statuses remain identical. Their status values are provably equal because both projections share the same validated route and row shape. Invalid-slot row0 CAS preserves sticky semantics; no activation/output-tail writes occur, and position remains unchecked as in the original checks. The separate expsact launch must remain. |
| Expert down -> check | p33 down_lane<1,K> is select-based IQ4_NL decode with original scale*level, product, and lane accumulation. No mixture reduction was inserted. Status reflects descriptor validity, not whether a particular row lies beyond row_count. |
| HC low -> activation | Original split4 partial grouping, where selected, is retained and merged `(p0+p1)+(p2+p3)` before B; then divide by 4, deterministic silu, B. A BF16 conversion before division is essential and present. |
| Shared up -> activation | Shared gate row is already materialized. Up result first gets B; activation computes gate-silu then multiply by up, finally B. No extra BF16 point inside silu. Shared gate/up format qualification remains per registered format. |
| Attention output -> residual combine | Output projection B is retained. For each coordinate, four stream stores perform `B(stream+attention*(2*sigmoid(inject/4)))` in the original expression order. Four stores consume no other GEMV row. |
| GDN qkv -> convolution | Qkv B is retained before the ordered four-tap FP32 accumulation beginning at +0. Conv weights are F32 in all 36 actual tensors; no B(acc) precedes deterministic silu for dilation1. Conv output gets B; history shifts its original three BF16 entries and appends the exact raw qkv BF16 bytes. Each channel owns disjoint history/output rows. |
| Shared down -> blend and residual | Down B is retained, as are `+0 + mixture*1`, B of that term, B of shared-down*sigmoid(shared_gate), B of their sum, and B of each residual update. Moving shared_gate and the existing mixture before down gives the needed scalars without changing any reduction. |

The imported dense body uses p33 dense_lane for GDN QKV Q6_K/Q8_0 K=2560;
shared up retains its measured p28 body. The subgroup tree is unchanged.
Attention Split4 retains its separate existing finish kernel. HC low and shared
Q6 Split4 use the existing rows4 local tree/barrier and finish in the same
kernel; shared Q8 uses the existing rows4 WG128 Split1 geometry. These source findings do not substitute for the offline
code-generation check or native exactness gate.

## Route/status control

The original GEMV is unconditional with respect to active/sticky controls.
Both candidate host and device paths retain unconditional y/status writes.
For paired expert activation, each subgroup evaluates all admitted route
descriptors using a subgroup vote after the unchanged GEMV reduction;
when any route is invalid, **every** subgroup suppresses activation, avoiding a
race where a valid subgroup could write before another sets sticky. The route
array is immutable for the entire launch. Only row 0 writes each slot's
uint32 status, and paired status arrays get the same validity result.

`sticky_fail` uses compare_exchange(0,1). It therefore never overwrites an
already-nonzero error code. Every successful concurrent writer stores exactly
uint32 1. Failed compare/exchanges do not modify the memory. Inactive inputs
never call sticky_fail. Because all subgroups see the same route-validity vote,
there is no interleaving in which an enabled activation competes with a
route-error store. For down-status fusion there is no conditional activation output: each invalid
slot's row-zero writer performs CAS(0,1), and all y/status stores stay
unconditional. No all-route vote is necessary for down. Dense tails have no
route errors; their only new error writer is the uniform invalid-position
path. Valid positions therefore observe the dependency-completed sticky state.

The original invalid-route output is canonical BF16 NaN, but a *valid*
descriptor with row_count shorter than rows also writes canonical NaNs outside
the count while status remains zero. That distinction is preserved.

## Findings and qualification limits

1. Initial CPU diagnostics contained 18 mixed-NaN/Inf output mismatches.
   Packet29 NONFINITE-GEMV.md explicitly excludes these synthetic inputs from
   its qualified GEMV contract. User requested that same policy, so retaining
   them as FAILED, unqualified diagnostics is acceptable; calling them exact
   passes or silently comparing NaNs as equal is not. Qualified finite, route-invalid and control-state gates remain strict;
   separate BF16-boundary probes include signed zero and rounding ties.
2. Chain launch needs complete per-kind pointer, extent and nonaliasing
   admission. In particular residual streams must not alias x or weights:
   early stream stores would otherwise race another row's GEMV reads. The
   runtime's distinct allocations satisfy this, but a raw public Bound API
   must enforce or clearly bind the same contract. This finding was fixed: the final validator checks per-kind mandatory
   pointers, alignment, declared ranges, row stride, 32-bit overflow and
   overlaps of every write range with all reads/writes. Actual allocation
   extent/ownership remains the coordinator caller responsibility.
3. Position controls on original ng activation/blend are not a free input.
   A full runtime token has passed begin's position bound before these sites.
   Standalone G4 fixtures must use an admitted position, or include equivalent
   position failure behavior. Descriptor status checks and simple hc_combine themselves do not
   bounds-check position. The final position_valid<Kind> preserves this
   distinction and the CPU fixture set includes both invalid signed positions.
4. No route ranking or router arithmetic is changed by these kernels. Stable
   route ties and router NaN rejection remain in the unchanged route body;
   they must not be claimed as newly accelerated operations.
5. The host model gate runs materialized original GEMV followed immediately
   by packet39 scalar helpers within that same plan site. It tests complete
   chain values, reordering and skipped sites. It does not execute the SYCL
   body, test concurrent scheduling, or establish native speed.
6. GDN qkv -> convolution was identified in this audit and subsequently
   implemented as the seventh kind, with the exact equation reviewed above.
   GDN z -> gated and HC gate -> mix, in contrast,
   have cross-row dependencies that invalidate the naive proposed epilogue.

## Host overlay review

The final seven-kind copied main executes `p39_after` only after unchanged GEMV completion on
the synchronous Host backend. It preserves gate/up/down outputs for observers.
The original logical check/activation/combine sites become no-ops, but their
labels remain so unchanged layer-fixture capture still sees ffn.combine.
The shared scalar GEMV and unconditional ordered mixture move to the expert-
down boundary. Neither uses shared branch outputs; both inputs are immutable
throughout that span. Their original sites are suppressed exactly once.

The overlay disables combine+norm dispatch flags, retaining normal parallel
norm stages. It does not enable small.ffn/small.hc sibling groupings, avoiding
competing ownership of moved projections. `host-build-receipt.json` pins
compile/link flags, reused host objects, binary, source, overlay and the
fused header identity at compile time. Later native/header changes must be
reported separately if they alter the scalar helper bodies under test.

The initial six-kind CPU attempt was stopped cooperatively by exact PID on
the coordinator's instruction to include convolution in a fresh complete gate.
Its failed partial receipt is `host-initial-six-kind-stopped.json`; it establishes
no token/layer oracle pass. The second attempt includes all seven kinds.

The eighth source-reviewed kind, `expert_checks`, was added as an offline-codegen
fallback while the seven-kind host pass was already running. It only removes
the two status launches and retains separate activation. Its source/CPU gates
are separate; the full-model host receipt still names its actual seven kinds.

## Additional baseline-geometry finding

The first G4 draft used WG32 split4 (partial and finish, two launches) for HC
low and shared Q6 up. The recorded selected runtime uses `p28.dense.rows4`
for those sites: its existing local split tree finishes in one launch. The
class-time receipt independently confirms one GEMV launch per group. This
was reported as a blocker for calling those G4 controls the actual runtime
chain. Attention output uses WG32 split4 in the receipt and legitimately keeps
its separate finish. This finding is CLOSED in the final rows4 implementation: HC low and shared
Q6 use WG512 with four adjacent subgroup partials per row and the unchanged
`(p0+p1)+(p2+p3)` local finish. Shared Q8 uses WG128, four rows. The local
index `(sub/Split)*8+part` equals original p28 projection-zero indexing.
Inactive tail subgroups still reach the existing barrier and never read
uninitialized partials. Every active row has exactly one BF16/raw/tail writer.
Shared up now explicitly uses p28 dense arithmetic as the measured incumbent.
No extra local array, barrier or finish launch is introduced. The offline
assembly check remains independent of this source identity review.
