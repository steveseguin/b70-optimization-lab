# Packet58n: one-card single-lever screen

**CPU-prepared only.** [Analysis](ANALYSIS.md) finds identical expert-cache
traffic and much slower host lookup preparation in packet58k's losing bundle.
The retained down-kernel K1 cases improve with tile16, including host-resident
weights. The proposed bracket isolates that lever:

1. Fresh production: down=production, route=route-exp32-rank4, recurrence=rows4-shared.
2. Fresh down-tile16: change **only** down; all other choices remain production.
3. Fresh production again.

Each arm loads the model **once**, then runs all twelve fixed prompts once at
128 output tokens. Every output token must match the unchanged packet49 oracle.
BF16 KV, target-only decode, context 4096, zero prompt/KV/response reuse and
the 18 GB immutable expert cache stay fixed. Two small fresh-process K1
fixtures before each model load select zero-copy or streamed misses at the
unchanged 12.5 GB/s threshold. No K1 receipt crosses arms.

The wrapper is copied from frozen packet58k, including its 58kf boundary
repair. Native binaries are byte-identical copies of the sealed packet58j
engine and cache fixture: **39,526,592 bytes (39.53 MB)**, below the 150 MB
build cap. No compilation or native executable ran. Inherited byte and 80
full-size startup/submit checks remain parent evidence, not new device checks.
[parent-screen-manifest.json](parent-screen-manifest.json),
[copy-manifest.json](copy-manifest.json), [parent-build-receipt.json](parent-build-receipt.json)
and [build-receipt.json](build-receipt.json) bind that provenance.

## Coordinator proposal

The only new ops file is
[proposed-p58n-screen-A.txt](../../ops/lane-queue/proposed-p58n-screen-A.txt).
It has three lane-A jobs in the order above, on **card 0 with whole-host
exclusion**, using fresh `evidence/card0-loo-a/{production-before,down-tile16,production-after}`.
It was planned on a temporary queue only; no live queue was edited.

Reserve **33–39 minutes**, conservatively unchanged from 58k: 10–12 minutes
per arm including its two internal 90-second gaps, plus two outer 90-second
queue gaps. Admission waits and unusually slow storage are outside the
estimate. It is not a timeout or kill deadline. The inherited fixture/model
watchdogs request cooperative stops; there is no retry, hard kill, service
restoration or automatic record launch.

| Bound | Unchanged bytes |
| --- | ---: |
| Required MemAvailable for model timing | 118,308,908,048 |
| Host budget excluding reserve | 109,718,973,456 |
| Host reserve | 8,589,934,592 |
| Pinned packed experts | 48,627,712,000 |
| Device expert cache | 18,000,000,000 |
| Conservative device/backing bound | 26,409,219,600 |

Every window retains lane-A ownership, lane-B exclusion, all-card foreign
client checks, the card-0 BDF mask, read-only memory-block fence, memory
admission, first-fault checks and the shared drain permit. The coordinator
must keep lane B out throughout the gap, including spacing between windows.
No 85.57 GB exactness-only floor is substituted for timing admission.
Only the job's own proven drained/pre-compute-refused records can be released.

The fault boundary is derived from the validated review capture's **newest
kernel line minus exactly two seconds**. It is never wall time, the raw newest
timestamp, or a later capture. The overlap regression tests are copied from
58kf and retained. The coordinator supplies a fresh review to each job.

The last job validates all nine distinct process owners, one boot, selected
views, native files, K1 choices, post-load allocation proof, all output tokens
and identical prompt/output signatures. All arms must select the same miss
path. It computes the median of six class medians using 99 intervals between
timestamps 1 and 100. The candidate must beat both controls and the saved
24.338653323339745 tok/s record; control drift must be at most 3%, exactly as
in 58k. An exact drained loss completes the queue but does not qualify a chain.

Keep the host preparation/major-fault counters when reviewing the outcome.
Do not discard high-fault tokens, adjust reported speed or rerun until page
residency is favorable. A single candidate launch and 128-token cap cannot
establish a record, fresh-process determinism or the strict final gate.
Any later full-chain/repeat work must select **down-tile16**, never the failed
three-lever port by default; it requires a separate proposal. No external
submission is made by this packet.

## CPU validation and restoration

Run from the repository root, using nice19, cores 8–15/24–31, `python3 -B`
and stdin `/dev/null`:

```bash
P=experiments/own-xpu-runtime/stage2/packet58n-onecard-loo
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/analyze.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/restore_build.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/run_cpu_gates.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/seal.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/seal.py" --verify < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/plan_queue.py" < /dev/null
```

[82 Python checks](evidence/python-cpu-gates.json) pass, including all-token
mutations, single-lever selection, fresh K1 owners, host admission, masks,
memory stops, faults, refusal/drain behavior and passive plans.
[All three queue plans](evidence/queue-plans.json) pass without creating the
future arm output root. The analysis joins 2,386 positions and retains the
source-bound receipt snapshots under `analysis-inputs/`; the generated pair
table is about 264 KB compressed. No new tracked artifact reaches 1 MiB.

`restore_build.py` only copies hash-matched existing parent binaries; it does
not compile or launch them. Keep frozen 58j sources/constants and dependencies
available. The native RoPE constant still uses its original source-relative
path. This is an in-repository research screen, not a standalone public recipe.
If parent binaries are absent, restoration needs separately authorized build
preparation; any compilation must use packet94's `compile_turn.py`, one
compiler at a time. Do not edit frozen parents to restore this packet.

See [CPU preparation closeout](CPU-PREPARATION-CLOSEOUT.md) and
[do-not-repeat boundaries](DO-NOT-REPEAT.md).
