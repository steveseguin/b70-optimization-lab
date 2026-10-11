# Packet 18 W0 canary, attempt a: device work passed, process aborted while exiting (2026-10-11 15:04 UTC)

Cards 2+3 (PCI 43:00.0 + 47:00.0), no NEO key, host fences. The native receipt says
`passed: true`: 100 verified peer-copy round trips, 1,000 kernels per card, the real
begin/broadcast/boundary/return/commit sequence, 545 host waits, device work 2.8 ms,
start-up and JIT 8.7 s, largest submission 31.6 µs, teardown complete with zero live
bytes. No kernel fault line. This is the same card pair that faulted at 09:09 UTC.

After writing that receipt the process aborted (`std::system_error: Invalid argument`,
exit −6), so the wrapper recorded W0 as failed and W2 cannot start.

Cause, from a debugger backtrace of a second run ([gdb-backtrace.log](gdb-backtrace.log)):
at the end of `run_canary` the last reference to a SYCL kernel bundle is dropped
after `d.shutdown()`. That destroys the SYCL context, whose pool teardown calls
`ze_memory_provider_free` into a Level Zero driver object the owner's shutdown has
already released; the driver's mutex is gone (error without the debugger, a wait on
the dead mutex with it). It is an object-lifetime bug in the canary's own code, after
all device work and teardown, not a device fault. The debugged process was idle and
was ended through the debugger; the kernel log stayed clean.
