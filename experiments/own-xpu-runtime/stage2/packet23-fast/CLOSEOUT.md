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


## r3 copy-per-launch closure (CPU only)

Question: can the fused, exact schedule submit without a queue copy at each
kernel? Identity: v2 arithmetic, unchanged weights, resident two-card plan and
frozen/R5 dispatch; this change is parameter storage and byte transport only.

The r2 run's exact output and 4,445 ms/token are preserved in
[evidence](evidence/20261011-w2-exact-but-slow-param-memcpy/README.md). Its profile
shows `appendUSMMemcpy` yielding while prior queue work finishes. r3 performs a
preparation pass, uploads immutable parameter tables, and rejects cache misses
inside resident decode. Token and lookup inputs are batched, and device byte
moves use kernels. The mock enforces two queue copies per card/token. The
arithmetic schedule remains 876 launches; capture byte moves add 64.

Retained mechanisms: pointer-only large captures, parameter CPU byte verification,
per-card copy assertions, the static copy-source check, explicit byte-move counts,
K0 guard, unchanged arithmetic bodies, and actual native-priority receipts.
[PORT.md](PORT.md) is the handoff for packet 24, which this task did not modify.

No r3 device code ran and no speed claim follows from CPU counts. The coordinator
must rerun the seven fresh `-r3` windows. GPU correctness, adapter behavior and
native-child priority on a real window remain unmeasured here. One-card CPU
weight-streaming and checked localization are outside the resident copy budget.

Fresh r3 CPU closure: 78 integration cases, 16 randomized mini runs, 104 randomized
integration cases, eight GNU/Intel fixture processes, 79 sanitizer controls, seven
lifetime controls, three entry-exit checks and 63 window tests passed. The exact
final host binary passed the full-prompt eight-token v2 oracle: 8/8 tokens and
384/384 layer hashes. Copy counts and their old-mock limitation are retained in
[copy-budget-summary.json](copy-budget-summary.json); all final identities and
source hashes are in [build-receipt.json](build-receipt.json). New device windows
are the revisit condition; no performance verdict is inferred from these gates.
