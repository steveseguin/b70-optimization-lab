# Recovery after disk exhaustion

The prior agent session ended near 04:59 UTC on October 12 when the root disk
filled. The coordinator incident record is
[DISK-CLEANUP-20261012.md](../DISK-CLEANUP-20261012.md).
This session began by checking the filesystem (28.34 GB available) and finding
6.8 GB of packet-local build output. Stale fixture and test scratch was hashed;
text evidence was compressed and verified before deletion. The build tree fell
to 1.7 GB. No other packet was changed.

The initial scan found empty interrupted mini-model receipts. No such receipt
is used for qualification. Existing target/draft inputs were hash checked;
GNU, Intel host, address/undefined-sanitized and device variants were rebuilt.
No device program was executed. ThreadSanitizer uses the successful LLVM CPU
runtime, without a host setting change.

Independent resumed reviews found that a receipt or journal write error could
bypass cooperative shutdown. Controller, rank and window failure paths now
attempt evidence first and still request bounded teardown if writing fails.
Injected full-disk, hook and stop-pipe failures are tested. Request-order proof
now covers standalone target scratch and host lookup state as well as plan
buffers, both recurrent banks, draft state, tokens and retained fixtures.

Final CPU results and any open coordinator-only checks are recorded in
CPU-RESULTS.md and build-receipt.json when qualification finishes.
