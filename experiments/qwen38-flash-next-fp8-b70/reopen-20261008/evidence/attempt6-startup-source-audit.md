# Attempt 6 startup-memory source audit (CPU only, 2026-10-08)

Attempt 5 failed before model construction. Its log reports 30.3 GiB total,
27.65 GiB currently usable on rank 0, and 27.87 GiB on ranks 1–3. Those are
rounded source-reported values, not exact byte totals. The resulting unavailable
amounts are approximately 2.65 and 2.43 GiB respectively. The original unrounded
bytes were not retained in the failure message.

## Startup sequence and meaning of the counters

Local V30 source root: `/home/steve/src/lumnus-20261008/vllm/`.

- `vllm/v1/worker/xpu_worker.py:133–139` selects the XPU, checks the dtype,
  empties the allocator cache and reads device properties.
- Lines 143–157 set distributed environment defaults and initialize distributed
  groups. Lines 159–166 perform the oneCCL warmup all-reduce for TP4.
- Lines 174–180 collect garbage, empty the cache again, take `MemorySnapshot`,
  and call `request_memory`. Workspace initialization and model-runner
  construction follow at lines 186–194. Thus the startup difference cannot be
  assigned to this model's weights, KV, captured graphs or activation workspace.
- `vllm/utils/mem_utils.py:138–159` reads allocator statistics and
  `torch.accelerator.get_memory_info`; it distinguishes allocator reservation
  from the difference between total and usable memory.
- `vllm/platforms/xpu.py:93–100` replaces that API with
  `torch.ops._C_cache_ops.getMemoryInfo`.
- Native source
  `/home/steve/src/lumnus-20261008/vllm-xpu-kernels/csrc/utils/mem_info.cpp:7–22`
  sums `zeDeviceGetMemoryProperties.totalSize` for total memory. Lines 25–49
  get free memory from the Level Zero extension field
  `ZE_STRUCTURE_TYPE_DEVICE_USABLEMEM_SIZE_EXT_PROPERTIES.currUsableMemSize`.
  This is driver-reported currently usable memory, not a sysman physical-memory
  allocation ledger.
- `vllm/v1/worker/utils.py:539–551` compares unrounded free bytes against
  `ceil(total_bytes * gpu_memory_utilization)`. The message rounds both sides
  to two decimal places, explaining why ranks 1–3 print `27.87 < 27.87`.

Read-only `git diff` verified that these four Python source files match official
V30 commit `ced6857afa0ea7b2e3f0846a62e1394e90f15607`; the native memory-info
file matches official kernel commit `6d92b1bfbf32767ecda8e819613eb151e70030ad`.

## Attempt 5 receipts and attribution limit

Paths below are relative to this lane directory's
`runs/screen1b-mmap-calibrate-load-20261008-attempt5/`:

- `server.log:115,134,153,175` contain the rank 3,0,1,2 startup failures.
- `launch.json` explicitly supplies `CCL_SYCL_ALLGATHERV_TMP_BUF=1` and
  `CCL_SYCL_ALLREDUCE_TMP_BUF=1`, together with
  `NEOReadDebugKeys=1 EnableDeferBacking=0`. `server.log:73–96` confirms the
  collective settings, OFI transport and PCIe topology.
- `launch.json`, `image-inspect.json`'s image environment, and the lane's
  `container-entrypoint.sh` contain no explicit reserve-VRAM flag or setting.
- `host-memory-samples.jsonl` has null per-card VRAM fields because this host
  did not expose the requested `mem_info_vram_total` sysfs files.

Driver usable-memory accounting, initialized device contexts and collective
buffers all precede this snapshot. There is no before/after collective memory
receipt to split the approximately 2.4 GiB among them. The TMP flags can affect
collective buffers, but assigning an exact number to them would invent evidence.
Neither lowering utilization nor additional host offload removes that startup
cost. At the rounded total, 0.90 corresponds to about 27.27 GiB; actual admission
continues to use the unrounded device total.

## Certified A367 comparison

Archive root:
`/home/steve/git-archives/flash-next-rescue-20261007/qwen38-flash-next-fp8-tp4-ep4-fullgraphdet-mtp1-4352-ple-only-r1-attempt367/`.

- `server-command.shell.txt:1` specifies utilization **0.92**, KV budget
  **376,569,856 bytes**, generic offload **12.25 GiB**, maximum context **4,352**,
  prefill chunk **64**, and decode graph capture sizes **1,2**.
- `server.log:563–566` gives initial free memory **28.62 GiB rank 0** and
  **28.85 GiB ranks 1–3**, approximately **0.97–0.98 GiB more** than attempt 5.
  These lines do not provide the unrounded free bytes or total device memory.
- Those lines explicitly say the manual KV budget skips memory profiling and
  does not respect `gpu_memory_utilization`. Lowering utilization is an admission
  change, not a hard total-allocation limiter when this KV budget is explicit.
- `server.log:548,551,554,555` reports model-loading allocation deltas of
  **29.38, 29.57, 29.54, 29.37 GiB** for ranks **3,0,2,1** respectively.
- `runtime-versions.txt` identifies Torch **2.11.0+xpu**, vLLM
  **0.20.2rc1.dev2+gc51df4300.d20260523.xpu**, and kernels
  **0.1.9.dev33+g3b4effe.d20260705**.
- `server.log:77–120` records different collective tuning, including 4 GiB
  simple thresholds, twoshots, direct send/receive and a P2P override. Different
  runtime, driver state and collective settings prevent attributing the extra
  roughly 1 GiB in attempt 5 to a single option.

The historical model-loading number is not the startup usable-memory counter.
Surviving source under `/mnt/fast-ai/qwen38-build/vllm-q38-hc-silu-a1-src/`
shows `vllm/v1/worker/gpu/model_runner.py:400–426` using `DeviceMemoryProfiler`;
`vllm/utils/mem_utils.py:86–102` subtracts before/after platform allocation
readings, while `vllm/platforms/xpu.py:450–456` returns
`torch.xpu.max_memory_allocated()` after resetting its peak. This surviving
source explains the counter mechanism; it is not a freshly reconstructed,
hash-bound A367 environment. The 29.38 GiB log is not a physical-VRAM peak and
cannot establish that V30 can fit that allocation into 27.65 GiB currently
usable memory. Exact A367 physical residency remains unknown.
