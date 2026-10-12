# Independent expert-down identity review

This reviewer did not implement the new kernels, compile code, run a device,
open a device node, or invoke device discovery. Source review covers the two
`p29.down.wg32` and `p29.down.rows4` entries. Their CPU/device fixture results
are separate evidence; this note claims no measured speed.

The native IQ4_NL row is 20 blocks of 18 bytes. Each block starts with its
FP16 scale and stores low-nibble weights 0..15 and high-nibble weights 16..31
in the same sixteen code bytes. The bounding study's adjacent-nibble packing
is deliberately not copied. Both implementations use the original bytes.
The sixteen signed levels equal the original model format table.

For each lane, the active columns are `8*lane + 256*t`, then offsets 0..7.
The scale converts once for each active eight-weight lane tile. Eight divides
32, so no lane tile crosses a scale block. At K=640 lanes0..15 have a third
tile and lanes16..31 stop after two. The numerical expression remains
`value = scale * float(level); product = value * BF16(input); sum = sum + product`.
The SG32 sum tree uses widths1,2,4,8,16 followed by the same BF16 rounding.
Neither geometry uses a barrier, local memory, a scale/table broadcast or a
64-bit weight-loop index. Reduction shuffles are still required by the same
tree; they are not scale broadcasts. Native pointer addressing remains the
platform's pointer width. The largest full-bank source offset is below
472 million bytes, so unsigned32 source arithmetic does not overflow.

Every route has its own 640-element input; expert-down has one projection.
There is no gate/up-style shared-input matrix pair and no paired candidate.
The two work-group shapes alter only row ownership. CPU row parallelism
keeps each row's lane sums and output independent.

The R5 IQ4 branch already uses the same byte level table and converts a
block scale once in its metadata-owner lane. It does not convert the scale
once per weight, nor does its IQ4 branch require the generic IQ2 uint64 grid.
The proposed difference removes the scale-owner subgroup select, dynamic
shape/format paths, inactive-lane decoding and wide numerical loop indices.
Source alone does not establish which instructions survive compiler
optimization or whether this is faster.

Review findings sent to the implementation agent: preserve compact ten-expert
streaming banks as well as full512 banks, validate against the actual bank
extent, and retain fixed2560x640 shape for new-down K1 while limiting active
route rows for cheap CPU gates. Invalid/empty/partial route outputs and status
must remain byte checked. The parent owns complete runtime fixture validation.

`expert_down_review_test.cpp` independently compares new lane/tree/BF16 bytes
against R5 and scalar original-format decoding. It covers all16 levels,
signed zero, subnormals, extremes, infinities and signed NaNs without any
NaN-category tolerance. It returns failure for every unequal bit pattern.
Its executed receipts belong in the build evidence, not this source review.

The reviewed implementation now admits only bank sizes10 and512, binds the
actual bank size in both host and device operations, and checks every route
against that value before forming a weight address. K1 keeps the fixed down
shape with eight active rows, adds invalid expert and row-span routes, an
empty route, nonzero row starts, and the final expert511. Untimed checks read
and compare each projection's status as well as every output byte. These
source findings are resolved; executed gates remain the build's evidence.

The initial strict-special probe was executed by the parent. GCC passed all
72,360 comparisons; Intel's host compiler reported2,469 unequal bytes, with
mixed-NaN payload examples (`0xffc10000` versus `0xffc00000`). The full
exceptional-value diagnostic therefore failed and cannot be called exact.
The arithmetic was not changed or canonicalized in response.

The test now reports three exact relations separately: candidate versus R5,
candidate versus scalar-v2, and baseline R5 versus scalar-v2. It also labels
fixtures containing any nonfinite input or scale separately from finite
fixtures using IEEE exponent bits. Signed zero and subnormal values remain
in the finite gate. The enhanced test has110,160 comparisons, of which31,416
are supported finite comparisons. `passed` and process exit still report any
mismatch as a failure, even when `supported_finite_passed` is true. Separate
finite/nonfinite counts and hashes prevent compiler-dependent exceptional
payloads from disappearing into a category-equivalence pass. Fresh executed
receipts determine those counts; this source review does not infer a pass.
The streaming real-model eight-token v2 oracle remains mandatory.

Reviewed source hashes:

- `expert_down.hpp`: `eb327fb716344751870064c00c843ec3147219f996dfd89a8818c70fede03ffb`
- `expert_down.cpp`: `027dd4750e4d285b55dd83e4289c19bee59398fbe84ca54e63d139866e1451ba`
- `expert_down_review_test.cpp`: `61bf7f0ab1164e18cfb609a09cfd2010811087665cea0249d14cc904647ffdbb`

Packet29's final independent diagnostic reports 31,416 finite comparisons per
process, all exact in four processes (GNU/Intel, two each). Mixed nonfinite
inputs remain unqualified: Intel reports 1,254 candidate-versus-R5 and 1,254
candidate-versus-scalar differences; R5-versus-scalar has zero differences in
this diagnostic. GNU reports zero differences. No failure was relabeled equal
and no kernel arithmetic was changed. See `expert-down-review-gates.json`.
