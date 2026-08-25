# Clean fa0 graph-port parent sentinel r1 failure

Date: 2026-08-25. State: **failed closed; cleanup passed; no curve authority**.

The same-new-binary target-only Q8/F16 TP1 parent sentinel completed its
graph-off control successfully. The control exited zero, emitted the required
all-zero graph summary, produced 1,290 output bytes with SHA-256
`48c64a14860487bbf8caca4c4965615476f273149ce8c0f521b838a951b030c4`,
and left its process group empty.

The graph-on/cache-eight candidate then exited with return code 1. Its stderr
contains the exact exception message:

```text
wait cannot be called for a queue which is recording
```

The complete emitted line was:

```text
wait cannot be called for a queue which is recording to a command graph.Exception caught at file:/home/steve/src/llama.cpp-q38-tp1-graph-port/ggml/src/ggml-sycl/ggml-sycl.cpp, line:4547
```

Before that failure, the log showed two completed cumulative graph sequences.
Compute one emitted requested=1, cache-miss=1, recording-entered=1, and
replayed=1 with recorded=1 and created=1. Compute two emitted requested=2,
cache-miss=2, recording-entered=2, and replayed=2 with recorded=2 and
created=2. These are useful pre-failure observations only. The process emitted
no accepted shutdown summary, created no candidate receipt, and never reached
the exact graph-off/on output-parity comparison.

The runner recorded `state=failed`, stage `candidate-graph1-cache8`, and
`cleanup_passed=true`. The terminal receipt SHA-256 is
`ac63223683ba5e40b0078d3ab59c895e59eb8de9f1ed76ca99d0ba1f0e4d79f0`;
the candidate stderr SHA-256 is
`3dd475cc6ff15b9a510e41565b2962118cc45a1477452f3812f13293e0f7175c`.
The durable JSON record binds the remaining control, candidate, identity,
model-view, compute-gate, DSO, and terminal evidence hashes.

This result does not determine a root cause. It records only the observed
runtime sequence and exception. The focused port is not mechanism-qualified,
the seven-cell curves remain unauthorized, and no site, speed, quality,
record, submission, or estimate claim follows. Protected graph-off results and
historical featured speeds remain unchanged.

Raw create-only evidence remains at:

```text
/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-fa0-graph-port-sentinel-20260825-r1
```
