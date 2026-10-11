# Independent bridge review

Reviewer: dense-family implementation agent. CPU-only source inspection;
no device binary, discovery, or device files were used.

Compared `submit.cpp` with packet26 `performance.cpp`, packet9's routed
`Projection`, packet10's expanded `Multiply`, packet8's raw constant-decode
path, and packet26 `owner.cpp`'s dependency handling.

## Geometry and arithmetic

For the four-row variant with split=4, a work-group has 512 threads: sixteen
SG32 subgroups, four consecutive subgroups per row. The logical index divides
by four, the split index takes the remainder, and the local partial index is
`(row_in_group*2 + output)*4 + part`. Its maximum is 27 for dense-only
output, or 31 for paired outputs (the allocation reserves 32 floats). Every active row has all four
subgroups, including when the matrix has an odd number of rows. Inactive
subgroups reach the barrier and never read unwritten partials.

For the single-subgroup variant with split=4, four separate work-groups write
four FP32 partials per row. `Finish` computes exactly
`(p0+p1)+(p2+p3)` and only then rounds to BF16. The packet26 owner appends
the previous event to every compute's dependencies, so the second submission
cannot read unfinished scratch despite the caller's empty explicit dependency
span. Both submissions must be included in the candidate's timing.

At split=1, the four-row variant has WG128 and the one-row variant has WG32.
Both keep eight contiguous weights per lane, 256 columns between tiles,
the adjacent-pair 32-lane tree, and the original BF16 output rounding.

Raw F32 and BF16 use the same per-element `decode` as the current packet6/
packet8 path. BF16 weight NaNs retain the original quieting conversion;
BF16 inputs retain the original bit expansion without an added conversion.
These classes have no expanded scale-load saving. Their per-weight work is
unchanged: F32 four byte loads and three byte-assembly operations; BF16 two
byte loads, one byte assembly, left shift, and the existing NaN-quieting test;
both have one input expansion, one product and one accumulation. Any speed
change must come from geometry and dispatch specialization, measured on card.

## Routes, arguments, and limits

Route validity has the same expert/range/count predicates as packet9. Invalid
routes write the same canonical NaN and set status. Valid short routes compute
only rows below `row_count`, and source rows include `row_begin` exactly once.
The bridge checks the paired matrices share shape, format, x and route bindings.
Inactive final IQ4 lanes do not load x; the lane source supplies safe weight
addresses while retaining subgroup participation.

The submitted kernel captures one small `Bound` value plus a local accessor;
the checked wrapper statically rejects captures over 1,024 bytes. `Bound`
contains direct pointers and scalar geometry, not a descriptor table. Native
64-bit addressing occurs while selecting a matrix row. Weight-loop code uses
32-bit integer indices and byte table/scale loads, without 64-bit grid words.

One concrete defect was reported to the harness author and fixed: validation initially
performed `columns % layout(type).elements` before rejecting an unknown type,
which could divide by zero. Explicit compiled-type admission now precedes that
expression, including rejection of unsupported IQ3_XXS, whose device submit
switch has no entry.

This review does not establish device exactness, subgroup support, or WG512
admission. Those remain K0/G2 checks. Host NaN encoding discrepancies remain
recorded separately and cannot waive same-card candidate/current byte equality.

## G2 harness review

The harness calls packet26's actual `integrated::dense` and
`integrated::experts` dispatch entries with the production R5 variant. It does
not substitute a copied implementation for the timing baseline. Native
candidate/current comparisons require byte equality; only current/host permits
both-NaN equivalence. The CPU-only fixture mode explicitly relaxes NaN payload
matching, retaining a separate `new_current_bytes_equal` diagnostic.

Correctness uploads and output reads occur outside the timing loop. Each
candidate gets 200 GPU-event samples; split single-subgroup candidates report
both the dot kernel and the finishing kernel. Host reference timing is not
used as GPU time. A failing exactness candidate is excluded while the other
candidates continue. Real device submission faults abort rather than trying
to continue on a faulted owner.

Three fixture weaknesses were reported and their fixes verified in source: all routes were valid
and full length, status outputs were not compared, and existing baseline
outputs were not poisoned before a candidate (so a missing output write could
pass). A dedicated route fixture with invalid, empty, shifted and short routes,
plus output/status poisoning before correctness submissions, now addresses these.
The initial eight-row repeated weight seed also made every production expert
bank identical because 640 and 2560 are divisible by eight. A seventeen-row
seed now distinguishes banks while retaining bounded tiled uploads. Mode 5
checks expert ID 512, row_begin beyond the row extent, excessive row_count,
an empty valid route, and a shifted short valid route. Both the current and
candidate status buffers are compared to independently constructed route
validity values after being poisoned with `0xcdcdcdcd`.

K0's final path only builds the executable SYCL kernel bundle for the selected
card, requires a nonempty kernel-ID set and verifies every ID is available.
It submits no kernels. The host fixture mode separately runs odd nine-row
matrices; G2 retains the complete production shapes.

The summary initially asserted 200 samples for every candidate. It now
excludes incomplete candidates; an incomplete baseline keeps its class
ineligible. Every retained repetition additionally requires the complete set
of one or two constituent events, so a missing split-finishing event cannot
make a candidate appear faster. This is independent of the exactness
candidate continuation already present in G2.

## Final compile-time specialization delta

Re-read the final `Kernel<Type,K,Split,RowsPerGroup,Shared,Paired>` bridge
against packet26's current dispatch and the packet9/10 reductions. `Split`
is now a template argument restricted to 1 or 4; routed kernels statically
require 1. Dense variants 4 and 7 select split4, while 0 and 6 select split1,
unchanged from R5. The work-group formula, logical row and split index,
partial storage, and finishing expression are the same equations reviewed
above with a compile-time split value.

`OutputPair` is true exactly for IQ2_S and IQ3_S. Host admission now requires
two matrices and shared x for those types, and one matrix with per-slot x for
IQ4_NL. Dense inputs remain one matrix/one vector. Thus removing the runtime
paired flag cannot drop an output or change an input offset on an admitted
call. Private/shared gate-up arms still compute two independent lane sums;
the paired arm shares each input load while preserving both sums' order.
Both outputs keep separate lane trees, status writes, and BF16 rounding.

The single-subgroup split4 finish is now templated on the output cardinality;
only dense single-output instantiations can reach it because expert Split=1
is enforced statically. The capture remains direct pointers plus scalar row
geometry, with no descriptor table or 64-bit grid-word path introduced.
SG32 and the selected WG size are now checked before submission.

No new arithmetic, route-tail, output-cardinality, or reduction defect was
found in this final source delta. This review did not compile or execute it;
the rebuilt host and pending device gates are still required.
