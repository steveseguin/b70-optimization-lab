# Muse width-16 PTI timeline

This preload collector records PTI device timestamps for kernels, copies,
P2P copies, fills, and device barriers.  It exists to decompose a target-only
TP4 Muse width-16 pass into real GPU busy intervals and queue gaps without
changing llama.cpp's queues or adding profiling tags between operations.

Build:

```bash
source /opt/intel/oneapi/setvars.sh
cmake -S . -B build -DCMAKE_CXX_COMPILER=icpx -DCMAKE_BUILD_TYPE=Release
cmake --build build -j4
```

Run the target under `LD_PRELOAD=.../libmuse-pti-width16.so` with
`ZE_ENABLE_TRACING_LAYER=1`, set `MUSE_PTI_OUTPUT` to the desired JSONL, and
set `MUSE_PTI_DECODE_CALLS` to the number of `llama_decode` calls to record.
The library interposes those calls, activates PTI only after model load,
synchronizes each diagnostic call, and disables/flushed tracing immediately
after the requested count.  This avoids the redesigned Level Zero runtime's
unusable timestamp queries against model-loading copy events.
The output is diagnostic: an adjacent untraced `llama-bench` measurement is
the wall-time authority because tracing adds overhead.

## Result: incompatible with current Level Zero V2 runtime

The collector compiled against Intel PTI `1.0.1-21`, but the runtime could
not produce a usable trace.  With device views enabled at startup, PTI
repeatedly called `zeEventQueryKernelTimestamp` on incomplete model-loading
copy events, emitted status `1` warnings, and spent minutes at 100% CPU in
flush.  Deferring all `ptiViewEnable` calls until an interposed first
`llama_decode` did not repair it: loading PTI together with
`ZE_ENABLE_TRACING_LAYER=1` still triggered the same polling before the
interposer was reached.  Both attempts were terminated at their diagnostic
bounds; the server binary and GPU runtime did not crash, and production
restarted without device recovery.

The paired untraced width-16 control was valid after its first cold sample:
the six warm samples were `42.529 / 42.380 / 42.434 / 42.396 / 42.439 /
42.331 ms`.  This agrees with the existing width-16 cost evidence.  The PTI
files are preserved under
`/mnt/fast-ai/bench-results/muse-glimmer-30b/pti-width16/`; all record JSONL
files are empty and must not be interpreted as a zero-busy timeline.

Decision: close PTI device views on this runtime.  The existing sparse
profiling-tag evidence remains the only working queue-timestamp diagnostic,
but its tags perturb throughput too strongly to justify a prerecorded
command-list implementation without a demonstrated `>=7 ms/pass` idle pool.
