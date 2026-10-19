# Packet58as: bounded spin for the one-card owner wait

CPU preparation only. No GPU, service, settings or live queue changed.
The source is a private packet58aj record-line copy. Packet58ar is untouched.
This port independently reimplements packet56x's sleep20 policy: one 250 µs
spin budget per wait invocation, CPU pause and yield every 256 iterations,
then 20 µs sleeps capped at the original deadline. Async errors are checked
on every iteration and completion still uses `wait_and_throw`. A uses the
original millisecond poll. The separate DMA-before-barrier recovery sleep stays.

The single proposed lane-A job is whole-host: K1a, K1b, then one model load
with A0/B0/A1/B1/A2, twelve fixed 128-token prompts each. There is **no separate
smoke**. A0 is an exact control and warm-up; it is excluded only from speed and
drift. Both B views must beat **every** warm A control by at least 0.5%, warm
control drift must be at most 3%, and every request must match the unchanged
`iq3-p49-split32-v1` oracle (60/60). In this packet the bracket's last field
selects `poll` or `spin`; lookups are resident in every arm. The test is a
kill-test screen, not a new record or public performance claim. Fresh-process
repeats and later qualification remain separate.

All arithmetic, selection and kernels remain packet58aj's. Keep HC fusion,
HC-wide, wide64+halfcache, other-fusion, ordered foreground retirement,
tile16, overlapped maintenance, zero-copy misses, 21,552,729,600 cache bytes,
4K BF16 KV and both complete resident lookups. Each reset retains allocation
identity and empties request state. No prompt/KV/response reuse.

Each request writes `owner-cpu.json` using CLOCK_THREAD_CPUTIME_ID at request
boundaries. The report gives total owner CPU seconds divided by request wall
seconds, as a percentage of **one core**, for each view. It includes prompt
reading and request work; it is not whole-process or whole-host CPU usage.
These two sensor reads are outside the token timing loop and identical in A/B.
Actual utilization and device speed are pending the coordinator run.

[CPU checks](evidence/cpu-exactness.json) compare every miniature output byte
with packet58aj under GNU and Intel, across 120 actual request resets and ten
view resets. The [device-define CPU transport probe](evidence/preparation.json)
uses the real device argv/parser/production plan, five view resets and 60 request
resets, with 130 real memory-sensor samples. Its transport and weight bytes are
synthetic; it does not prove GPU execution. [Wait tests](native/wait_test.cpp)
cover completion, deadline, yield, capped sleeps, async and completion errors.
[Real-data replay](evidence/analyzer-real-parent.json) reads 60 packet58aj and
72 packet58aq requests, including all cold rows, from byte-identical private
snapshots. They cannot qualify as new spin-wait data. Synthetic threshold tests
are explicitly labeled. The 600 s per-operation wait is at least four times
the largest measured cold phase; there is no wall-clock data-proof cutoff.

[Shared entry/report rehearsal](evidence/shared-entry-report-final.json), actual
entry imports under the closed launch environment, both native loaders, every
native flag against --help, and [temporary lanequeue plan](evidence/queue-plans.json)
pass. The shared tool has no unranked one-card preparation adapter; the separate
real device-define CPU probe above supplies that evidence. Shared report testing
also exercises its generic synthetic smoke report; no smoke job is proposed.
In-run checks cover stream presence/format and exactness only. The final decision
runs after the complete bracket.

CPU build uses nice19, CPUs 8–15/24–31, Python -B and one ops/compile_turn.py
turn. Compilation and tests stay below 4 GiB; the CPU disk stop is 27 GB.
Device admission retains a 25 GB disk floor, whole-host lane A, the unchanged
98,990,252,032-byte memory floor and idle-class ionice for native model readers.
The coordinator owns the launch, lane-B exclusion, fault review and graceful
shutdown. One attempt, no retry or resident service. Final READY is written last.

## Retention and rebuild

This is a host-local research packet, not a published deployment package.
The private 4,194,304-byte RoPE table preserves the original runtime bytes.
Tracked real-device timing snapshots and historical admission inputs are needed
to replay the analyzer and admission; none is a packet58as device measurement.
Their exact hashes are sealed. Restore them from Git, never regenerate data.
Compiled objects/executables are ignored. `restore_build.py` restores unchanged
parent objects only after checking every original byte against the retained
manifest; `build_engine.py` rebuilds the entry, wait backend and CPU probes in
one compiler turn. The final source diff is [native-delta.patch](native-delta.patch).
The source tree and every prior packet are preserved; only this packet's new
source, proposal and work note are committed.
