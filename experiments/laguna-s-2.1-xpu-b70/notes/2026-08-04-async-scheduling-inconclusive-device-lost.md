# Async scheduling: inconclusive, and it lost the device

Date: 2026-08-04 America/Toronto

Status: **attempted, no usable 32K measurement. The failure mode is worth
recording; the hypothesis remains open.**

## Why it was worth trying

The fixed ~27-34 ms decode step survives removing 95% of collective bytes and
36% of drafter work, so it is not volume. Sampling puts ~41% of decode wall
clock in host frames that block on the device queue (`copy_to_gpu` 27.6%, the
M=1 linear path 13.7%), and `torch.xpu.synchronize` costs **~30 us largely
independent of payload**.

If that host work is serialised against device execution, overlapping the two
recovers it. `--async-scheduling` does exactly that: it prepares step N+1 while
step N runs. The shared-elementwise contract forbids it outright ("async
scheduling is enabled"), so it had never been measured on this stack, and unlike
a drafter or kernel change it would have been a flag.

## What happened

| arm | 8,192 case | 32,640 case |
| :--- | ---: | :--- |
| `async_scheduling=0` | -- | benchmark exited with no rows |
| `async_scheduling=1` | 7.801, retrieval true | **`UR_RESULT_ERROR_DEVICE_LOST`** |

The async arm served the 8K case correctly, then lost the device on the 32K
case:

```
RuntimeError: level_zero backend failed with error: 20 (UR_RESULT_ERROR_DEVICE_LOST)
```

That left 80 orphaned GuC resets per minute with no process holding the render
nodes -- the documented wedge signature -- cleared by the usual unbind and
module reload.

The control arm is separately unusable: its benchmark exited producing
`status: RUNNING` with zero rows, and the harness reported silence because it
checked only that `bench.json` existed. That check now verifies the 32K row is
present.

## Reading it honestly

**This is not evidence that async scheduling is bad.** One arm never produced a
control, and the other died on the long-context case. Possible readings, none
established:

- async scheduling is genuinely incompatible with the breakable-cudagraph path
  on this stack, which would explain why the contract forbids it;
- the device loss came from the accumulated GPU state of a long session rather
  than from async scheduling;
- the two interact only at long context, since the 8K case completed cleanly.

Distinguishing them needs a fresh stack and both arms run to completion. The
8K arm completing at 7.801 with `retrieval_pass` true does at least show the
flag is not immediately fatal.

## Standing recommendation

Retry on a freshly rebooted host, control arm first, and treat a second
`DEVICE_LOST` at 32K as evidence the contract's prohibition is load-bearing
rather than conservative. If it survives, it is still the cheapest candidate for
the fixed per-step cost: no kernel work, no quality change, and scheduling
overlap cannot alter emitted tokens.

## Boundaries

Both arms ran with the M12 shared-elementwise selector and transposed decode
scales off, so absolute figures sit below the full stack; only async scheduling
differed between them. No quantisation change, no caching or speculation setting
used to inflate any number. No throughput figure is claimed from this
experiment. The protected `125.4619731637751 tok/s` conventional short-decode
record is untouched.
