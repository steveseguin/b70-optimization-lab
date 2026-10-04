Posted 2026-10-04 to https://github.com/intel/compute-runtime/issues/948#issuecomment-5982081300 (owner approved). Text as posted:

**A narrower data point: the load-time `bcs` / `-EINVAL` variant is the copy engine reading a temporary `EXTERNAL_HOST_PTR` mapping, it only exists for single host<->device copies of 512 MiB or more, and splitting those copies avoids it**

This covers one class only: copy-engine page faults *while a model loads*. It is not the under-load `ccs` reset others describe here, and not the teardown noise after a kill. Posting because the address turned out to be fully explainable and the workaround is cheap.

### Setup

2x Arc Pro B70 (`8086:e223`), EPYC 8-core, 15 GiB RAM, Ubuntu 24.04, `xe`, GuC 70.54.0. Kernels 7.0.0-31 and 7.0.0-38. vLLM 0.29 XPU, TP=2 (oneCCL) and TP=1, in a container with compute-runtime 26.27.39122.11 / libze1 1.32.0 / torch 2.13.0+xpu; also reproduced the allocation behaviour on the host with 26.22.38646.7 and torch 2.14.0+xpu. `PYTORCH_ALLOC_CONF=expandable_segments:True`.

### The signature (four saved incidents, both cards, both kernels)

Always during weight load, always the same GPU VA range and nearly the same page order:

```
xe 0000:e3:00.0: [drm] Tile0: GT0:
	ASID: 1146
	Faulted Address: 0x0000800400213000
	FaultType: 0
	AccessType: 0
	FaultLevel: 1
	EngineClass: 3 bcs
xe 0000:e3:00.0: [drm] Tile0: GT0: Fault response: Unsuccessful -EINVAL
... (27-45 of these, all inside 0x800400200000-0x800400228000)
xe 0000:e3:00.0: [drm] Tile0: GT0: Engine memory CAT error [18]: class=bcs, logical_mask: 0x1, guc_id=18
xe 0000:e3:00.0: [drm] Tile0: GT0: Engine reset: engine_class=bcs, logical_mask: 0x1, guc_id=18, state=0x249
xe 0000:e3:00.0: [drm] Tile0: GT0: Timedout job: seqno=4294967260, ... in python3
```

Devcoredump: `IPEHR 0x13000203`, ACTHD 0x3c into a batch at a high heap address. (Practical note: the fault record is one multi-line kernel message, so `journalctl -o short` plus `grep` keeps only its empty first line. `journalctl -k -o cat` shows the address.)

### What that address is

- In `xe_pagefault_service()` (v7.0), `-EINVAL` is returned when the VM is not in fault mode or when `xe_vm_find_vma_by_addr()` finds no VMA. NEO creates its VM with `LR_MODE | FAULT_MODE` here, so this is "no VMA at the faulting address".
- `0x800400200000` is `HEAP_STANDARD` base plus the 2 MiB granularity, i.e. the first slot the heap allocator hands out for allocations above its 4 MiB threshold.
- With `NEOReadDebugKeys=1 LogAllocationType=1 LogAllocationStdout=1 PrintBOBindingResult=1` the runtime names the object:

```
Created Graphics Allocation of type EXTERNAL_HOST_PTR
 ... Type: EXTERNAL_HOST_PTR Pool: System4KBPages Root index: 1 Size: 1271398400 CPU VA: 0x75644437f040 - 0x75648ffff03f GPU VA: 0xffff800400200040 - 0xffff80044be8003f ...
bind BO-0 to VM 1, vmHandleId = 0, range: ffff800400200000 - ffff80044be81000, size: 1271402496, result: 0
unbind BO-0 from VM 1, vmHandleId = 0, range: ffff800400200000 - ffff80044be81000, size: 1271402496, result: 0
```

  1,271,398,400 bytes is the model's 124,160 x 5,120 FP16 embedding / LM-head shard. A TP=2 start makes exactly eight of these, at the end of the main weight load and during the draft-model load, which is exactly where every fault landed.

So the event is: the copy engine reads the temporary userptr mapping of the host source buffer for a host-to-device copy, and there is no VMA there at that instant.

### The size threshold

One-card probe, a plain `cpu_tensor.to('xpu')` of N MiB, counting `EXTERNAL_HOST_PTR` creations in the allocation log (same result on 26.27 and 26.22):

| Copy size | `EXTERNAL_HOST_PTR` created |
|---|---|
| 2, 8, 64, 256, 257, 300, 384, 448, 496, 500, 511 MiB | 0 |
| 512, 1024, 1212 MiB | 1 each, at GPU VA `0x...800400200040` |

Device-to-host copies of that size make the same mapping. Smaller copies go through `BUFFER_HOST_MEMORY` staging and never touch this path.

### Workaround that removes the path

Split any host<->device copy of 512 MiB or more into smaller pieces (we use 128 MiB slices of a flat view). With that:

- allocation log: 0 `EXTERNAL_HOST_PTR` mappings during the whole start (control: 8 on TP=2, 3 on TP=1 where one is a 2.5 GB device-to-host move);
- outputs bit-identical (weights compare equal; our 12-prompt token-identity gate passes; a video pipeline's clip hashes are unchanged);
- load time unchanged, the 1.27 GB upload itself went from 0.14 s to 0.08 s.

I cannot give a before/after fault rate: with the container not swapping, the fault was about 1 in 59 starts, so counting would take hundreds of starts. The claim is only that every saved fault was a read of that mapping and the mapping is no longer created.

### Things that did not help

- `ExperimentalH2DCpuCopyThreshold=2147483647` (with `NEOReadDebugKeys=1`): no effect, same mappings. `preferCopyThroughLockedPtr()` apparently does not classify torch's destination as device USM under `expandable_segments`.
- `ExperimentalForceCopyThroughLock=1`: segfault.

### Timing sensitivity

With the container allowed to swap at its own memory limit (`--memory 12g --memory-swap 16g`, 29 GB of weights streaming through its page cache) this exact fault hit 3 times in 4 days. With `--memory-swap` equal to `--memory` it dropped to 1 in 59 starts. Host memory pressure seems to widen whatever window this is; it is not the cause.

### What I have not determined

Which side drops the mapping while the blit is still reading: the runtime's release of the temporary host-pointer allocation (the shared temporary-allocation list cleaned by `cleanTemporaryAllocations`, across the main and copy CSRs), or something in the kernel. I read the release logic and could not find the hole by inspection. Happy to share the four devcoredumps and the allocation logs, or to run a specific debug key if one would discriminate.
