# Ownership and bounded teardown

Each native rank owns one `ownrt::Device`, one single-device SYCL context and
one queue. All allocation labels use local card0; the physical index is selected
only when constructing that process's backend. Neither integer handles nor
SYCL objects cross the process boundary. The old shared-context backend is not
included by this runtime's main translation unit.

The producer drains its local queue before D2H readback and shared-slot
publication. A socket reply orders publication before the coordinator copies
the bytes; the consumer command orders that copy before upload. Only one
command per rank may be outstanding. The coordinator cannot overwrite a busy
consumer slot. Sequence numbers reject duplicate/reordered commands.

Sockets handle partial frames, EOF, EINTR and bounded waits. The stop pipe is
polled without consuming its byte, so both ranks observe one stop request.
Pipe HUP also stops ranks when the coordinator disappears. Loading and idle
ranks poll this channel; no rank is signalled. Native fixture entry points use
the same kind of pipe at owner admission. A K0 JIT already inside the driver
cannot be interrupted by this pipe; the wrapper retains/reports it on expiry.

Failure receipts are written before cooperative stop/drain. A boot fault marker
is written only after a child has launched. Admission/loader refusals cannot
write it; reviewed historical journal lines are never treated as new faults.
The wrapper takes its own journal cursor before work and considers only later
lines during work, drain and postflight. No retry, reset, hard kill, process group kill, or power/host setting
change exists here. The wrapper watches kernel fault signatures during load,
work, drain and postflight. A failed rank stops its peer through the one stop
pipe. A loading rank is never signalled.

Successful finish marks expected process exits before sending FINISH to either
rank, so an early clean exit is not mistaken for peer failure. It requires one
complete teardown receipt per rank, zero live bytes and zero in-flight work.
Shutdown remains owner-controlled: quiesce → drain → graphs → allocations →
idle marker → events → queue → SYCL context → native context. No kernel bundle
or other SYCL borrower survives context release. The tiny canary keeps all
copy/operation objects inside the work scope before shutdown.

A failed local drain writes retained-owner.json and parks with its owner alive.
The coordinator's 65-second drain wait records retained PIDs and leaves their
backing shared file intact. It does not force exit. The indefinite *retention*
is deliberate ownership preservation, not an unbounded work/hand-over wait.
Only the coordinator can decide what to do with retained ownership.

Host lifetime controls, process-stub fault/EOF tests, actual native-host rank
failure/stall tests, and ASan/UBSan gates cover this protocol. They cannot prove
driver internals or clean device exit; W0p is required before full-size concurrent
model work. No C++ controller threads are introduced, so no new threaded owner
path or TSan qualification is claimed.

## Prepared command lifetime

Each rank captures its own commands after allocation/upload and before READY.
Rank 0 captures both recurrent/conv buffer parities; rank 1 captures one set.
Prepared commands own their operation or native command-group value, binding
IDs, resolved pointers and owner generation. No pointer to a temporary operation
or a temporary binding span is retained. Every device functor remains bounded
by the 1,024-byte argument guard.

`Device::issue` rejects a different owner, a changed generation or a quiescing,
faulted or closed owner. Releasing any allocation advances the generation before
freeing it; explicit invalidation refuses pending work. Generations are unique
across owner reconstruction, including reconstruction at the same address.
Unrelated allocation does not invalidate still-live pointers. Native callbacks
borrow only that live owner's queue/event/error storage. Engine destruction
releases captured command vectors before its `devices` field; shutdown closes
admission before resources can disappear. No callback is invoked after shutdown.

The single-device backend keeps an in-order queue. Unprepared dependency IDs
are still checked for ownership; redundant same-queue dependency lists are
omitted. Prepared callbacks use the same queue and fail closed when the owner
or native event capacity is exhausted. There are no cross-rank events or queues.
Speculation/rollback changes only which previously captured vector is selected.

The normal prepared issue path uses cached booleans/class indices, a direct
callback and pre-reserved event ledgers. The rank loop uses cached layer/skip
metadata and a fixed 48-entry snapshot index array. The device accessor throws
only on failure: it does not construct a temporary `std::string` on every call.
The independent source guard covers those success paths. The instrumented
mock issue benchmark covers application allocations across 19 kernel families
(the original 14 plus five p33 paths); SYCL runtime/driver allocation, token-boundary lookup preparation,
Python coordination, fixture capture and diagnostic logging are outside that
zero-allocation claim.

GNU host argument audits compare independently reconstructed operations and
bindings to the actual selected captured vector. The serializer clears ABI
padding using GCC's builtin and intentionally refuses Clang; icpx correctness
runs are separate. The owner invalidation/sanitizer gates, actual forced-miss
runs and byte comparisons are complementary checks. No new arithmetic, NaN
policy or exceptional-value behavior is introduced by preparation; inherited
kernel qualifications and limits remain in force. Device ownership and kernel
execution still require the coordinator windows.
