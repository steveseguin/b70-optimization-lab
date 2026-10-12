# Independent cancellation and retention review

Reviewed by the draft implementation agent, not the cancellation author.

The initial cancellation check was at plan sites. A site can issue more than one kernel. This was fixed before sealing: the owner now checks before each compute/issue submission, and records the submitted prefix as the drain tail. A cancellation is outside the backend fault catch and cannot set the device fault state.

A cancelled prefix drains before rollback. It has not swapped temporal state banks; rollback therefore leaves the old active bank selected. A completed speculative half records its swap, so rollback exchanges it back. The confirmed redo overwrites its cache row and scratch, restores the official token history, and is subject to the same exact-output gate.

Only rank 1 publishes target verification, after checking its error and reading its final token. Position-bound release/acquire publication rejects old values. The controller does not issue the following rank 1 half before the previous rank 0 transaction is resolved, so the shared token cannot be overwritten during its reader's matching generation.

Fixture retention reads target streams through ordered copies into separate snapshot storage. It changes neither a target binding nor arithmetic. The snapshot buffer is returned to zero after extraction, giving on/off runs the same scratch bytes. Cancellation and retention still require the runtime gate receipts; this review does not claim a device run.

## Follow-up: terminal EOS remains open

A read-only follow-up found that rollback does not restore the rank0 `token` input buffer to its pre-speculation value. It restores position and histories, but `half_step` has already written the guessed token before the first cancellable compute launch. Rollback also clears lookup/FP32 cache metadata rather than restoring its prior state; speculative layer-streaming routing can remain in `selected`. The terminal committed-state comparison omits these fields, so it cannot establish token-control/cache-metadata equality. These are additional explicit limitations beyond inactive banks, scratch and invalid QSA tails. They do not make a draft guess authoritative for emission.

The strict all-state review is therefore open. Previous findings and successful nonterminal redo/retention gate results are preserved below their original scope; no universal terminal byte-equivalence claim is accepted. Read [EOS-STATE-SCOPE.md](EOS-STATE-SCOPE.md) for the current boundary and proposed remedies. No runtime sources changed in this follow-up.
