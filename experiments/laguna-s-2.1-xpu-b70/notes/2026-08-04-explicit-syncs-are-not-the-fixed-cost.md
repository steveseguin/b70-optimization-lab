# Explicit synchronisation is not the fixed per-step cost

Date: 2026-08-04 America/Toronto

Status: **measured. Refutes the leading hypothesis from
[`2026-08-04-host-attribution-by-sampling.md`](2026-08-04-host-attribution-by-sampling.md).
Recorded so nobody builds the copy-batching optimisation it implied.**

## The hypothesis

Sampling put **27.6%** of decode wall clock inside `copy_to_gpu`
(`vllm/v1/utils.py:142`), whose copy enqueues in 2-3 us standalone, and a
standalone benchmark put `torch.xpu.synchronize` at **~30 us largely
independent of payload** (30 us for 48 bytes, 56 us for 1 MiB).

That suggested a synchronisation quantum: at ~30 us each, **800-1000 syncs per
step** would account for the entire fixed 25-31 ms that survives removing 95% of
collective bytes and 36% of drafter work. The implied fix was batching the
per-step `CpuGpuBuffer` copies so one sync covers many.

## The measurement

A counter wrapped around `torch.xpu.synchronize` at worker init, default off,
logging count and time every 5 s. All four workers instrumented, warm 32,640
case, server healthy throughout:

```
LAGUNA_SYNC_COUNT calls=1 total=0.000s mean=380.4us rate=0.0/s
LAGUNA_SYNC_COUNT calls=1 total=0.000s mean=381.6us rate=0.0/s
LAGUNA_SYNC_COUNT calls=1 total=0.000s mean=452.6us rate=0.0/s
LAGUNA_SYNC_COUNT calls=1 total=0.001s mean=989.5us rate=0.0/s
```

**About one explicit synchronisation per five seconds**, against roughly 30
decode steps per second. That is **~0.007 syncs per step**, not 800-1000. The
hypothesis is dead by three orders of magnitude.

## What this means

The blocking that sampling observed inside `copy_to_gpu` is **implicit** -- the
call waiting on the device queue inside `Tensor.copy_` -- not an explicit
`torch.xpu.synchronize()`. So:

- **Do not build the copy-batching change.** Its entire premise was reducing a
  sync count that is already negligible.
- The ~30 us figure from the standalone benchmark is real but irrelevant here:
  the serving path is not calling it.
- The fixed 25-31 ms per step remains **unexplained**. Sampling localises *where
  the process waits*; it has not identified *what it waits for*.

## Where that leaves the search

Excluded by direct measurement across this session: memory bandwidth (595 GB/s),
compute (153 TFLOP/s per GPU), PCIe (28.7 GB/s), collective transport (69% of
PCIe), collective volume (20x reduction, -4.6%), draft depth (36% reduction,
-0.6%), GPU clocks (2%), and now explicit synchronisation (~0.007/step).

What has not been examined: what the device queue is actually waiting on when
`copy_` blocks. That is a Level Zero / SYCL queue question rather than a Python
one, and the tools used so far -- torch profiler, py-spy, differential
end-to-end -- cannot see it. `unitrace` or `ze_tracer` at the driver level
would.

## A note on method

This is the fourth hypothesis this session that survived reasoning and died on
measurement -- after MoE all2all volume, draft depth, and async scheduling. The
pattern holds: sampling and tracing identify *where time is spent*, which is not
the same as *what causes it*. Only changing a thing and measuring end to end has
settled anything here.

## Boundaries

Warm server, cold prefix cache, TP4, util 0.80, q12, depth 11, all four workers
instrumented. The counter is default off (`VLLM_XPU_LAGUNA_SYNC_COUNT=1` to
enable) and wraps only `torch.xpu.synchronize`; implicit queue waits inside ATen
operations are by construction invisible to it, which is precisely the finding.
No quantisation change, no caching or speculation setting used to inflate any
number. The protected `125.4619731637751 tok/s` conventional short-decode record
is untouched.
