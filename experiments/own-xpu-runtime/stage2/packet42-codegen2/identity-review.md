# Independent source identity review

Reviewer: root agent; expert and tiny implementations authored by separate agents.
No device execution. CPU compiler evidence remains a gate, not a substitute for device bytes.

## Expert families

Reviewed `expert_candidates.hpp` and `expert_submit.cpp` against packet28 decode8,
packet33 candidates and the packet29 route/shape validation. Both projections
retain their own weights, share only activation bytes and address calculations,
and keep eight ordered multiply/add steps per lane and the explicit adjacent
32-lane reduction. Packed table words are little-endian byte regroupings.
Finite signed table magnitudes fit exactly in FP32, so multiplication with the
signed integer preserves finite sign and rounding; exceptional scales use the
original magnitude-then-sign order. IQ4 vector loads cover complete eight-byte
code and sixteen-byte input tiles; the K640 loop prevents inactive tail lanes
from reading past input. The scalar odd-length host fallback is separately
tested and does not execute the device vector branch.

No new barrier or local storage. `p28::checked` guards actual closures, and row
extent is validated before conversion to uint32. Invalid/partial route outputs
and statuses retain their exact sentinel bytes. The native timing harness calls
the incumbent through p28/p33 Device submission and checks against the unchanged
registered CPU arithmetic, not a handwritten substitute. Nonfinite GEMV
reference mismatches stay outside packet29 qualification, visibly recorded.

## Tiny families

Review of `tiny_core.hpp` confirms that activation, mixture, MoE and
convolution leaves retain the original operations verbatim, including the BF16
rounding before MoE addition, convolution dilation-specific rounding, serial
expert sum and shift-register update. Only global element mapping changes.
The old inactive/sticky-error/position checks remain. Cooperative width changes
retain each explicit tree node and add +0 for the same missing odd-tail partner;
iteration order across independent nodes is not a floating-point reassociation.
Final tiny CPU gates pass 240 fixtures and 720 geometry comparisons per process,
with two fresh processes under each host compiler. Intel host compilation needs
strict floating-point mode to match the reference NaN payload; the original
non-strict failure is retained. Device flags remain unchanged, so device byte
equality remains mandatory.

## Parallel families

Independently reviewed by the expert agent in `expert-review-parallel.md`.
Findings concerning direct helper coverage, native argument validation and
failed case exclusion were fixed and rechecked. Production route is reviewed
separately in `extras-review-route42.md`; the generic route_gather diagnostic
is excluded from production route dispatch. Complementary tiny families are
reviewed in `expert-review-extras.md`.

## Final cooperative specialization review

The root reviewer ran `tiny_source_gate.py` independently: PASS. It extracts
`ng::group` from the unchanged packet29 header and verifies the complete copied
body byte-for-byte after only template-function naming, `s.op` → `Code`,
`if constexpr` dispatch, and explicit `ng::select` qualification. Arithmetic
statements, tree nodes, barriers, and stores are unchanged. The CPU candidate
now invokes that same specialized body; final native GEN is checked separately.
This replaces the earlier host-only assignment of a captured op field, which
did not remove the monolithic device switch.

The final convolution alias review confirms `p4=p1` for history in all three
CPU paths and both native arms. Upload skips duplicate output slot4, restores
input history before each arm, and snapshots/compares the mutated input bytes.
Only the in-place production fixture contributes gdn.conv timing. The public
tiny submission overload now forwards its dependency span to Device.compute.
