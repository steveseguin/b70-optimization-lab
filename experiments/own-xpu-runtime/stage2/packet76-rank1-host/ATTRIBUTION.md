# Packet 76: rank 1 host residual

CPU analysis of 96 instrumented halves (12 prompts, fixtures 9–16). No GPU ran.
The original residual is **1607.837 µs**, not measured device idle.

| Additive accounting of the residual | Mean µs |
| --- | ---: |
| (a) Consecutive device gaps from final layer end through argmax | 1.249 |
| (d) Host work outside prepare, enqueue and wait timers | 1457.321 |
| (d) Outer command setup, including ordered half-input submission | 92.215 |
| (b/c/d) Unresolved boundary time | 57.053 |

The host work bucket follows the enqueue loop in `rank.hpp`: drain reporting,
profiling queries, event retirement, result copies outside the wait timer,
resource accounting and timing output. It is accounting, not a function-level
profile. Preparation is effectively zero in these asynchronous draft halves.
Its matched uninstrumented control is **666.135 µs**;
instrumentation adds **791.185 µs** in that bucket.
That difference is observation overhead, not an available production speedup.

(a) The two fully sampled layers have 8.029 µs of
adjacent gaps in total. These are already inside the subtracted layer span and
are not additive to the residual. Events for intermediate layers are missing;
the large interval between sampled layers contains kernels and cannot be called
idle. No full-device idle or inter-layer-gap total can be recovered.

(b) Host receipt clocks put mailbox arrival at
7.940 µs after send. This precedes
rank_received, so it is outside the measured half. The controller copies the
rank0 hidden state before sending the half request. Rank0 completion and handover
waiting must not be charged to this residual. All 480 sampled target
copy events report the same zero-width timestamp, 223696213281 ns, while compute
events use a very different range. These cannot establish transfer latency or
arrival on the compute timeline; zero duration does not prove a free transfer.
Controller `bounded_spin_iterations` is null, not a measured spin count.

(c) Rank1's instrumented host enqueue loop averages
3075.507 µs, and its control averages
3029.693 µs. This overlaps device work. No
per-kernel submit times or clock correlation were retained, so late host issue
cannot be separated from device scheduling. The 1.61 ms cannot honestly be
divided into four fully causal, nonoverlapping numbers using these receipts.

The JSON hashes every input, retains all 96 half calculations and reports
packet64/70 host timings separately. No GPU timestamps are compared across
cards or subtracted from host timestamps. No extrapolated timing is used.

## Selected screen

The largest identified bucket is host housekeeping. The existing retirement
path polls every event again after waiting for the tail, then synchronizes and
releases events. Screen a rank1-only ordered-queue retirement path: one terminal
completion check proves the ordered prefix, retaining error propagation,
synchronization and event release. Kernels, their order and arithmetic stay
unchanged. Add host timers for retirement and profiling to distinguish this
mechanism from instrumentation overhead in the next screen. Retirement's share
is not measured yet; neither a speedup nor full attribution is claimed.
