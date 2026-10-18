# Packet92 rank-1 reply boundary

CPU source attribution, October 18. Sources and the inspected packet84 selection
are hash-bound in attribution-sources.json. Packet91 retains this same boundary.
The control is packet84: hc-wide, wide64, ordered retirement, rec-parallel,
production route/norm/dense, draft-HC, batch rollback, rank1 draft, 24/24.

| Order after target enqueue | Dependency and disposition |
| --- | --- |
| Engine::drain waits on tail; progress callback publishes an earlier draft result | Required completion and asynchronous-error proof. Keep. |
| drain queries pending event timings, enforces four-second event budget, aggregates class/site data | Mixed accounting and safety; keep before reply in this bounded candidate. |
| drain clears pending records; ordered retirement checks terminal prefix, synchronizes provider, releases event handles | Error/completion/lifetime proof. Ordered already removes per-event polling. Keep. |
| integer(error) calls readback: drain, copy to pinned slab, wait, ordered retire, host memcpy | Sticky target error must be zero before reply. Keep. |
| Retained layer snapshots are copied and zeroed when requested | Correctness fixtures and subsequent captures depend on this. Keep. |
| integer(next_token) copies and waits exactly as error; publishes verified token with release store | Required token and cancellation proof. Keep. Rank1 final hidden state stays in streams on the device; draft copies it before overwriting half inputs. |
| Streaming resource release, if applicable | Keep; candidate admitted only in resident mode. |
| getrusage process/thread end snapshots | Keep here so counters retain the same half boundary, excluding the next draft. |
| getloadavg, sched_getaffinity; site half row; formatting/output of all timing fields | Bookkeeping. Freeze all per-half values, defer these calls and output. Affinity failure or stream failure remains fatal. |
| Construct Reply; execute adds received/completed timestamps; worker writes mailbox reply and release-publishes sequence (socket path uses transfer) | Controller can observe the verified result. |
| Controller immediately calls rank1 accept and waits; accept publishes retained fixtures, clears candidate | A barrier: bookkeeping merely moved after half send but before accept still blocks draft startup. |
| Controller starts asynchronous rank1 draft; provider queues unchanged draft kernels and result copies | First useful overlap opportunity. Run deferred half bookkeeping after this submission, before draft reply/next half. |

All existing fields stay. Counters/arrays are copied before deferral; host load
and affinity explicitly describe report time. No kernel, queue order, readback,
state ownership, verification or error check moves. Only host report work moves.
Without a draft, flush before the next command other than accept; reset, dump,
finish and native termination must flush. On failure poison the deferred slot,
abort the native mailbox and refuse subsequent commands. There is at most one
pending report and no background thread. Preserve the report on exceptional exit
where possible; a failed receipt write is a failed run, never silent success.

Cheap identical timers in both views measure result-ready to half publication
and the report bucket. Two steady_clock reads per bucket; separate diagnostic
rows keep publication timing out of the fixed Reply ABI. Bookkeeping timing
excludes writing its own diagnostic row. Timers are host observations, never GPU
latency. Control completes bookkeeping before publication; reply-first can do it
after next-draft submission. End-to-end screens decide whether overlap helps.

Packet76 measured 666.135 us before ordered retirement. Its current remainder
and the movable sub-bucket are unknown. Packet85's +0.293 tok/s per 0.1 ms is a
conditional sensitivity, not this candidate's expected gain. No claim that all
retirement/profiling is safely movable, or that the 1.544 ms residual is idle.
Graph replay remains deferred. A small/neutral screen closes this mechanism.
