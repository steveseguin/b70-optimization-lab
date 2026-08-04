# Host attribution by sampling: where the fixed per-step cost actually sits

Date: 2026-08-04 America/Toronto

Status: **measured with py-spy on a warm worker, no code change. First direct
host-side attribution of the fixed ~27-34 ms decode step
([`2026-08-04-FINDING-decode-is-a-fixed-per-step-cost.md`](2026-08-04-FINDING-decode-is-a-fixed-per-step-cost.md)).**

## Why sampling rather than tracing

The torch profiler cannot attribute this cost: its spans contain the waiting
they would need to explain. `execute_context` reports 59.99 ms against a
measured 27.9 ms step, and `c10d::_allgather_base_` reports 12.17 ms that is
provably not causal, since removing 95% of its bytes moved decode by -4.6%.

`py-spy` samples the interpreter stack at 250 Hz and attributes wall clock
directly. It needs no rebuild and no instrumentation, so it cannot distort what
it measures. 5,678 samples over 60 s on the warm 32,640-token case.

## Result

| % of wall | frame | location |
| ---: | :--- | :--- |
| **27.6%** | `copy_to_gpu` | `vllm/v1/utils.py:142` |
| **13.7%** | `_xpu_apply_batched_m1_method` | `linear.py:198-199` |
| 4.9% | `all_gather_into_tensor` | `distributed_c10d.py:4316` |
| 4.2% | `_apply_kernel` | `fused_moe_interface.py:1261,1328` |
| 2.4% | `load_binary` | `driver.py:217` |
| 2.4% | `capture_end` | `graphs.py:94` |
| 2.0% | `parse_output` | `rejection_sampler.py:267` |
| 1.7% | `replay` | `graphs.py:107` |

Two frames account for **~41% of decode wall time**, and neither is model
compute.

## What `copy_to_gpu` is, and what it is not

```python
def copy_to_gpu(self, n=None):
    return self.gpu[:n].copy_(self.cpu[:n], non_blocking=True)
```

A host-to-device copy from a pinned buffer. XPU reports
`is_pin_memory_available() == True`, so the buffers really are pinned, and a
standalone benchmark confirms the copy itself is asynchronous:

| payload | enqueue | copy + sync |
| ---: | ---: | ---: |
| 48 B | 2.36 us | 32.44 us |
| 4 KiB | 2.19 us | 30.74 us |
| 128 KiB | 3.24 us | 33.74 us |
| 1 MiB | 3.18 us | 56.10 us |

**The copy enqueues in 2-3 us. It is the synchronisation that costs ~30 us**, and
that cost is nearly independent of payload size -- 30 us for 48 bytes.

So time spent inside `copy_to_gpu` is not transfer time; it is the call blocking
on a device queue. That is the same shape as the collective finding: the frame
that appears expensive is where the process *waits*, not where the work happens.

## The ~30 us synchronisation quantum

This is the most actionable number here. A decode step issues roughly 268 kernel
launches and an unknown number of queue synchronisations. At ~30 us per
synchronisation, **fewer than a thousand syncs would account for the entire
25-31 ms of unexplained per-step cost**, and nothing about that scales with
context length, collective volume, or draft depth -- which is exactly the
insensitivity measured across every arm today.

## Caveats, stated plainly

- Leaf-frame attribution charges blocking to the blocking call. `copy_to_gpu` at
  27.6% means the process is *inside* that call 27.6% of the time, not that
  27.6% of the work is copying.
- The 60 s window includes some JIT (`load_binary`, `make_llir`, ~4%) and some
  teardown (`shutdown`, `_cleanup_profiling_kv_cache`, ~2.6%). Steady-state
  decode is the remainder.
- `_xpu_apply_batched_m1_method` at 13.7% is the M=1 linear path, i.e. the
  drafter's per-token projections. Note this sits **in tension** with the
  measured null result for draft depth 11 -> 7 (-0.6%): if the drafter's linears
  were causal, removing a third of them should have shown. Either the sampling
  window over-weights the 8K case, or that time is also blocking rather than
  work. It should not be acted on without a differential test.

## What to do with this

1. **Count and time the synchronisations per decode step.** At ~30 us each this
   is the leading candidate for the fixed cost, and it is directly measurable
   with a counter around `torch.xpu.synchronize` and the queue-blocking paths.
2. **Reduce sync points**, not bytes. Every optimisation tried today reduced
   bytes or work and moved nothing; the quantum here is per-synchronisation.
3. **Do not act on the `_xpu_apply_batched_m1_method` line without a
   differential test**, for the reason above.

## Boundaries

Warm server, cold prefix cache, TP4, util 0.80, q12, depth 11, sampled on rank 0
only. The H2D benchmark is standalone with no model loaded. No quantisation
change, no caching or speculation setting used to inflate any number. The
protected `125.4619731637751 tok/s` conventional short-decode record is
untouched.
