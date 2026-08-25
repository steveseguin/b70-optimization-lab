# Qwen target-Q8/F16 TP1 fa0 graph-port parent sentinel R3

State: **sealed, preregistered, inert, and not launched**.

R2 created its result root and completed model-view verification, but aborted
before either graph arm because the mature lifecycle read
`manifest["runtime"]["source_provenance"]` and the specialized R2 schema kept
the same object only at `manifest["source"]["provenance"]`. No graph-off or
graph-on row was produced.

R3 fixes only that packet mismatch. Its synthesized runtime manifest copies
`source.provenance` exactly into `runtime.source_provenance`. The sealed R2
source, model, binary, backend, CMake receipts, 34-row DSO closure, runtime
knobs, prompt, and 64-token same-binary arms are otherwise byte-identical.

The R2 partial root remains immutable. R3 uses the create-only root:

```text
/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-fa0-graph-port-sentinel-20260825-r3
```

The pass contract remains unchanged: the graph-off summary must be all zero;
the cache-eight candidate must complete with positive record/create/hit/direct
replay evidence, exact counter conservation, no pointer-stability failure, and
`replayed == requested`; both 64-token outputs must match byte-for-byte.

Even a pass is parent-sentinel-only. It grants no curve, website publication,
speed claim, quality claim, record submission, TP2/TP4 expansion, or authority
to replace a protected graph-off value.

Exact acknowledgement:

```text
RUN qwen36-q8-f16-tp1-fa0-graph-port-sentinel-20260825-r3
```
