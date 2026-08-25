# Target-only Q8_0 q8_0-KV TP1 fa0 graph exact-depth preregistration

State: **preregistered, unsealed, and not launched**.

This is a distinct q8_0-KV companion to the F16 graph work. It may measure only
the seven target-only Unsloth Qwen3.6 Q8_0, TP1, MTP0, graph-on cells at true
active contexts 0/2/4/8/16/24/32K. It does not modify, rerun, replace, or infer
from the accepted graph-off q8_0-KV values.

The packet deliberately fails closed until the new `llama-bench`, graph backend,
and complete effective DSO closure are sealed and the focused-port parent
sentinel has passed on the same build root. The F16 parent can transfer only
mechanism evidence and build provenance; it cannot transfer q8_0-KV correctness
or quality.

## Execution and graph evidence

Each context is a fresh `llama-bench` process with its own home, cache, SYCL
cache, temporary directory, process group, `/dev/null` stdin, and watchdog. This
separation is intentional: each cell must independently emit exactly one graph
summary and positive request, fresh miss, record, create, cache-hit,
direct-replay, and replay evidence. Compatibility rejection, unsupported-device,
and cache-full counts must be zero, cache limit must be eight, and every request
must be replayed. Missing evidence in any one cell fails the whole curve.

The seven raw JSON arrays are merged only after all identities and per-cell graph
gates pass, then processed by the existing exact-depth parser. No blank may be
filled from an estimate, and there is no speed floor.

## Publication boundary

A successful measurement still has zero website, quality, record, serving, or
submission authority. Before these graph-on q8_0-KV cells can be published, a
separately frozen receipt must certify graph-off/on exact-output parity and the
q8_0-KV-specific quality battery on the same model, build, and KV identity. The
F16 parent is not that quality gate. Graph-on cells are append-only; the existing
graph-off curve and all featured speeds remain immutable.

After every placeholder is sealed and the committed packet is reviewed, the
execution acknowledgement is:

```text
RUN qwen36-q8-q8kv-tp1-fa0-graph-exact-depth-20260825-r1
```

The create-only root is:

```text
/mnt/fast-ai/bench-results/qwen36-q8-q8kv-tp1-fa0-graph-exact-depth-20260825-r1
```
