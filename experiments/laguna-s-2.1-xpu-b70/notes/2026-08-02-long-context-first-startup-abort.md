# Laguna 32K first startup abort

Date: 2026-08-02 America/Toronto

The first preregistered candidate start produced no model worker, request, or
performance row. The API process accepted the intended identity:

- `max_model_len=32768`;
- `max_num_batched_tokens=8192` with chunked prefill enabled;
- BF16 KV, utilization 0.90, prefix caching off, one sequence;
- M12/DFlash11, synchronous candidate scheduling, and PIECEWISE breakable
  graph mode.

It then failed before engine-core creation because the new runner derived the
ZeroMQ IPC directory from the full descriptive run name. The resulting Unix
socket path exceeded the 107-character `sockaddr_un.sun_path` limit:

```text
zmq.error.ZMQError: ipc path ... is longer than 107 characters
```

Sealed evidence:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-long-context-mbt8192-baseline-20260802T170236Z
```

Cleanup reported `original_status=2`, `stop_status=0`; no vLLM worker or port
listener survived and all GPUs returned idle. This is a harness-path abort,
not a model, XPU, oneCCL, memory-capacity, correctness, or performance result.

The runner now uses a fixed short `l<6-hex-hash>` RPC directory. Its complete
future socket path, including vLLM's UUID, is preflighted below the platform
limit while the full run identity remains in the sealed artifact root. No
service, model, kernel, benchmark, or measurement setting changed.
