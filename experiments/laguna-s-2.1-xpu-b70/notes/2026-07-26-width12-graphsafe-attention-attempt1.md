# Laguna width-12 graph-safe attention: attempt 1 harness rejection

Date: 2026-07-26 America/Toronto

Status: **no device execution; candidate not classified**.

Artifact:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m12-attngraph-20260726T181050Z
```

The measurement leg completed model verification and the 60-second strict idle
interval, wrote a complete identity, and then the serve wrapper rejected
startup with:

```text
VLLM_XPU_LAGUNA_M8_CAPTURE_ATTENTION_GRAPHS must be 0
```

This was a stale wrapper preflight, not a kernel, graph, model, collective, or
correctness result. The measurement leg had been widened to pass the new
default-off selector, but its width-parameterized serve wrapper still pinned
that selector to zero.

Cleanup passed completely: no service or worker survived, the port was free,
and the failure-post idle snapshot passed. The sealed artifact is not reusable.

The repair accepts `0|1` at the wrapper boundary and independently rejects the
still-unvalidated combination of attention subgraphs with prebuilt metadata.
The next attempt must use a fresh artifact root.
