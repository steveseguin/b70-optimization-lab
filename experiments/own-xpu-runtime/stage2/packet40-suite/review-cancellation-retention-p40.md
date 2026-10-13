# Independent cancellation and retention review

Reviewed by the draft implementation agent, not the cancellation author.

The initial cancellation check was at plan sites. A site can issue more than one kernel. This was fixed before sealing: the owner now checks before each compute/issue submission, and records the submitted prefix as the drain tail. A cancellation is outside the backend fault catch and cannot set the device fault state.

A cancelled prefix drains before rollback. It has not swapped temporal state banks; rollback therefore leaves the old active bank selected. A completed speculative half records its swap, so rollback exchanges it back. Strict image restoration now restores the complete saved write set before the confirmed redo, which is subject to the same exact-output gate.

Only rank 1 publishes target verification, after checking its error and reading its final token. Position-bound release/acquire publication rejects old values. The controller does not issue the following rank 1 half before the previous rank 0 transaction is resolved, so the shared token cannot be overwritten during its reader's matching generation.

Fixture retention reads target streams through ordered copies into separate snapshot storage. It changes neither a target binding nor arithmetic. The snapshot buffer is returned to zero after extraction, giving on/off runs the same scratch bytes. Cancellation and retention still require the runtime gate receipts; this review does not claim a device run.

## Historical follow-up: terminal EOS finding

A read-only follow-up found that rollback does not restore the rank0 `token` input buffer to its pre-speculation value. It restores position and histories, but `half_step` has already written the guessed token before the first cancellable compute launch. Rollback also clears lookup/FP32 cache metadata rather than restoring its prior state; speculative layer-streaming routing can remain in `selected`. The terminal committed-state comparison omits these fields, so it cannot establish token-control/cache-metadata equality. These are additional explicit limitations beyond inactive banks, scratch and invalid QSA tails. They do not make a draft guess authoritative for emission.

That finding was open at the time of the follow-up; its original text is retained here and in the archived review. The strict image subsequently resolved it. The image was authored by draft_runtime and independently reviewed by cancel_runtime, as recorded in [review-p40-strict-rollback.json](review-p40-strict-rollback.json). No owner exception was assumed.

## Current strict-image resolution and CPU evidence

The image captures before guessed-token upload or host preparation. After draining the issued prefix and undoing any completed bank swap, it restores all mutable write-set bytes, token/history/position, exact routing/cache metadata and the rank0 producer slot. Active committed banks and valid QSA prefixes are deliberately excluded from restoration, so corruption there remains detectable. Only private backup storage is cleared at resolved request boundaries.

Current evidence contains 207 ordinary cancellation/retention gates (101 native mini, 101 Python mini, five full original-prompt real cases), 204 complete-inventory forced-miss comparisons, eight long-retention comparisons across 12 requests, and 28 asynchronous-draft cases. The separate strict terminal proof has 472 gates: 408 mini and 64 production-weight diagnostic cases, including 12 actual committed-state corruption negatives. Its real workload is seven original prompt tokens with zero or one verified generated token appended; it is not full-prompt or speed evidence. Only scheduling telemetry is excluded from equality, with raw counters and hashes retained.

The source and receipt hashes in the JSON bind this follow-up. The original cancellation/retention reviewer completed the final peer signoff below; the strict image has its separately attributed independent review. Device event ordering, kernel parity and speed remain coordinator windows.

## Final original-cancellation peer signoff

The draft-runtime reviewer independently reread the cancellation/retention code
written by the cancellation agent. The review covers both actual compute and
prepared issue boundaries, callback cleanup on all loop exits, tracking the
last submitted event through partial multi-pass sites, drain and sticky-error
checks, conditional bank swap-back, target-only sequence-bound verification,
and retention's read-only source copies plus dedicated snapshot cleanup.
The native controller resolves the preceding speculative rank0 transaction
before issuing the next rank1 target half; publication remains stable during
the matching reader generation. Only checked rank1 target results authorize
emitted tokens. No unresolved finding was found in this scope.

All source and execution-receipt bindings listed in the JSON were checked
against the current files. The reviewer launched no tests, compilers, owners or
devices. Runtime evidence retains its separately declared mini/full-prompt/
short-prefix scopes and excludes only scheduling telemetry from equality.
The strict image was implemented by this reviewer, so its correctness review
is explicitly delegated to the separately attributed cancellation-agent peer
review; this signoff does not call that self-review independent.

The draft-runtime reviewer also independently reviewed the cancellation agent's
`audit_rollback.py` and `test_audit_rollback.py` source changes. All 1,015 plan
buffers remain classified, and the six QSA sites' row geometry reconciles the
319,074,840-byte private capacity with 318,976,536 bytes per direction at
position7 and 318,961,176 at position8. The 65,536-byte shared-slot host copy is
separate. Whole-archive identity and selected-member byte/hash authentication
precede accounting; plan equality and snapshot counters/retirement flags bind
the examples. The provided eight focused tests are current; none were rerun by
this reviewer. Byte accounting is not measured device cost.

Final CPU follow-up: all five GNU native modes now match their current Python receipts on eight tokens, 384 fixtures and complete compared final state per mode. The seven-receipt `real-native` qualification ledger passed, as did both comparison and rollback-audit child ledgers. This is additional runtime evidence; independent source-review attribution is unchanged. Only coordinator device qualification and measured copy/overlap/speed cost remain pending.
