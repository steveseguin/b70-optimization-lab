# Packet 23 capture and failure-exit repair closeout

Question: can the fused packet fit the B70 kernel-argument limit and report a
first-build failure without silently parking? This was CPU-only preparation.
No device binary, Level Zero discovery, /dev/dri access or host-setting change ran.

W0 proves the original Chain kernel exceeded the 2,048-byte device ABI limit:
6,036 bytes in the compiler receipt. CPU compilation measures its closure at
6,056 bytes. The repair reduces it to 56; all 41 functor classes now fit within
224 bytes. The build wraps every kernel, enforces a 1,024-byte static limit,
and rejects an oversized negative control. See KERNEL-ARGUMENTS.md and the
verbatim W0 evidence. Host compilation still does not qualify the device JIT.

K1 attempt a's immediate exception remains unknown. Code proves the hiding
mechanism: compute sets fault_, old shutdown refuses all faults, and destruction
parks before the outer exception handler. No external retained SYCL borrower
was found in the fixture. CopyEngine contains only an owner reference. The
same Chain JIT error is a hypothesis, not a recovered error log. Original
coordinator evidence remains under evidence/20261011-k1a-nongemv-parked/.

Owners now report exception text, status, in-flight count and IDs, live bytes,
and registered borrowers before attempting bounded shutdown. Fixture output
rows and hashes are flushed before teardown; model timing rows are flushed on
success and failure. Known completed work can exit with failure status. If a
borrower or cleanup error prevents native destruction after zero in-flight work
is proven, the drained backend is retained until normal process exit; that is
a failure receipt with retained bytes, never successful clean teardown. A
pending/unknown event is explicitly listed before supervisor retention.
The CPU controls inject a first-build exception and a retained borrower, and
require failure.json plus a normal exit with code 1 within ten seconds.

K0 links the same kernel objects as all three native programs. It builds every
kernel for each admitted card in one process, without a queue, kernel execution
or explicit USM allocation. The wrapper binds its native receipt, boot, complete
binary set, environment and admitted cards before K1, W0 or any model window.
The next work is the coordinator's K0/K1a/K1b/W0/W2/W3/W2d sequence in WINDOW.md.
No device correctness, timing, clean exit or speed claim is promoted here.

Arithmetic/schedule bodies remain hash-identical to packet21. Changed adapter,
GEMV and Step storage code is explicitly recorded in carryover-proof.json and
host-plumbing.patch; the old 64-token/R5 and long sanitizer receipts retain
their original binary identities. Fresh three-position streaming and additional
eight-token v2 oracle receipts supplement, rather than relabel, that evidence.
See cpu-tests.json, real-eight.json and build-receipt.json for final counts,
identities and limits. Retain both coordinator evidence folders and original
build/k1a and build/w0. Revisit any failed device window only with new evidence
and coordinator admission; never skip K0 after a binary change.

Parameter-upload ordering is also checked: native backends assign compute event
IDs after the submission has finished preparing its tables. This keeps the
owner's event ledger sorted when preparation adds tracked copy events. One CPU
control checks metadata upload/cache reuse and the resulting event handle; the
queue source gate binds the check to both native backends. Earlier packets are
unchanged; the one-card backend change lives in the asserted local overlay.
