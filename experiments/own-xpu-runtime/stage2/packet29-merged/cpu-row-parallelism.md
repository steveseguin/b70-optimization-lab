# CPU-only row scheduling addendum

Two independent host loops now use `omp parallel for num_threads(2)
 schedule(static)`. This changes CPU fixture/oracle execution scheduling only;
no device code, arithmetic expression or device dispatch is changed.

In `p25bridge::Kernel::run`, the loop over complete output rows runs on at most
two host threads when there are at least 64 rows. Route validation and status
writes stay outside that parallel region. Each thread owns an entire output row
for both paired projections, with private accumulator arrays. It reads immutable
weights, the BF16/FP32 input vector and the already-selected route. Rows write
disjoint BF16 elements; validated writable-alias exclusions still apply. The
per-lane products, addition order, subgroup-equivalent tree, split tree and final
BF16 conversion are unchanged. Eight-row fixture cases remain serial.

In `round2::gdn_host`, the independent loop over 6,144 state/output rows uses two
threads. Each owns the complete 128-element recurrent state slice for its row
and processes tokens in original order within that row. Query/key inputs and
weights are read-only. State outputs and output activations have disjoint indices
across rows. Position and sticky-error checks stay before the parallel loop; no
thread writes shared status inside it. All temporary arrays are private to each
iteration. The pragma is compiled only with `OWN_RT_HOST_ONLY`, so the SYCL path
is unchanged.

This source review establishes the independence argument, not a measured speed
improvement. The parent rebuilds and reruns retained CPU gates. This agent did
not compile or execute a device binary for this change.
