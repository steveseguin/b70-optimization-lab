# Independent native concurrency review

The suite subagent reviewed the native controller separately from its author.
An already queued command could previously bypass the abort check. The native
author found this edge after the first review; the independent rereview confirms
the fix described below. No unresolved blocking finding remains in this source.
This is a source review; the separate sanitizer receipts state their actual
execution outcome.

The mailbox has one producer and one consumer. Rank 0 writes the request payload
before a release-store of its request sequence. Rank 1 acquire-loads the sequence
before copying the payload. The reply uses the reverse release/acquire edge.
Rank 0 may overwrite a request only after the matching reply; rank 1 may overwrite
a reply only after another request. This also protects the shared stream and MTP
publication bytes. Each rank owns its model state and candidate; rank 1 never
mutates rank 0's state. The shared words are aligned 32-bit integers and GCC atomic
builtins are lock-free on the explicitly supported Linux x86_64 host. They do not
construct `std::atomic` objects inside a Python-owned mapping.

Futex operations are process-shared (no PRIVATE flag). The waiter checks the
sequence, then sleeps only if it still equals the expected old value. A release
between check and sleep produces EAGAIN, so the wake cannot be lost. Wakeups are
hints; the sequence predicate is checked again. EINTR and spurious wakes do not
complete a command. Ten-millisecond timed sleeps bound cancellation checks;
there is no spin phase. Command waits also have absolute deadlines.

Any native-loop exception sets the abort word and wakes both futex directions
before it propagates to the rank failure receipt and teardown. The supervising
wrapper polls rank liveness, stop request and its own absolute deadline while
waiting for the socket completion replies. A crashed peer cannot strand its
partner indefinitely. Stop uses the existing cooperative pipe and bounded drain;
no retry or forced process-group kill is introduced.

Normal completion sends an acknowledged op-0 worker exit before returning to the
socket command loop. An early EOS first waits for and rolls back an outstanding
rank-0 speculative candidate. Native exit requires no pending draft. Suite reset
occurs only after both socket replies: both ranks have returned to command wait,
so clearing the shared bytes cannot race with mailbox accesses. Each reset command
itself drains the owner before changing state; request sequences on the socket
remain monotonic while native mailbox counters start from zero per request.

Real-process device fault behaviour and the platform's device backend require
the coordinator's windows. No device was touched by this review.

## Queued-command abort admission fix

The previous worker checked cancellation through `wait_change` only when it had
to sleep. If a request sequence was already advanced, it could execute that
queued command despite an already published abort. `Backend::start` also checked
the external stop callback but not the mailbox abort flag before local work.
The updated worker checks both stop and abort on every admission path, including
already queued requests; `Backend::start` does the same before either local
execution or remote publication.

The fifth case in `native_mailbox_fault_test.cpp` publishes a request, publishes
abort, then enters the worker and asserts the execution callback never ran. It
also tries local dispatch on the aborted mailbox and asserts no callback. This
independent source rereview verifies that the test reaches the formerly skipped
branch. A concurrent abort after admission still uses the ordinary cooperative
in-flight cancellation and bounded teardown; the test does not claim an atomic
transaction between fault publication and a kernel already admitted.

This admission fix does not change the emitted-token authority: only a confirmed
rank-1 target result may be emitted, and subsequent ACCEPT dispatch also passes
the new cancellation guard. The updated suite reset evidence and standalone
mailbox regression receipts bind the final executable separately.
