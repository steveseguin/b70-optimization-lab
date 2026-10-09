# Flash-Next exit lifecycle analysis — 2026-10-09

**The two tiny probes strongly implicate the exit boundary, but neither proves
that a pinned slab was still mapped there. All four incidents are not proven
instances of one teardown bug.** The host-UMD comparison also faulted, so NEO
26.27 versus 26.18 is not the discriminator. Closed-VM teardown is the leading
probe hypothesis; confidence in the particular live-host-USM/blitter explanation
is lower. CPU analysis and preparation only; **GPU launches remain halted**
after the second incident of boot `4aafe57b`, pending the owner's decision.
No GPU APIs, installs, host settings, protected model storage or LTX edits were used.

## Four-incident evidence (UTC)

Paths in this table are under `../reopen-20261008/runs/`; original receipts were read only.

| Incident | Ordering in saved evidence | Fits abrupt exit with live mappings? |
|---|---|---|
| Screen 1, Oct 8, 14:04 | BCS `-EBUSY` at **14:04:34.984196**; first OOM victim at **14:04:45.026078**; worker OOM at **14:04:51.878504**. `screen1b-mmap-calibrate-load-20261008-attempt7/kernel-latest.log` lines 3452, 3734, 5443 preserves this earlier boot window. The dedicated Screen 1 window file is empty. | **Not as an OOM-initiated fault.** First fault precedes even the first logged OOM kill by 10.042 s, the worker kill by 16.894 s. Later teardown may contribute further faults. |
| Attempt 7, Oct 8, 21:11 | First CCS fault detail **21:11:18.369060**, `-ENOENT` .371641, reset .385005 (same kernel log lines 5459, 5467, 5697). `server.log:347` last timed progress 21:11:18; untimed segfault stacks at 348/402/456/510; worker death reported **21:12:07** at 564, startup failure 21:12:56 at 566. | **Unresolved, not established.** No timestamped worker death precedes the first fault. Untimed segfaults prevent a strict causal ordering. This was startup/first-forward work, unlike probe post-readback exit. |
| Image NEO 26.27 probe, Oct 9 | `probe-indirect-20261009/receipt.json`: exact bytes, gather 1, sync 1, clean watcher updated **01:39:27.134629**, worker wait status 0. Kernel detail **01:39:27.868140**, BCS `-ENOENT` .868476, reset .868648 (`kernel-latest.log:2268`). Guardian postflight requested **.868464**. | **Strong exit-boundary association.** No exact exit-instruction timestamp or allocation-lifetime trace. |
| Host NEO 26.18 probe, Oct 9 | `probe-indirect-hostumd-20261009/receipt.json`: same bytes/gather/sync/status, `FLASHNEXT_PROBE_UMD=host-26.18.38308`; clean watcher updated **02:27:31.555379**. Kernel detail **02:27:32.185140**, BCS `-ENOENT` .185435, reset .185617 (`kernel-latest.log:2278`); guardian postflight **.185534**. | **Same strong association across UMDs.** Other image layers and kernel remain shared. |

Both probe fault addresses (`0xd556a74c0000`, `0xd556aa350000`) differ from all
recorded slab/UVA and device-buffer spans. These are not identified slab accesses.
Watcher update/read times are sampling boundaries, not a continuous clean trace;
`waitpid` completion is an exit proxy, not the exact `os._exit` instruction time.

## What actually survives the original worker

[Probe source](../reopen-20261008/probe/single_rank_slab_probe.py): child imports
Torch/Triton, allocates a 3 MiB pinned CPU slab, interior CPU view and native UVA
wrapper; resident/table/output device buffers; CPU source/table readback/output.
`operands` aliases device tensors; the metadata loop's `tensor` aliases UVA.
The direct variant additionally owns row/selector buffers (neither receipt used it).
`run_device` **returns before `os._exit(0)`**. CPython drops all these local
references, including aliases and the local compiled-kernel/stream wrappers.
Thus “os._exit with all local tensors still live” is incorrect.

What may remain is native device allocation cache, small pinned cache/event
state, Triton's global compiled module/function cache and SYCL/UR/L0-owned
queues/context/driver allocations. Their destruction was not instrumented.
The 3 MiB slab is above the explicit 1 MiB pinned-cache limit: the exact image's
`torch/include/ATen/core/CachingHostAllocator.h:351–413,735–761` records events
at free if streams were registered, otherwise destroys an over-limit block
immediately. It does **not** justify assuming the slab stays cached. Native
UVA USM kind was unavailable in both receipts; pinned flags are not that query.
The image's `vllm/utils/torch_utils.py:915–931` delegates the already-pinned
view directly to `_C.get_xpu_view_from_cpu_tensor`, without another Python pin.

Gather uses the recorded current queue and completes its explicit device sync;
table/output `.cpu()` transports are blocking. No user payload copy is shown
pending. Free-time allocator event recording could enqueue markers *after*
that sync, but this probe never explicitly registers a host stream; internal
transport events/staging remain untraced. Triton warmup/IR/cache writes precede
gather and are CPU filesystem writes, not BCS transfers. Runtime-internal ring
or semaphore activity is a more concrete remaining possibility than cache I/O.

## Mechanism and confidence

Host module: `/lib/modules/7.0.0-39-generic/kernel/drivers/gpu/drm/xe/xe.ko.zst`,
`srcversion=992B74FB6C5940A1403864D`, SHA256
`3c83b8f45038ec66e9447e709bea3884fdd7088237ea84d0253729c2ef203a6c`.
`modinfo`/installed docs identify `7.0.0-39.39~24.04.1`; only -38 headers were
available, no matching Xe C source. No package/source installation was attempted.

- **Strong source analogy, medium confidence for this binary:** upstream
  [v7.0 xe_pagefault_service](https://github.com/torvalds/linux/blob/v7.0/drivers/gpu/drm/xe/xe_pagefault.c#L132-L197)
  returns `-ENOENT` for a VM already marked closed; missing ASID/VMA uses
  `-EINVAL`. This strongly suggests a closed-VM fault response, not proof that
  the faulting instruction first ran after close. The distro source is unverified.
- [File close](https://github.com/torvalds/linux/blob/v7.0/drivers/gpu/drm/xe/xe_device.c#L155-L178)
  kills/puts execution queues before `xe_vm_close_and_put`.
  [VM close](https://github.com/torvalds/linux/blob/v7.0/drivers/gpu/drm/xe/xe_vm.c#L1595-L1736)
  marks the VM closed, waits binds, clears page tables/TLB and releases mappings.
  Do not describe this as a proven kernel “unmap before queue kill” bug.
- **Plausible abrupt-exit trigger:** NEO
  [26.18.38308.4 L0 cleanup](https://github.com/intel/compute-runtime/blob/26.18.38308.4/level_zero/core/source/device/device.cpp#L1469-L1486)
  stops direct submission before releasing resources. Its
  [ring lifecycle](https://github.com/intel/compute-runtime/blob/26.18.38308.4/shared/source/direct_submission/direct_submission_hw.inl#L195-L281)
  can idle on an internal semaphore; stopping unblocks and waits for completion.
  `_exit` bypasses native finalization. An idle ring can therefore explain BCS
  activity without unfinished payload copies. Ring activation/address ownership
  here is **unmeasured**; this source tag is an analogue, not the host package pin.
- The [Level Zero free contract](https://github.com/oneapi-src/level-zero-spec/blob/master/scripts/core/memory.yml#L194-L203)
  requires callers to finish device references before freeing memory. It is a
  lifetime obligation, not evidence that these calls violated it.
- [Intel issue #967](https://github.com/intel/compute-runtime/issues/967) reports
  a B70 exit hang in direct-submission shutdown after overcommit. Relevant path,
  different symptom/workload/kernel; no reviewed issue proves this exact fault.

LTX's three fault-free server lifetimes are a useful **unmatched** control.
Read-only `experiments/ltx25-b70/recovery/20261008-continuation117-stream/launch-117.sh:27–29`
uses the host venv, `Restart=no`, `SendSIGKILL=no`, SIGINT, 180 s timeout and
`env --default-signal=INT`. `stream/ltx_continuation_client.py:485–491,1600`
drains on first signal and uses `sys.exit(main())`. The actual GPU-server target
is under prohibited model storage and was not read; complete server finalizers
and equivalent USM ownership are not established by the accessible launcher.

## Prepared discrimination, not executed

[Probe README](../reopen-20261008/probe/README.md#exit-lifecycle-discrimination--prepared-not-executed)
contains the full interpretation table. `--clean-exit` keeps allocation/gather/
readback unchanged, explicitly drops aliases and output/table/resident/UVA/view/
slab, collects garbage, synchronizes, flushes device cache and the available
public `torch.accelerator.empty_host_cache()`, then normal `sys.exit(0)`.
The latter API was read in image `e4446310b1d3`'s `torch/accelerator/memory.py:35–42`
without importing Torch. Global compiled modules/queues still depend on runtime
finalization. `after_free` records completed release calls, not zero mappings.
`--exit-after-sleep N` idles **after original local-reference release**, then
abruptly exits: same boundary, shifted time. Range 0–30 s; modes mutually exclusive.

Both record UTC/Unix/monotonic lifecycle timestamps, including before-return,
after-free (clean), before-exit, and sleep boundaries; cleanup sync is separate.
Guardian, fresh post-exit watcher read, 120 s alarm, 150 s watcher and stop rules
remain. Error/alarm paths are inconclusive and retain abrupt fail-stop behavior;
there is no automatic second arm, retry, health launch or boot-marker removal.

Prepared commands **only print**; do not execute the output while launches are halted:

```sh
probe=experiments/qwen38-flash-next-fp8-b70/reopen-20261008/probe
bash "$probe/run-probe-in-container.sh" --render-node /dev/dri/by-path/pci-0000:23:00.0-render --health-receipt /PATH/FRESH-HEALTH.json --receipt-dir /PATH/NEW-CLEAN --clean-exit
bash "$probe/run-probe-in-container.sh" --render-node /dev/dri/by-path/pci-0000:23:00.0-render --health-receipt /PATH/FRESH-HEALTH.json --receipt-dir /PATH/NEW-SLEEP --exit-after-sleep 10
```

Hold image UMD and all other settings fixed. Clean clean + abrupt fault supports
teardown; both fault leaves allocation/mapping/runtime class open (including
teardown if clean finalization itself faults); both clean means flaky/other.
Sleep clean until exit strengthens exit causality; fault before exit disproves
exit as a necessary trigger. Neither one clean arm nor this CPU work certifies a fix.

## Conditional production changes — design only, overlay untouched

Paths below are relative to `../reopen-20261008/`.

| Exact place | Existing behavior; conditional change if teardown is confirmed |
|---|---|
| `container-entrypoint.sh:40`; `screen.py:390,402,496–530,618–637` | Already final `exec`, SIGINT stop signal, spawn workers, STOP before one SIGINT, 300 s wait with container preservation. Restore default SIGINT explicitly before setup/exec; cover setup interruption. Require per-rank teardown receipts and clean kernel tail before declaring completion. Docker stop timeout must never silently escalate to KILL; retain single signal + inspection rather than default `docker stop`. |
| `overlay/vllm/v1/executor/multiproc_executor.py:457–459,874–881,929–962,1023–1030` | Pristine vLLM 0.30.0 waits default 5 s, TERM then KILL after 4 s; **the applied overlay already bypasses that path**, defers signals during loading and retains partially initialized workers for cleanup. Preserve this; acknowledge each rank only after explicit drain/release, before its target returns. |
| `overlay/vllm/screen1b_guard.py:28,268,385–411,511,526–527` | `_tables` and `_models` strongly retain owners with no clearing path. Add idempotent teardown clearing these after outstanding work drains. Existing 120 s warning waits indefinitely without killing; keep it. |
| `overlay/vllm/v1/worker/gpu/model_runner.py:2284–2314`; `overlay/vllm/screen1b_ple.py:204–206,270–271` | Runner synchronizes before deleting model/cache but retained globals can keep pins live. Stop submissions and drain copy/collective streams; close PLE memoryviews/mmap via `ClockCache.close`, release UVA aliases before slab owners, clear all registries, collect, synchronize after release, flush device and host caches. Verify communicator/worker shutdown order and record timestamps. |

Current shutdown order is explicit in `WorkerProc.shutdown:824–834`: close RPC
queues, call worker shutdown, then destroy model-parallel/distributed groups.
The image's `vllm/v1/worker/xpu_worker.py:227–237` calls its GPUWorker superclass
(transfer services, elastic executor, model runner: `gpu_worker.py:1481–1500`),
then releases XPU pools. Any conditional overlay of these two worker files must
preserve that ordering and add a final per-rank drain/receipt after communicator
cleanup; a model-runner-only receipt would be too early. No such overlay was added.

These changes require separate CPU coverage for normal, partial-load and signal
paths, then separately authorized native validation. **No userspace plan can
guarantee graceful release after OOM, fatal native crash or SIGKILL.** Memory
admission and no-kill supervision reduce exposure; timeouts remain evidence/
owner-intervention boundaries, never permission to tear down busy workers.

Validation: **26 probe tests passed**, no skips; both flag parsers, invalid modes,
refusal metadata, watcher STOP and real CPU fork/atexit semantics. No device
cleanup was executed. [Source-bound CPU receipt](../reopen-20261008/probe/cpu-exit-lifecycle-validation.json).
