# Nonspeculative M=1 Intel PTI attribution cross-check

Date: 2026-07-20

## Numbers first

**Verdict: CONFIRMS.** A stable host-only Intel PTI GPU `unitrace` capture
measured a median **70.458 effective Level Zero submission boundaries** and
**10.792 command-list host synchronizations per rank/token**, matching the
prior hand counters at approximately 70/10. The directly traced nonblocking
Level Zero API cost is only **0.430 ms/token**. There is no new independently
removable bucket at or above `0.5 ms/token`.

The trace used 24 steady decode intervals from one active generation. Mean
stream interarrival was `21.8625 ms`, close to the normal 43-44 tok/s lane;
the request completed 64 tokens with `cached_tokens=0`.

| Removable-overhead bucket | ms/token | Evidence and interpretation |
|---|---:|---|
| CPU/host submission and scheduler gap | `3.005` | `2.510` directly observed time with no Level Zero API active, plus `0.496` profiler-invisible scheduler/window-edge residual; reconciled inside the established `3.435` outer host bucket |
| Level Zero submit/sync active time | `0.430` | median nonblocking host API sum across four ranks |
| oneCCL live critical-path allocation | `2.746` | production-cycle additive allocation; PTI's inclusive long wait is `18.925` and is a non-additive, distortion-prone upper bound |
| Per-kernel device overhead above the `7.270` weight floor | `9.431` | same-identity device-event fallback: `2.819` weight-kernel slack + `3.310` norm/MHC/RoPE/KV/misc + `1.842` non-GEMM MoE + `1.460` sparse attention |
| **Rounded removable total** | **`15.612`** | established total is `15.611`; `0.001` is display rounding |

The full noncollective device-kernel time represented by the last row plus the
floor is `16.701 ms/token`. The PTI kernel-timestamp mode did not produce an
independent valid device decomposition; its failure and the fallback are
preserved below.

## Tracer and bounded fallback

VTune was absent (`intel-oneapi-vtune` is removed). The selected tool was the
already built Intel PTI GPU `unitrace` 2.4.0 at commit
`a5bab309f4ffdd78bd127035c46f5f75371160f8`, built with Level Zero support.
It was the fastest available professional Intel tracer and supports temporal
pause/resume collection across child processes.

Two negative modes were preserved:

1. Wrapping the outer launcher caused profiler-instrumented helper processes
   and stalled worker startup for more than three minutes after weight load.
   Raw run:
   `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/nospec-unitrace-crosscheck-20260720T140738Z`.
2. Wrapping only vLLM with host calls plus device kernel timestamps reached a
   normal warmed `43.82 tok/s`, but enabling the 24-token trace serialized
   progress, printed `Unable to query event for timestamps`, and killed a
   worker after about 43 model steps. It produced no valid kernel timeline.
   Raw negative:
   `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/nospec-unitrace-crosscheck-20260720T141436Z`.

The final bounded fallback wrapped only the vLLM executable and enabled
host-only Level Zero timing/call tracing after the first streamed token. It
paused after 24 further token intervals, let the sole request finish, then
stopped and flushed on clean service exit. This avoided timestamp-event
injection into oneCCL and preserved normal decode speed.

Valid raw run:

`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/nospec-unitrace-host-crosscheck-20260720T141855Z`

Primary files:

- `host-trace-summary.json`: four-rank parsed attribution;
- `profile-request.json`: one-generation control times, interarrival series,
  usage, output hash and trace-control acknowledgements;
- `unitrace/python.1655724/chrome_trace.json` through rank process 1655727:
  raw Level Zero call timelines;
- matching `host_timing.txt` files: Intel PTI API counts and durations;
- `server.log` and `identity.txt`: startup/runtime identity;
- `warmup.json`: unprofiled warmed check at `43.9547 tok/s`, cache-zero.

## Configuration confirmations

The valid fallback launch retained the requested exact source and model
identity: vLLM `a681dbb2b4b19c2c5a964817095b5f8c1f27ff48`, XPU kernels
`6522849b02894273b1e779b3c115527b5cdf3756`, oneCCL
`48fda4f0e074db005596d6899d5227d3f0316c12`, and K160 revision
`7c360e1cd4a5168099dbc54d16d929bf6df04990`. Speculation was absent.

1. Async scheduling was enabled. Exact startup line:

   ```text
   (APIServer pid=1655135) INFO 07-20 10:19:21 [vllm.py:1090] Asynchronous scheduling is enabled.
   ```

2. Runtime `enforce_eager=False`; the resolved engine config contains
   `'cudagraph_mode': <CUDAGraphMode.FULL_AND_PIECEWISE: (2, 1)>`, and the
   live capture line is:

   ```text
   (Worker_TP0_EP0 pid=1655724) Capturing CUDA graphs (mixed prefill-decode, PIECEWISE)
   ```

   `identity.txt` independently records `enforce_eager=0` and
   `compilation_config={"cudagraph_mode":"PIECEWISE"}`.

3. The all2all backend was **`allgather_reducescatter`**. The exact resolved
   argv in `identity.txt` contains:

   ```text
   --enable-expert-parallel --all2all-backend allgather_reducescatter
   ```

## Submission and wait cross-check

Across the four rank traces, median counts per token were:

- `1.000` literal `zeCommandListImmediateAppendCommandListsExp` graph submit;
- `70.458` effective boundaries when graph submit, kernel appends, memory-copy
  appends and signal appends are counted using the prior definition;
- `10.792` `zeCommandListHostSynchronize` calls;
- `1.000` long progress-thread `zeEventHostSynchronize` per token at the
  median (rank 0 had two). This event wait overlaps the long oneCCL-associated
  memory-copy scope and is not an extra additive bucket.

The effective-boundary result is within `0.7%` of the prior 70 count. The
command-list synchronization result is within one call/token of the prior 10;
window edges explain the rank range `9.833-11.000`.

PTI observed a median `18.925 ms` inclusive long
`zeCommandListAppendMemoryCopy` / paired `zeEventHostSynchronize` wait. It
encloses downstream device progress and almost the full token cycle, so it is
only an upper bound and cannot be added to the device or host rows. This is
exactly the profiler interpretation pitfall anticipated for oneCCL.

The useful independent values are therefore the counts, the `2.510 ms/token`
no-Level-Zero host gaps, and the `0.430 ms/token` nonblocking Level Zero API
cost. The latter agrees with the prior `0.5165 ms/token` submit/sync-active
measurement and is below the `0.5 ms/token` new-bucket gate. The remaining
`0.496 ms/token` scheduler/window-edge residual is not new: it was already
inside the hand-attributed worker/scheduler/metadata host bucket.

## Conclusion and recommendation

The professional host trace confirms the structural diagnosis: roughly 70
Level Zero boundaries and roughly 10 command-list syncs are real, but their
direct API active cost is small. The prior exact native K=2 experiment's
`0.9256 ms/token` same-suite recovery is credible; merging submission calls
does not expose a missed multi-millisecond host-API prize. The dominant open
boundary remains the ungraphable oneCCL/host-coordination transaction, while
the largest additive device opportunity remains the already known per-kernel
overhead above the weight floor.

Recommendation: **do not start another submission-fusion optimization from
this trace**. Retain the native fixed-geometry decoder direction only as the
documented warm-captured architectural lane, and require a tracer/runtime fix
before treating Intel device-timestamp collective durations as additive.

No LocalMaxxing submission was made. No frozen held-out pack was opened or
modified.
