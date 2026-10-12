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

Failure receipts and the window boot marker are written before a cooperative
stop/drain. No retry, reset, hard kill, process group kill, or power/host setting
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
