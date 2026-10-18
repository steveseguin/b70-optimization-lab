# Packet58y: one-card attribution after cache overlap

CPU-prepared diagnostic copied from frozen packet58v. It uses the unchanged
`iq3-p49-split32-v1` target, tile16, 18 GB expert cache, full BF16 KV and
`cache_maintenance=overlap`. Device evidence and lever ranking are pending.
[Preregistered +3% gate](../../../../notes/2026-10-18-own-runtime-packet58y.md).

## Coordinator contract

Use only `ops/lane-queue/proposed-p58y-attrib-A.txt`, after packet58x smoke and
bracket, in **their same continuous whole-host hold**. Do not give 58y a separate
hold. Lane B must stay paused and drained; the diagnostic refuses unless both
58x jobs completed cleanly on this boot and PAUSE-B predates their first window.
It checks that the pause remains unchanged before each stage, during the gaps,
and after completion. The coordinator owns the order and continuous hold.
[Batch contract](batch-contract.json), [runtime guard](batch_gate.py).

The proposal has explicit dependencies on `packet58x-smoke-A` and
`packet58x-v5-A`. Temporary planning includes those two jobs in order before
58y. The first attempted batch plan is retained: it caught a changing 58x seal.
Never reinterpret a failed predecessor plan as a passing batch.

One model load runs D0: twelve fixed prompts, at most 128 output tokens each.
K1a/K1b precede the load. Expected total 600–900 seconds, watchdog 7200 seconds.
The native loop checks every generated token against packet49 before advancing;
Python repeats the complete output check. Oracle files keep their original
`oracle-binding.json` / `shared_oracle.py` authority; no external symlink is
flattened into the source seal. A mismatch fails the whole diagnostic.

The original drain fix, native getrlimit check, whole-host admission, closed
environment and lanequeue-derived `screen-packet58y-attrib-A.service` gate remain.
The proposal embeds [the recorded oneAPI library path](library-path.json).
Packet58u measured admission plus 58v's allowance requires **95,435,761,152
bytes** of available host memory, including the unchanged 8 GiB reserve.
Instrumentation adds fixed counters and a 24,576-byte published-table bitmap
inside the inherited 32 MiB metadata allowance; it adds no device allocation.

## What each row means

Every prefill position and generated event has a row in
`WSCREEN/run/run/D0/<prompt>/attribution.jsonl`. `generated_index=0` is prefill;
1 is the first generated token; 2–100 are the primary 99 charged positions.
The first cold prompt remains in every full-suite aggregate.

| Field | Measurement |
| --- | --- |
| `host_exclusive_ms.prepare` | Token preparation and input upload submission, excluding separately counted waits |
| `host_exclusive_ms.enqueue` | Existing command submission loop, excluding waits |
| `host_exclusive_ms.cache_boundary` | Publication preparation and fill submission at the safe boundary, excluding waits |
| `host_exclusive_ms.cache_plan` | CPU LRU planning while compute is already enqueued |
| `host_exclusive_ms.readbacks` | Token/status readback submission and host processing, excluding waits |
| `host_exclusive_ms.cache_after` | Route readback submission, route processing, observation, existing cache logging, excluding waits |
| `host_wait_ms` / `host_wait_calls` | Existing event and queue waits, split by the operation being awaited |
| `enqueue_class_ms` | Host submission spans in the ten inherited operator families; nested in enqueue, never additive to it |
| `class_submissions` | Compute-kernel submission counts by family (copy-only sites are not kernels) |
| `device_class_ms` | Null: production queues have no valid profiling timestamps |
| `fills` / `fill_bytes` | Expert blocks and commanded fill payload submitted at this boundary |
| `misses` / `miss_bytes` | Selected experts and logical bytes served through the actually published host pointers |
| `hits` / `hit_bytes` | Selected experts and logical bytes served through published device pointers |
| `publication_uploads` / `publication_bytes` | Pointer-table publication commands and payload |
| `fill_queries` / `fill_pending_queries` | Existing completion queries; no extra device query is added |
| `fill_pending_end` | An unpublished fill transaction remains; not a claim that DMA is still running |
| `residual_ms` | Token span minus exclusive host buckets and waits; bookkeeping, timer overhead and uncovered CPU work |

The wait names are compute (including zero-copy miss kernels), separate
zero-copy-miss waits, fill copies, table publication, readbacks and input upload.
There is **no separate wait for zero-copy miss kernels** in this engine. Its
zero count is a control-flow fact; `zero_copy_miss_stall_ms` is null because
that cost shares the compute tail. Overlapped fills have no blocking decode
wait; quiescent shutdown/view-change fill waits are outside decode.

Miss counts use the table actually published, including revoked victims and
incomplete fills. The cache's staged `resident()` metadata is deliberately not
used as a proxy. Byte counts are logical payload, not measured PCIe traffic.
No event profiler, graph timing, new synchronization or per-layer drain is added.
The ten class names are included in the nullable device map in the same order
as the enqueue/count arrays. These unavailable durations are never zero-filled.

The additive partition uses one steady host clock. Host enqueue/planning can
run alongside device work, so neither those spans nor summed kernel durations
are automatically removable critical-path costs. The new trace write occurs
after its row's clock stops; ordinary generated timestamps still include the
intervening instrumentation work in the next interval. The analyzer retains
that interval residual and does not turn token wall time into a throughput
headline. No matched device overhead result exists yet.

## CPU reproduction and evidence

Run from this directory with `nice -n 19 taskset -c 8-15,24-31 python3 -B`,
stdin `/dev/null`. Never run the device binaries in CPU preparation.

1. `restore_fixtures.py`, `build_engine.py` (shared compile-turn admission).
2. `protocol_gate.py`, `k1_gate.py`, `cpu_gates.py fullshape`, `cpu_gates.py reset`.
3. `attribution_gate.py`, `startup_gate.py`, `argument_gate.py`, `run_cpu_gates.py`.
4. `shared_oracle.py --require-complete` into `evidence/oracle-gate.json`.
5. `seal.py`, `seal.py --verify`, `plan_queue.py` (temporary queues only).

Builds are ignored and reproducible from frozen, hash-checked kernel objects.
Both parent executables are relinked byte-identically before object reuse.
The attribution delta is [attribution_source.py](attribution_source.py) and
[native/attribution.hpp](native/attribution.hpp). The symlink-preserving
[copy manifest](copy-manifest.json) pins the original 58v bytes.

CPU gates cover miniature token/layer equality, protocol races, full-size
startup, admission, drain/teardown, parser negatives, actual proposed unit and
closed-environment entry through all three intercepted native launches, and
same-hold refusal cases. The suite also refuses missing, truncated, reordered or
inconsistent traces before success. They establish CPU behavior, not device correctness.

[CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md),
[do-not-repeat boundaries](DO-NOT-REPEAT.md), [seal](build-receipt.json).
Hot-expert-cache idea credit: Niko1221 / Strata. Implementation is lab-authored.
