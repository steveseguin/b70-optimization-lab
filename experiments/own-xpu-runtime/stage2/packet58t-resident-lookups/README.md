# Packet58t: resident packed lookup bytes

CPU-qualified candidate for the packet58p one-card engine. The only model data
change is its **host backing**: exact packed embedding and PLE bytes move from
per-row file mappings to read-only anonymous copies at load. The device data,
quantization, arithmetic and outputs are unchanged by design. Actual full-model
device equality and performance remain pending.

[Access inventory and budget](ANALYSIS.md), [work note](../../../../notes/2026-10-18-own-runtime-packet58t.md),
[CPU closeout](CPU-PREPARATION-CLOSEOUT.md), [boundaries](DO-NOT-REPEAT.md).

The copied engine entry is the checked 58j source underlying 58p's selected
native artifact; 58p's tile16 selection and seven-window wrappers are retained.
Packet58r's bracket entry and error-teardown machinery are copied locally,
then narrowed to file-backed / resident / file-backed lookup views with the
same tile16 kernels. Parents are read-only inputs. `copy-manifest.json` records
snapshot provenance; it is not a requirement that another worker's mutable
parent readiness files remain unchanged.

`resident_source.py` contains the explicit integration delta.
`native/resident_lookup.hpp` owns bounded copying, SHA-256 verification,
read-only protection and cleanup. It copies 29,321,610,240 bytes across two
GGUF tensors. `prepare_token` retains its original lookup and dequantization
arithmetic and now records preparation-specific major and minor fault counts.
The original whole-token counters remain alongside them.

CPU reproduction (from repository root, stdin closed):

```bash
P=experiments/own-xpu-runtime/stage2/packet58t-resident-lookups
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/restore_fixtures.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/build_engine.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/resident_gate.py" copy < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/resident_gate.py" engine < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/fullshape_submit_gate.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/startup_gate.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/postload_allocation_gate.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/budget_gate.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/k1_cpu_gate.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/run_cpu_gates.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/argument_gate.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/screen_argument_gate.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/seal.py" --verify < /dev/null
```

The entry-only build reuses hash-bound frozen kernel objects. GNU and Intel
host entries compile the changed host path; the original kernel objects are
shared deliberately. The independent packed-copy/dequant gate compiles its
whole fixture separately with both compilers. No device binary is executed
by these commands. This is a local experiment, not a standalone published
recipe. Rebuilding may change binary hashes; never reseal a started run.

`build_engine.py` uses packet94's compiler turn, an 8 GiB CPU-process address
space cap, a 25 GB root stop floor and a 200 MB build ceiling. Full-size mocks
reserve sparse virtual arenas larger than 8 GiB; their physical RSS is checked
instead. Actual launch-argument gates must inherit unlimited address space
and prove that no import alters resource limits. No runtime wrapper sets caps.

The queue proposal is
[proposed-p58t-screen-A.txt](../../ops/lane-queue/proposed-p58t-screen-A.txt).
`plan_queue.py` copies it into a temporary directory and asks the normal
coordinator to plan it. It never edits the live queues or starts a service.
Expected duration is 15–25 minutes excluding admission waits; the native and
model-window watchdogs are 7,200 seconds, over four times the upper estimate.
Two K1 fixtures precede one model load and three full twelve-prompt views.
The coordinator must keep lane B out through the whole bracket and gaps.

The unchanged packet49 oracle checks all 128 generated tokens per prompt;
this repeated one-load screen is not the 512-token final gate. Every view
retains fault counters, preparation time and rate. No slow tokens are removed.
Copies load before the first control, so source file pages have been read;
this is not a reconstruction of 58n's cold file-cache state. All three views
hold the same anonymous allocation. No future zero-fault guarantee under swap
or memory pressure is claimed; there is no mlock or host-setting change.

A later seven-window candidate chain uses `--resident-lookups` on every model
window and remains blocked until `verify_ready.py` rereads the completed
resident bracket, verifies its original receipts, requires exact output,
zero resident preparation major faults, and at least 0.5% over both controls
with at most 3% control drift. A saved readiness flag cannot authorize it.
There is no submission/publishing entry in this packet.
