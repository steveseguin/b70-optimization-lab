# Independent non-GEMV review

Reviewer: small-GEMV implementation agent, reviewing a different agent's
non-GEMV code. Static CPU-only review; no device execution, discovery, or
performance claim. File hashes are in review-nongemv.json. The build and
fixture receipts, rather than this review, establish executed CPU coverage.

## Per-kernel arithmetic and ownership

- **GDN recurrence:** the existing ng::dot128 groups four contiguous products
  per logical lane, starting from +0, and reduces the 32 lane sums with the
  adjacent tree. The new private q/k/state arrays preserve exactly those four
  products and that accumulation order. lane_tree adds widths 1,2,4,8,16 only
  in the same parent lanes. The complete sum is broadcast after the last add.
  Normalization, decay, delta, state update, gated output, and BF16 state
  stores retain their original parentheses and rounding points. One subgroup
  owns one (head, output-row) state slice; slices never overlap. The per-token
  barrier precedes rereading BF16-rounded state, including in-place state.
- **QSA score:** same BF16 operands, 256-leaf adjacent tree, division and FP32
  store. Reducing the physical workgroup to 32 changes who fills scratch,
  not the arithmetic tree. Each head/slot has a unique output.
- **QSA softmax:** the maximum scan moved to one lane; its order and std::max
  predicate are unchanged. Scratch slot n stores the maximum and the
  budget+4 allocation includes it. Exponentials, adjacent denominator tree,
  and divisions are unchanged. Local barriers separate all scratch phases.
- **QSA value:** same selected-ID order, FP32 probability products,
  odd-padded adjacent tree, intermediate BF16 rounding, sigmoid product and
  final BF16 store. Each (head, value-coordinate) workgroup has one output.
  Invalid IDs are guarded before address formation. As in existing code,
  poisoned request state is a failure path, never a qualified model output.
- **QSA select:** each block independently computes the same four 128-product
  trees and accumulates head results in order. Division follows the fourth
  head. The strict greater-than / equal-and-lower-ID rank predicate preserves
  ties. Selected groups own disjoint four-ID ranges; block zero owns only
  the non-overlapping trailing raw IDs and -1 suffix. Nonfinite scores clear
  every ID to -1 before block zero reports failure; other blocks do not write.
- **Route:** the complete rounded softmax probabilities are retained before
  ranking. Early termination applies only once at least top entries outrank
  an item, so no winning ID or rounded-probability tie is changed. The selected
  probability sum keeps the adjacent top-width tree. Rank outputs are unique;
  separate launches order probability generation, selection and normalization.
- **Argmax:** independent lane scans and chunk winners use the same finite
  maximum and lowest-ID tie ordering. IDs below the one-million-element guard
  are exactly representable in FP32 scratch. Nonfinite input triggers the
  original 128-lane serial compatibility fallback before the sticky error,
  preserving that original winner-selection rule. Each chunk has one writer;
  the final pass has one output writer.

Every new non-GEMV device entry instantiates a compile-time operation. The
launch host switches to concrete templates. No device operation descriptor is
interpreted in an element/row loop. Shapes and request positions remain
bounded invocation data; these are not device-side kernel selection tables.

## Fixture repair

K2 moves the pool fixture to position63. The CPU reference recomputes previous
completed pools from the raw history; production kernels correctly retain
those previous pools. The repaired source seeds exactly the already-completed
prefix (15 blocks x128 BF16 elements) from the matching reference history.
It leaves the current sixteenth block untouched, so both implementations
must still calculate it. K1 also includes a position63 regression case.
The failure loop excludes only the failing implementation and continues the
remaining candidate/class work. It does not relaunch a failed server.

## Findings and resolutions

1. ADL made groups/local_floats calls ambiguous with ng helpers. Calls now
   explicitly qualify round2 helpers. This was observed in the first host
   compile before any device binary was run.
2. The first route argument guard required signed i32 even though the actual
   plan uses unsigned32 IDs/descriptors. Both integer representations now
   pass the bit-identical storage guard; logical top/top*3 lengths are checked.
3. The first select failure path left the selected-ID prefix stale. It now
   has block zero clear the entire output before reporting nonfinite failure.
4. The shared fixture driver initially passed output.bin where the small
   fixture API expected a directory. That call now receives the directory.
5. The folded route setup originally forced implementation1 after dispatch.
   This prevented selecting round2 for route+gather; the parent corrected the
   fusion selection override.
6. Requested explicit alias validation for round2 scratch and writable
   outputs, while allowing the documented GDN state input/output alias.
   These guards are now present: each operation declares its used read/write
   slots, scratch aliases are rejected, and only GDN slots5/7 may share state.

Device timing, native code generation, and bit identity on two fresh device
owners remain the coordinator's K0/K1/K2 gates. Static reasoning cannot replace
those measurements. Invalid-request output bytes are not used for quality or
speed promotion; valid fixtures and model outputs must match exactly.

## Final scheduled-ABI and CPU-row review

The simple-kernel entry now admits either compact ni1 or the real Builder ni3
ABI. The extra two inputs must be one-element u32 active/error controls and
must alias the canonical trailing control allocations. Output indices remain
relative to ni, and the kernel still reads its vector at binding0. This admits
the actual plan without weakening its shape, output-size, alias or memory
guards. K1 now exercises scheduled controls for16/512-expert routes, a folded
route/gather and argmax, plus the full248320-element argmax workload with
finite, tied and NaN inputs.

The CPU-only two-thread GDN loop parallelizes independent state rows. Each
iteration owns state[g*128:(g+1)*128] and output[r*6144+g]. Its q/k/v arrays
are block-local, all weights/inputs are read-only, and the token loop remains
serial within its row. The error guard occurs before the parallel region;
there are no concurrent error writes inside it. The implicit end-of-loop
barrier completes all rows before return. Neither products, trees nor rounding
points change, including in-place state. The native device body is unchanged.

Fixture-driver stage_count is the complete collected arm event count,
including all three QSA attention phases. Every adapter timing class currently
contains one folded or ordinary site, so its launch event count is also the
complete arm count. Small-tuple baseline counts include all sibling launches;
FP32-input GEMV timing includes the preparation launch. The extra receipt
counts report actual source, adapter, GEMV and tuple coverage separately.
