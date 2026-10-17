# Wait audit against packet56w

Both binaries use the same helper. `spin` checks completion with PAUSE until
completion/deadline and yields every 256 iterations. `sleep20` does that for
250 microseconds, then polls with sleeps of at most 20 microseconds (capped
to the remaining deadline). The budget is not restarted after sleeping.
Scheduler preemption can exceed these requested intervals; no real-time bound
or measured device improvement is claimed.

| Path | Packet56w | Packet56x |
| --- | --- | --- |
| SyclDevice::wait: target, draft, corrected miss, copies/drains | 250 us spin then 1 ms sleep | Selected helper; final event wait_and_throw and error check retained |
| Controller request/reply, accept/rollback, draft publication | 250 us spin then 100 us futex timeout | Selected helper; acquire/release, stop, peer abort, deadline retained |
| Engine::wait with pending draft callback | completion poll with yield on each loop | Selected helper; progress callback and guard continue on every loop, plus final callback |
| Handoff | memcpy after rank-0 drain and before rank-1 request | Unchanged; no independent sleep |
| Device::wait / retirement / idle marker | Delegate to backend wait | Covered by SyclDevice helper |
| Queue synchronize | Direct queue wait_and_throw after event/idle drain | Unchanged; no explicit timed poll |
| rank.hpp socket transport | poll(fd), wakes on data or stop | Unchanged; not a periodic sleep on native token path |
| owner/rank stop probe | poll(fd, 0) | Unchanged nonblocking cancellation |
| MTP/rank injected stall | poll(nullptr, ..., 5/10 ms) | Unchanged fault-injection-only code |
| hold_for_supervisor | condition variable hold after unsafe teardown | Unchanged emergency lifetime retention |

The complete local include closure was searched for sleep_for, sleep_until,
FUTEX_WAIT, wait_and_throw, yield and poll. No 1 ms timed device poll remains.
Publish still issues the existing futex wake; it is a wake hint with release
semantics, and no wait depends on that hint. Keeping it avoids a second
host-side optimization in this experiment.

The rank-0 queue profiling property adopted by packet56w is retained. Target
and draft kernels, submission ordering, arithmetic, prefix, dispatch, selection,
BF16 cache and packet49 oracle stay unchanged. See evidence/source-delta.json
and evidence/native-waits.patch. This is our own host scheduling change.
