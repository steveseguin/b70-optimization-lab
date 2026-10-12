# Resume-session independent controller review

Source review only; no binary or device executed. The accompanying JSON binds the inspected source hashes. Earlier gate receipts were not accepted as proof.

The native mailbox itself has no blocking concurrency finding: request and reply sequence stores publish their payloads with release/acquire ordering, one outstanding command prevents concurrent overwrite, and the shared futex checks its expected sequence atomically before sleep. A publication between predicate check and sleep causes EAGAIN, not a lost wakeup. Spurious wakes and interrupts recheck the predicate. Sleeps are at most 10 ms, every wait has a deadline, and there is no spin phase. Both queued and new command admission paths check cancellation and abort.

Normal native completion receives the worker exit acknowledgement before returning to socket supervision. Native exceptions publish abort before propagation. Both ranks observe the same unread stop pipe; parent death produces HUP. Request reset waits for both socket completion replies. The wrapper does not remove the shared mapping while either child is retained.

Two failure-path findings were fixed during this review:

1. `pipeline.py` calls the failure hook and writes failure receipts before notifying the stop pipe, without a finally path. A hook exception or ENOSPC can skip both notification and bounded cleanup. Attempt receipts first, then always notify and drain; retain the diagnostic-write error. Add an injected write-error regression.
2. `rank.hpp` writes failure files from its catch body before explicit provider and engine shutdown. `main.cpp::save` throws on stream failure. If recording fails, explicit ordered teardown is skipped. Protect diagnostic writes and continue owner shutdown even when storage is unavailable.

These are concrete storage-failure cases relevant to the session interruption, not claims that a device fault occurred. No earlier receipt or sanitizer pass is certified here. Source-level mailbox ordering is sound; device cancellation and owner-drain behavior still require coordinator windows.

## Fix verification

`Transport.stop` now protects diagnostic hook/write attempts, then always signals the shared stop pipe; a pipe-write error closes the writer to produce HUP. Ownership receipt errors are reported only after handles close. Both single-request and suite exception handlers attempt receipts before entering cooperative stop and bounded cleanup. The native rank catches failure-record write exceptions independently before explicit provider and engine teardown.

Three CPU-only mocked hook/ENOSPC cases passed in this session, including simultaneous hook and receipt failure. Each observed the stop byte, idempotent stop, and closed resources despite an ownership receipt write failure. See `review-resume-storage-gates.json`. Python sources parse. No native compile or device execution was performed by this reviewer; the C++ catch change still needs the parent's rebuild and normal host gates. No unresolved concurrency finding remains in the reviewed source.

## Device-wrapper preparation review

The fixture and concurrency-canary exception paths now protect receipt and fault-latch writes before cooperative notification and bounded drain. The watcher records a newly observed kernel-fault signature in memory before writing the log, so a failed log write cannot erase that observation. No device code was executed. Four mocked window regressions passed, covering these three failure cases and exact compressed evidence retention with deliberate corruption rejection.

Window storage admission reserves the projected raw plus compression peak: 1.1 GB for K1/K2, 32 MB for K0/W0p, and 550 MB for a model request plus 16 MB per retained suite request. The existing storage checker enforces 8 GB root free and packet build below 3 GB including that reserve. Each fixture launch checks again. Compression streams in 1 MB chunks; raw event/trace JSONL, process logs and fixture output.bin above 20 MB become gzip files only after exact round-trip hash verification. Fixture bytes must also match the native receipt hash. The window records original and compressed hashes; prerequisite verification checks both the compressed artifact and its original decompressed bytes. Any old evidence consuming the reserved capacity causes a clear refusal before device launch.

## Final source rereview after snapshot retention

The final `suite.py`, `native_mini_gate.py`, reset inventory and window sources were reread and their hashes refreshed. This step was source-only; actual native and suite reruns remain separate evidence owned by the parent. No blocking finding remains. Both reset socket replies complete before snapshot retention or shared-mailbox clearing. Retention cannot race with a native worker. It verifies runtime target hashes, retains exact metadata plus file hashes, and removes only finished state snapshots, keeping emitted-token fixtures. Any admission, compression or retention failure enters the protected cooperative shutdown path. The mini-model comparison consumes the archived state while continuing to compare tokens, guesses and counters directly.

The later mini-gate harness simplification was source-reviewed separately. An initial reset prepares case 0; one reset after each request captures that completed case and prepares the next. Its signature is read only after reset and archive completion, and only the completed case is removed. Eliminating the extra empty `between` request preserves one complete reset per request. This is not a runtime pass; the interrupted prior run cannot certify the exhaustive gate.

The final streaming `storage.py` revision was reread. Its source-bound synthetic export receipt parses, all five referenced source hashes match, and its six reported checks remain explicitly synthetic. Archive writing and verification use bounded chunks; exact text and nested gzip bytes are checked before scratch deletion. Existing `admit(extra)` callers keep the same budget behavior. This rereview ran no tests or ranks. The refreshed mock storage receipt was also parsed and its source hashes verified before updating its digest binding.

`storage.admit` now uses a single-pass size helper that ignores only vanished members during concurrent scratch cleanup. It does not retry or swallow permission/I/O errors. Three mock-only race checks passed, and all six synthetic export/retention checks were rerun against this final storage hash. No ranks or device executed.
