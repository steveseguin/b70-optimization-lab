# Final independent bridge review

Reviewer: windows subagent, independent of the kernel author. This addendum covers
the late packet25 bridge and its final admission fixes. It does not attribute these
changes to the earlier race reviewer. The exact source hashes are in
[bit-identity-review.json](bit-identity-review.json). No device ran.

`Kernel<Type,Variant>` is a separate template instance for each linked type and
candidate. Candidate names are resolved on the host. The kernel never loops over
operation descriptors, reads a hot parameter block through a pointer, or switches
quantization type at runtime. Its `Bound` is captured by value, alongside the SYCL
local accessor. The mechanical kernel wrapper must compile the capture-size
assertion on this final source; this review does not substitute an estimated size
for that build check. The pointers in `Bound` name actual model tensors and route
records, which are ordinary kernel input data.

Write ranges are disjoint. Let R be rows per workgroup and S the split count.
Local scratch has 2*R*S floats. Subgroup row rr, projection p and split s write
`(2*rr+p)*S+s`, whose maximum is 2*R*S-1. Only lane0 writes that slot. The local
size supplies exactly R*S subgroups, so every partial that part0 reads has a
writer. A workgroup barrier separates those writes from the final reads. Lane0
of part0 alone writes each output coordinate `slot*rows+row`. Different workgroups
own different coordinates. Only row0 writes each route status; count 1 routing is
preserved by the explicit `has_routes` flag. Route validity and active-row bounds
are uniform within each subgroup, so subgroup collectives are not divergent.

The host checks positive bounded geometry, complete quantization blocks, matching
paired types/shapes/expert counts/input allocations/routes, supported row span,
and every weight/input/output/status extent before submission. A valid route
bounds source rows within the expert table. Input indexing is either one shared
row or slot*columns; both extents are checked. Output and status indexing stay
inside count*rows and count respectively. Final admission permits exactly R5's
packed expert variant 2 and expanded dense variants 6/7; unsupported split identities
cannot silently use the bridge's split 1 tree.

Arithmetic remains eight sequential products per lane, adjacent tree32 and,
when selected, `(p0+p1)+(p2+p3)`. The review repaired routing-count, paired-binding,
block-alignment and variant-admission issues; it did not alter those arithmetic
bodies. K1 checks four finite modes for every GEMV workload, both with and without a
requested candidate. Nonfinite GEMV inputs remain unqualified, as recorded below. A candidate that changes
any tested byte fails K1 and cannot generate a measured deployment choice. K2
still measures only the registered finite decode workloads, 200 repetitions per
arm, and uses the requested candidate's actual linked implementation name.

Later fixture-scope correction: the optional mixed-nonfinite GEMV diagnostic exposed NaN-sign disagreement in the unchanged baseline. [NONFINITE-GEMV.md](NONFINITE-GEMV.md) records the rejected diagnostic. The bridge and its reviewed arithmetic/write ranges are unchanged; final K1 uses four finite modes with strict byte equality. Required NaN-route coverage is unchanged.
