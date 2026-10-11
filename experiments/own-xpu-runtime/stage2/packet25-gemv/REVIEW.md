# Independent review record

Three subagents reviewed the kernels/reference separately from implementation:
expert bit identity, dense bit identity, and cross-work-group writes/ownership.
[review.json](review.json) records the reviewed source hashes and fixes.

Expert review independently checked each candidate family against packets 7–10
and the frozen packet23 schedule, then authored `review_gates.hpp`. It found
the mixed-NaN propagation issue and required a real fallback call rather than
copying oracle bytes. Those initial failures remain evidence. Final assessment:
finite arithmetic is preserved; exceptional fixtures explicitly call current;
GPU current/reference and full-model gates remain mandatory.

Dense review found a non-constexpr predicate, malformed source quoting, and
unused out-of-allocation side-table pointer arithmetic. All were corrected.
It checked Q6/Q8 scale/product order, unequal split4 tile bounds, all rounding
points and each paired BF16 boundary. An optional SiLU diagnostic later exposed a
compiler-dependent NaN sign; reviewers approved retaining its failure separately
while keeping all GEMV fixtures unchanged and ending this gate at GEMV outputs. It required per-value exceptional
checks so a row-level NaN could not hide later errors. No static blocker remained.

Race review independently enumerated row/partial owners and scratch regions.
Every output belongs to one (group,row,part-zero,lane-zero) owner. Padded rows
still join barriers. Scratch is indexed by route slot, so duplicate expert IDs
only duplicate reads. Code, scale and metadata writers occupy disjoint ranges.
Paired allocations are distinct. The in-order queue serializes stage decode,
GEMV, repeated output writes and readback. A partially successful two-stage
submission is drained with a queue-wide wait, even if no tail was recorded.
It also required every phase's timestamp/budget checks and full-sequence receipt
hashes/coverage. These fixes are in the final sources.

The runner's mock tests were written with the race reviewer, then inspected by
the primary agent; this is not claimed as an independent review of its own code.
The static kernel race review remained independent. CPU compiler receipts and
real device validation are separate evidence, never inferred from this review.
