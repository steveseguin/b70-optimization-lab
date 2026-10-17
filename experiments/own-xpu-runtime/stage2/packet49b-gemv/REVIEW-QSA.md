> Historical packet49 review copied as design context. It does not qualify packet49b. See REVIEW-INDEPENDENT.md for the new review.

# Independent QSA integration review

The oracle author reviewed the independently implemented production bridge,
scalar reference, snapshot extent and K1 admission on October 17, 2026.
This is source review; device qualification remains with the coordinator.

- `p49_qsa_submit.cpp` sends the admitted owner bindings through the packet47
  admit, fixed32 tile and combine stages with explicit dependency ordering.
  Its host implementation uses packet47's independent scalar reference.
- Scratch has 16 bytes for counts followed by
  `M * 24 * ceil(selected_capacity / 32) * 258` floats. The owner checks every
  binding's lifetime/extent, scratch alignment, scratch aliases and output
  aliases before submitting work.
- The production `core_v2.hpp` fallback independently uses padded32 local
  reductions, local maxima, corrected partials and the final adjacent tree.
  BF16 rounding occurs before the unchanged sigmoid gate and at the output.
  Miniature geometry retains its historical arithmetic and does not establish
  production arithmetic correctness.
- `strict_snapshot.hpp` now accounts for all production QSA scratch writes.
  The production adapter uses one-row attention for each verification row,
  as packet45 did. Therefore its write-set bound is M=1. This does not batch
  the engine's two verification attention rows; the standalone bridge fixture
  separately exercises genuine M=2 buffers and causal positions.
- `p49_qsa_fixture.cpp` checks 88 owner-level cases including both row counts,
  split tails, contexts through4096, disabled execution and pre-existing errors.
  K1a/K1b require the bridge binary identity and exact output bytes. Actual
  device success cannot be inferred from host fixture success.

No blocking arithmetic, extent or ordering defect was found in these reviewed
paths. The new full-model oracle, fresh device K1 windows, full model fixture
windows, rollback checks and fresh-process repetitions are still required.
