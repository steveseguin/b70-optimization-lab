# Qwen3.8-27B Q8 TP2: per-subgraph SYCL graph cache is safe but negative

Date: 2026-08-17 EDT

Status: **rejected; do not retry this granularity unchanged**

## Intent

The accepted target-only TP2 decode executes 516 per-device backend graph
computes for a one-token `llama-bench` process and roughly 1,674 device kernel
submissions per token.  Command graphs were the remaining mechanism with a
plausible double-digit upside after the smaller kernel and collective changes
had converged.

Earlier ordinary graph recording failed because a TP2 scheduler event from the
execution queue became an external dependency of the first recorded node.
Forcing native recording was unsafe and caused a device-lost/reset storm; it
must never be retried.  A later isolated-recording-queue prototype cleared the
external-event error but hit a forbidden `queue::wait()` while growing the Q8
activation memo.

## Materially different candidate

Patch: `../patches/q8-tp2-sycl-graph-cache-negative-20260817.diff`

Apply the intentionally context-minimal artifact from the accepted source root
with `git apply --unidiff-zero <path-to-patch>`.

Relative to the accepted DP4A2 x SG24 source, this candidate:

1. records on a fresh in-order queue in the same context, then submits the
   executable graph on the normal in-order execution queue;
2. rejects prompt/multi-row matrix graphs and keeps prefill eager;
3. reserves sixteen 64 KiB Q8 memo buffers before recording, so the recording
   region can never execute the memo growth drain;
4. caches one executable graph per stable per-device subgraph UID instead of
   repeatedly replacing an unrelated topology; and
5. releases that host-side cache before the backend context and queues are
   destroyed.

It was built with the same oneAPI 2026.1.1 BMG-G31 AOT configuration, except
for the required `GGML_SYCL_GRAPH=ON`. Runtime additionally set:

```text
GGML_SYCL_ENABLE_GRAPH=1
GGML_SYCL_GRAPH_RECORD_QUEUE=1
```

`SYCL_GRAPH_FORCE_NATIVE_RECORDING` was not set and must remain unset.

## Results

Model and quality configuration were unchanged: Qwen3.8-27B Q8_0 target,
F16 K/V, flash attention, two B70s, tensor split `1/1`, no speculation.

| Test | Candidate tok/s | Accepted reference | Interpretation |
|---|---:|---:|---|
| `p0/n1/r1` | 13.982698 | about 36.77 | first-token construction cost is prohibitive |
| `p0/n16/r1` | 24.554824 | about 36.77 | steady updates remain about 33% slower |

Both tests completed within their bounds, retained the expected fusion and Q8
dedup census, reported zero verification mismatches, and left both GPUs in
`normal` state with no new Xe fault/reset/hang. Raw logs are retained locally
under `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-graph-cache/`.

The `n16` process reported 4,386 backend graph computes.  Re-recording and
updating hundreds of very small command graphs every token costs more than the
kernel submissions it replaces.  This is not a warmup-only loss.

## Do-not-repeat boundary and next implication

Do not retry per-meta-subgraph ordinary command graphs, isolated queue plus
memo preallocation, or native recording.  A future graph attempt would need a
larger stable capture unit and a way to update token-varying scalar arguments
without re-recording hundreds of graphs. Cross-device collectives prevent the
current per-device command graph from simply spanning the full token.
