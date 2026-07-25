# Laguna M8 in-process replay: second launch abort

Date: 2026-07-24 America/Toronto

Status: **ZMQ path-length abort before engine workers, weight loading, or
generation**.

Sealed root:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-inprocess-replay-c0255cc1e-8cf58ed0f-20260724T235918Z
```

The repaired 41-key environment contract passed. During q1 `LLM`
construction, vLLM rejected its first IPC bind:

```text
zmq.error.ZMQError: ipc path ... is longer than 107 characters
```

The runner's unique 12-hex RPC tag made the projected socket pathname 114
characters after vLLM appended its 36-character UUID. No EngineCore or worker
started, no model weights loaded, no generation ran, and the eager and graph
arms were never attempted. The post-arm worker report was empty and strict
post-idle proof passed.

The sealed root is an abort artifact only. It carries no timing, correctness,
or performance evidence and must not be reused.

Disposition: retain uniqueness but shorten the RPC leaf to eight hash
characters plus a one-character arm identity, and fail preflight unless the
projected UUID-appended pathname is at most 107 characters. Commit the repair,
then use a new run root.
