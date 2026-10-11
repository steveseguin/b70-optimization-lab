# Independent write-race review

Reviewed the new kernels directly alongside the reference core, adapter and submission code. The reviewer implemented the owner/host path, not the specialised kernels. Exact source hashes are in [review-races.json](review-races.json). No device was opened or run.

No conflicting semantic output writers were found. Each reduction writes disjoint subtree partials; the upper tree starts in a later ordered submission. Stable rank uses the original index to break ties, so equal route and selection values still have unique output owners. GDN assigns an entire recurrent state row to one work-item and loops over tokens within that owner. In-place combine/norm reads only the output coordinates owned by that work-item after the partial-sum stage has completed. Pooling reads older cached rows or current input rows, never the cache region being concurrently appended.

The sticky error is atomic on device. A failure can leave internal scratch partially populated in schedule-dependent order; scratch is not a semantic output. Subsequent stages see the sticky failure and leave semantic outputs unchanged. Standalone gather explicitly delays raising the failure until descriptor and data initialization is complete. Argmax writes its deterministic error-path result before setting failure.

These statements assume the registered plan bindings. Arbitrary new alias combinations are not admitted. Static review does not replace two fresh-owner K1 runs, randomized CPU ordering, or the same-run old/new byte comparisons in K2.


Final source-only refresh also covers the late streams broadcast, PLE-add kernels,
fixed model-shape template instantiations, and packet25 bridge. Broadcast owns one
output coordinate per work-item and reads an immutable source row. PLE add reads
and writes only its own index, so the registered in-place streams output introduces
no cross-item dependence. Fixed-width and fixed-head instantiations are selected
only after the host shape matches and preserve the same output partitions.

The bridge assigns one local partial to each (subgroup row, projection, split)
coordinate. Lane zero writes that partial; a workgroup barrier precedes the
part-zero final reduction. Only lane zero of split zero writes a given global
output coordinate, and only row zero writes that route's status. Both predicates
are subgroup-uniform. This agrees with the separate final admission and identity
review in [review-bridge-addendum.md](review-bridge-addendum.md), which was written
by the windows subagent. The refreshed JSON binds the exact final files inspected.

This refresh executed no device, ran no additional tests, and changed no runtime
source. It found no new write-race blocker for the registered bindings. It does not
qualify arbitrary aliasing, nonfinite GEMV diagnostics, or hardware behavior.
