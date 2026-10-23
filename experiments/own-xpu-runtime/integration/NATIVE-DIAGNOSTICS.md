# Bounded native diagnostic capture

[native_diagnostics.py](native_diagnostics.py) drains a blocking, read-only pipe
into an already-created [BoundedEvidence](BOUNDED-STORAGE.md) file. It creates
no producer, native process, service or device owner. It controls routed stderr
capture only; driver caches and native output files remain outside its scope.
The existing storage budget/profile stays unchanged and not live-ready.

## Ownership and use

```python
from native_diagnostics import PipeDiagnostics

# Caller owns the pipe and has already created this bounded evidence file.
diagnostics = PipeDiagnostics(stderr_read_fd, evidence, "stderr.log").start()

# An outer coordinator polls this during its independently admitted work.
if diagnostics.incident_event.is_set():
    original_incident = diagnostics.error

state = diagnostics.join(timeout=1)
# A timeout never closes the busy reader or signals the producer.
```

`start()` duplicates the supplied FD and owns only that duplicate. The caller
keeps the original FD and may close it after successful start. There must be
no other pipe reader or mutation of shared file-status flags. Nonblocking and
write-only endpoints are refused without changing their flags. A failed start
is not permission to retry; retain and inspect its status.

The reader and capture worker are non-daemon threads. The reader uses fixed
chunks and never waits on the evidence writer or queue capacity. A separate
capture thread performs the writes/fsyncs. Defaults are16KiB chunks and four
queued chunks, giving a96KiB payload-buffer bound including both active chunks
(Python object/thread overhead is additional). This is not a guarantee about
OS scheduling or an otherwise malfunctioning pipe.

## Incidents and retained state

If the logical byte cap is reached, the writer fails, or the queue fills, a
sticky incident is recorded. Capture stops at a contiguous prefix; queued and
subsequent bytes are discarded while the reader continues to EOF. The reader
does not wait for a blocked writer. An in-progress write can still complete
its earlier prefix. No later chunk is written after a discarded gap.

`error` retains the first original exception object; `capture_error` also keeps
a later original writer exception if queue saturation occurred first. There
are no incident callbacks, error lists, automatic signals, kills or retries.
The outer coordinator must halt new requests and choose its existing incident
drain action. Observe the event; never clear it.

`join(timeout)` accepts0–60 seconds and reports reader and capture retention
separately. A timed-out join leaves both the reader endpoint and any active
writer intact. The caller must keep the evidence writer alive while capture
is retained. `successful_append_bytes` counts only fully acknowledged chunks;
after a partial writer failure it is explicitly a lower bound. The bounded
writer's own accounting supplies actual partial-prefix bytes once safe to read.

Only observed EOF automatically closes the duplicate. Unexpected read failure
does **not** establish EOF or producer progress; the endpoint stays open so this
component does not induce SIGPIPE. A reader-start interruption can similarly
leave an uncertain live reader. `retained` includes an owned open endpoint even
when no thread is currently reported alive.

After every producer/write endpoint has independently exited, a coordinator may
call `release_after_producer_exit(producer_exited=True)`. This is an explicit
caller attestation, not a process check. It also requires both workers finished
and the reader completion observed. It must not be used as timeout cleanup;
unresolved reader startup requires separate inspection. The component never
closes the caller's original descriptor.

## CPU evidence

Ten [tests](test_native_diagnostics.py) use real anonymous pipes and producer
threads, with no native process. They cover clean EOF, cap/failure discard,
original-error retention, partial-write reporting, a blocked writer with a
completed1MiB producer, join retention, interrupted start, retained read-error
endpoints, rejected FD modes, single use and descriptor cleanup. See the
[CPU receipt](receipts/native-diagnostics-cpu.json).

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest discover \
  -s experiments/own-xpu-runtime/integration -p test_native_diagnostics.py -v
```

The [prior candidate](lineage/native-diagnostics-before-endpoint-review/native_diagnostics.py)
is retained as review history; it closed read-error/startup endpoints too early.
These tests qualify the pipe component, not its integration with a native owner
or a complete live storage budget.
