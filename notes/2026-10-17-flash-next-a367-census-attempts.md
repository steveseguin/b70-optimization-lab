# Flash-Next A367 M=2 diagnostic census: device attempts, October 17, 2026

## Attempt 1: graph-census arm (seal `f9ba14c2`, run `a367c-20261017T002647Z`)

The approval was recorded from the owner's census pre-approval and the standing "decide on your own" instruction (`owner-approval-census-reseal.json`).

Before launch:

- payload receipt 00:33:23;
- health pass 00:33:33 (zero faults);
- launched 00:38:43 UTC with the record server profile (nice 0, CPUs 0-31, OMP=1) and the ITT unitrace, started paused.

| Time (UTC) | Event |
|---|---|
| 00:39:15 | Server started under the paused tracer |
| 00:49:58 | Weights loaded (554.7 s); all four ranks then reported `Model loading took` (673 s) at 00:51:47 |
| 00:51:47 | Tracer resumed and acknowledged (`trace-control.json`) |
| 00:51:57 | **All four workers SIGSEGV (address 0x140) in the profile run** |
| 00:52:14 | All owners gone (returncode 1); 305 s watch complete; **zero GPU fault lines** |

**Crash stack:** `ProcessGroupXCCL::initXCCLComm` → `ccl::create_communicators` → `ccl_comm::init` → `allocate_buffers` → `coll_init` → sycl wait → `urEventWait` → `libur_adapter_level_zero_v2` → **`libze_tracing_layer`** → `libze_intel_gpu` → SIGSEGV.

vLLM creates XCCL communicators lazily on the first collective. That happened in the profile run, after the resume. **Creating a oneCCL communicator while the L0 tracing layer is active crashes the driver.** The CCL microtest missed this because it resumed after its first all_reduce, so its communicator was created while paused.

A one-card event-wait check at 00:57 (v2 and v1 adapters, traced and untraced) passed, so a plain `urEventWait` under tracing is fine.

**Next.** Resume through a rendezvous at `capture_model` entry, after profiling has created every communicator and before any graph capture, with a source audit for later communicator creation. Plus a microtest step that creates the communicator after resume, to confirm the cause cheaply.

Evidence: `data/2026-10-17-flash-next-a367-census-reseal/window-20261017T002647Z/run/` (`server-crash-excerpt.log.gz`).
