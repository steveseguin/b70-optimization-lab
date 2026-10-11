# Packet 17 — arithmetic identity v2

CPU-only preparation. **No device ran in this preparation task.** The identity is
`iq3-p17-detmath-v2`. Host agreement is evidence, not device qualification.
The declared GEMV order remains `r234-sg32-split4-bf16`. The model is the
Unsloth Qwen3.8 Flash-Next UD-IQ3_XXS quantized compressed version, with its
existing admitted bytes unchanged.

[Closeout](CLOSEOUT.md) · [Closed arms](DO-NOT-REPEAT.md) ·
[Evidence retention](RETENTION.md).

## Why v1 cannot be the portable reference

The October 11, 07:28–07:45 UTC card-3 observations supplied by the coordinator:
Packet 13 produced all eight expected tokens
`332,37947,1653,10082,3508,8812,25,23288`, but **zero of 48** first-step
layer states equalled its CPU reference. Layer 0 differed in 4,091/10,240 BF16
values (maximum 0.00098, relative RMS 0.33%); relative RMS reached 5% at layer 47.
See [device comparison](../packet13-integrate/correctness/device-comparison.json).

Packet 15's parallel kernels equalled its serial core on the same device in
72/72 cases and repeated across two fresh owners, but device core equalled host
core in only 50/72. Original differing-byte counts were: gdn-1 25;
gdn-packed-1 18; gdn-runtime-f32-1 18; route-gather-1 10; qsa-attention-1 48;
gdn-3 114; combine-norm-3 12; mix-3 1; route-gather-3 30;
qsa-attention-3 175; gdn-87 512; combine-norm-87 99; mix-87 11;
gdn-gated-87 6; route-gather-87 345; qsa-prepare-87 1;
qsa-attention-87 55,800; route-varied 6. The original per-case log also records
gdn-packed-3 104; gdn-runtime-f32-3 104; gdn-packed-87 496;
gdn-runtime-f32-87 496, completing the 22 differing cases.
Exact original per-case evidence is under
`../packet15-nongemv/build/card3-exact-b/owner0/arithmetic-diagnostics.jsonl`.

The old specification delegated elementary functions to platform libm. Flags
already disabled fast math and contraction and preserved denormals. Those flags
do not define exp/log/trigonometric bits. Equal tokens do not excuse unequal
states, and an unchanged C++ expression does not prove equal device arithmetic.
Some matching fixtures still evaluate elementary functions (conv uses sigmoid/exp;
plain norm uses sqrt/division). Their BF16 outputs can hide elementary-bit
differences. W-A is needed to localize which operations differ; the observed
fixture pattern alone does not isolate a single library function.

## Reimplementable numerical specification

The defining executable specification is [detmath.hpp](detmath.hpp). All
finite arithmetic is IEEE-754 binary32, round-to-nearest ties-to-even with
gradual underflow. No FP64 operation occurs. Each written +, -, *, / rounds
separately; contraction/reassociation is forbidden. `fma(a,b,c)` rounds the
exact product-plus-add once. It is an IEEE operation implemented using a compiler
intrinsic, not a platform transcendental routine. Division and sqrt must be
correctly rounded. Builds require precise device division/sqrt options as well
as `-fno-fast-math -ffp-contract=off -fdenormal-fp-math=ieee`.

`Pair {hi,lo}` represents a compensated sum of two binary32 values. `sum` is
the explicit error-free two-sum sequence; `add` sums high components, then
low components in its written order; `mul` obtains the high-product residual
with fma and adds the two cross products with fma, omitting low*low. `quotient`
computes a binary32 quotient and one compensated residual correction. These
are our own implementations of standard compensated-arithmetic ideas; no code
was copied from a library or another runtime. The exact hexadecimal constants,
helper operation order and loop-unrolled polynomial order in the header are
part of the identity.

For exp, choose integer n by truncating `x*0x1.715476p+0f` plus signed 0.5.
Subtract n times the two-component ln(2)
`{0x1.62e43p-1f,-0x1.05c61p-29f}` using Pair operations. Evaluate the degree-12
Taylor polynomial for exp with split binary32 coefficients 1/k!, from k=12
down to zero, by Pair Horner evaluation. Coefficients were derived directly
from rational factorials; the retained hexadecimal constants are authoritative.
Scale by a power of two. For n <= -126, scale the Pair to the integer subnormal
significand domain and round once using both residual components, ties-even.
For n=128 first multiply the Pair by two and scale by 2^127.

For log, normalize subnormals by the exact multiplication 2^23. Extract the
exponent and mantissa by integer bits; if the mantissa exceeds
`0x1.6a09e6p+0f`, halve it and increment the exponent. Compute
z=(m-1)/(m+1) with the compensated quotient, including the exact two-sum
for the denominator. Evaluate
`z*(2 + z²*(2/3 + z²*(2/5 + ... + z²*(2/21))))`
in the fixed Pair Horner order, then add exponent times the split ln(2).
Round the resulting Pair once to binary32. Softplus keeps the old composition:
`x < 20 ? log(1 + exp(x)) : x`; there is no log1p rewrite.

Both exp and log return canonical positive quiet NaN `0x7fc00000` for any NaN;
log also uses it for negative nonzero inputs. This intentionally differs from
platform NaN payload/sign propagation. log(+0) and log(-0) return -infinity;
log(+infinity) is +infinity; log(1) is +0. exp(-infinity) is +0;
exp(+infinity) is +infinity and exp(±0) is 1. Exp overflow/underflow cutoffs
are the explicit hexadecimal comparisons in the header. Subnormal outputs are
preserved, not flushed. errno and floating exception flags are outside this
model's numerical identity. Finite output differences from glibc are measured
as accuracy diagnostics, never a bit-exact glibc claim.

Sqrt remains the correctly rounded IEEE operation. Reciprocal square root is
**rounded sqrt followed by rounded division**, not a correctly rounded
mathematical reciprocal square root. The default candidate is a volatile
integer-bit barrier between sqrt and division (mode 1). Modes 0 (plain) and 2
(integer-corrected reciprocal of rounded sqrt) remain selectable with
`DETMATH_RSQRT_MODE`; changing the selected mode requires its W-A evidence and
a rebuilt receipt. Mode 2 uses a 64-bit integer quotient/remainder of 2^47 by
the normalized 24-bit significand and rounds ties-even. W-A must prove both
sqrt and the selected reciprocal spelling, including denormals. Host success
is not permission to assume the compiler preserves those operations on Xe.

## RoPE constants

[rope.bf16](rope.bf16) is 524,288 bytes: 4,096 positions × 32 frequencies ×
(cos,sin), little-endian BF16. [generate_rope.py](generate_rope.py) pins the
host authority to scalar glibc powf/cosf/sinf, explicit FP32 angle multiplication,
and BF16 ties-even. The generator and libm identity and table SHA-256 are in
[rope-receipt.json](rope-receipt.json). Regeneration refuses changed bytes.
A generated constexpr header lives only in ignored build/. The device reads
constants and performs no pow/sin/cos. This version supports rotary=64 and
positions 0..4095; extending the table is a new hash-bound model-constant
artifact. The serial core rejects out-of-range geometry, and the parallel
kernel's existing capacity/position bounds cover the same table.

## Proof obligations and evidence

[gnu-host.json](gnu-host.json) and [icpx-host.json](icpx-host.json) record
72/72 parallel-v2 == core-v2 under each compiler and 72/72 core-v2 GNU ==
core-v2 IntelLLVM. Each comparison covers 79,551,248 output bytes. The
v1 comparison is informational; v2 is a newly defined reference, not a claim
that v1 state bytes are unchanged. [Fixture comparison](fixture-comparison.md)
lists every case. [Independent arithmetic review](review-special-cases.md)
and [accuracy code/results](accuracy-results.json) are separate checks.

| Function | Maximum measured true error | High-precision inputs |
| --- | ---: | ---: |
| exp | 0.50000004486907294204 ULP | 285,253,651 |
| log | 0.50000001016321183457 ULP | 285,253,651 |

The independent check includes 2^28 stratified bit patterns, dense real inputs,
transition collars and every log input in [0.5,2). Worst vectors are recomputed
at 100-digit Decimal precision in [accuracy-high-precision.json](accuracy-high-precision.json).
No sampled error exceeded one ULP and no sampled adjacent monotonicity check
failed. These are measured maxima, not a mathematical whole-domain upper-bound
proof. Exhaustive glibc comparison is only a sanity bound: glibc is not the
true-value authority. [The exhaustive receipt](host-hashes-receipt.json) covers all 2^32 encodings
per function: exp differed from glibc at 170,655 finite inputs, log at 416,903,
always by at most one ULP. Both had zero monotonicity failures and zero
non-NaN special-result mismatches. The pass took 91.98 seconds for exp and
276.28 seconds for log on one idle-priority CPU thread. NaN encoding differences
include the documented canonicalization and negative-log domain convention.

[WINDOW.md](WINDOW.md) gives separately admitted W-A/W-B commands. W-A measures
native elementary differences, three reciprocal-square-root spellings, division
and contraction, plus every distinct actual elementary argument from all 72
v1 fixtures. W-B checks all 2^32 exp and log inputs by two 64-bit chunk hashes,
then requires parallel-v2 == device-core-v2 == host-core-v2 on all fixtures
and identical results from two fresh owners. Hash equality has a collision
risk; it is not a stored element-by-element proof. No W-A or W-B ran here.

The re-based real-model CPU oracle uses the same 87-token incident prompt,
48-layer graph, per-row GEMV order, BF16 boundaries, 64-token cap, top-five
logits each step and all 48 hidden-state fixtures at steps 1..8. The completed
[run receipt](../../../qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/receipt.json)
records all 64 generated tokens and 384 layer files.
[The full comparison](oracle-comparison.json) reports **41/64 token positions
equal**, with the first divergence at step 42. [Per-layer differences](oracle-layer-comparison.md)
cover all 384 fixtures. At step 1, layer 0 is unchanged; layer 47 differs in
9,758/10,240 BF16 values with 3.8136% relative RMS. The run used two CPU threads
at nice 19, idle I/O, with no device dependencies. It does not qualify a device
runtime or promote a performance result.

The v2 oracle first changes the generated output at step 42: v1 chooses token
1881 with top logits 22 versus 21.875 for token 279; v2 ties both at 22 and
chooses token 279 under the unchanged greedy tie rule. The first 41 tokens,
including steps 11 and 12, agree. Therefore v2 is an **output-changing arithmetic
revision relative to v1**, not a lossless replacement for v1. It remains a
candidate identity requiring the owner's quality judgement before adoption;
none of the host or prepared device gates overrides this difference.

## October 11 link precision repair (CPU only)

The coordinator's [attempt-a evidence](evidence/20261011-wb-a-link-flags/README.md)
shows that both precise divide and precise sqrt flags must also be on the link
command. Both device targets now have them, and the builder checks every
generated SYCL link command before compiling. The existing exhaustive host
hashes and CPU oracle are hash-verified and reused. Attempt-a originals are
preserved under that evidence folder. No device ran in this repair task.
W-B is the next coordinator window; W-A host-work relocation follows separately.
