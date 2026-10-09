# Attempt 7: ordering and remaining mechanism — 2026-10-09

**The GPU fault preceded the controller stop and every recorded crash/death
report. It was a CCS fault during initial profiling; a first host-expert read
is not established as its cause.** Confidence is high in the recorded ordering
and exclusion of the RAM watchdog, moderate in a compute-time trigger, and low
in the exact failing allocation/instruction. GPU launches remain halted after
the second incident of the current boot, pending the owner's decision.
This review used CPU-only file/journal reads; no runtime or host changes.

## Evidence and clock limits

`R` below is [attempt 7](../reopen-20261008/runs/screen1b-mmap-calibrate-load-20261008-attempt7/);
`S` is [the saved overlay package](../reopen-20261008/).
[Extracted Docker/journal evidence](../data/2026-10-09-attempt7-ordering-evidence.json)
preserves selected precise events, commands and hashes of the source receipts.
Boot: `1019201097004915ac6c980d6b74afa0`; container:
`flashnext-screen1-screen1b-mmap-calibrate-load-20261008-attempt7`, ID
`70f04ed5369a441613c0e6800b744c09eb7bb1aef55da6aca962d14572e79a59`.

All table times are **2026-10-08 UTC**, milliseconds unless explicitly finer.
Rank log PIDs are container PIDs; the sampler observes corresponding host PIDs.
`server.log` has second-resolution application times and untimed native stacks;
retained `docker logs --timestamps` supplies **reception**, not execution times.
Kernel JSON supplies paired realtime/monotonic microseconds; their first-fault
offset is `1791126168.241033` seconds. Loader/sample times below use that offset;
they are reconstructed wall times, not independently measured UTC timestamps.
No per-rank forward-entry markers or native signal-delivery trace were saved.

Queries used `journalctl -b BOOT --since '2026-10-08 17:00:00'
--until '2026-10-08 17:14:00' -o json --no-pager`: bounds are **local EDT**.
Read `-k`, the system journal (including docker/containerd), and `--user -u
flashnext-screen1-20261008T165744.service` (user search began at 16:55 EDT).
For presentation use `--utc -o short-iso-precise`. Docker used explicit UTC
`--since '2026-10-08T21:10:00Z' --until '2026-10-08T21:13:20Z'`.
Historical `docker events` returned no retained signal events.

## Timeline

| UTC | Event and source |
|---|---|
| 21:10:40.029 / .054 | Rank 1, PID 478: loaded / last pre-fault rank log, attention block setup (Docker). |
| 21:10:40.495 / .514 | Rank 2, PID 513: loaded / last pre-fault rank log, same setup. |
| 21:10:40.539 / .558 | Rank 3, PID 548: loaded / last pre-fault rank log, same setup. |
| 21:11:12.940 / .974 | Rank 0, PID 450: loaded / last pre-fault rank log, same setup. |
| 21:11:13.236 | EngineCore PID 339 selects KV layout; no completed-profile message follows. |
| 21:11:18.058 | Sample 1356: all four worker PIDs, positive RSS; 46.587 GiB available. |
| **21:11:18.369060** | **First kernel fault:** card `47:00.0`, CCS, ASID 1164, VA `0xf4725000`, AccessType 1, FaultLevel 3. |
| 21:11:18.372 / .372 / .385 | Card 47 `-ENOENT` response (.371641), CAT (.372442), reset (.385005). |
| 21:11:18.385 / .400 / .414 | First fault details on cards 43 / 27 / 23; resets at .398 / .413 / .424. |
| 21:11:18.390 | Rank 0 MoE-config warning received (E=128, N=640, FP8 blocks 128×128). Its 21 ms lag does not order GPU execution. |
| 21:11:18.399 | Recovery snapshot page-allocation warning, after first fault/reset; not initiating host OOM. |
| 21:11:18.558 | Sample 1357: all four workers still have positive RSS; 46.225 GiB available. |
| 21:11:19.057 | Sample 1358 changes to shutdown. |
| 21:11:19.061 / .068 / .078 / .083 | Rank 3 / 2 / 1 / 0 `cancel_requested`, `loader-{548,513,478,450}.jsonl:117214`. |
| **21:11:19.113462** | Successful controller SIGINT **completion receipt**, +744.402 ms; delivery instant unavailable. |
| 21:11:36.408526 / .408699 / .408810 / .774845 | Four unranked native segfault banners reach Docker, 18.039–18.406 s after fault. |
| 21:12:06.065 / .566 | Last all-worker positive-RSS sample / ranks 0 and 3 first absent. |
| 21:12:07.065 / .128 | Rank 2 first absent / EngineCore reports `VllmWorker-3 died unexpectedly`, exit code unknown. |
| 21:12:56.077 / .864 | Rank 1 first absent / EngineCore startup failure and Python `RuntimeError: cancelled`. |
| 21:13:16.461 / 19.092 | Container exits 1, `OOMKilled=false` / controller unit exits 2. |

Per-rank forward **start times are unknown**. Source and the EngineCore stack
place execution in `determine_available_memory -> profile_run -> _dummy_run`:
64 tokens, before completed KV initialization/graph capture. Rank 0 reached
MoE configuration; the other ranks' last attributed logs remain load/setup.
The four native stacks (`server.log:348,402,456,510`) begin in Torch's
`PythonKernelHolder` dispatch and cannot be assigned to ranks or an operator.

No recorded process exit, Python exception, SIGSEGV/SIGBUS, OOM or kill precedes
21:11:18.369060 in the inspected journals/receipts. No process-coredump service
event was found. Positive RSS before/after fault argues against completed
worker exits, but does not prove runnable workers or exclude an earlier native
fatal signal whose report was delayed. **Absence of an exit record cannot prove
the premise “no process crashed first”.** Docker reception and deferred kernel
fault handling are not instruction timestamps.

`calibration-load.json` says `watchdog_reason:null`, failure due to the fault
latch; `graceful-stop.json` says controller completion/failure. Thus this was
the controller's post-fault SIGINT, not a memory-watchdog stop. The loading
minimum was **41.882 GiB available**, 17.882 GiB above the **24 GiB** calibration
threshold (`calibration.trip_reason`, overriding the watchdog's 32 GiB default).
Pressure peaked at 79.208 GB against the separate 96 GB load guard. No ready
plateau or generation request occurred. Later cancellations are consequences.

## Structural comparison and ranked explanations

Attempt 7 used **96 separate expert allocations per rank**, 37.68–281.80 MB
each, totaling **12,779,520,000 bytes/rank (11.902 GiB)**; not one giant slab.
The two byte-correct probes used one **3 MiB** slab and a 16 KiB integer gather,
not the FP8 expert compute kernel. Both used the >1 MiB exact-allocation path
(`pinned_max_round_threshold_mb:1,pinned_max_cached_size_mb:1`). This policy
changes size/cache handling, not host-USM allocation type. Earlier load attempts
did not reach this forward, so there is no matched old-rounding success.

The PLE cache is **1 GiB/rank, 4 GiB total**. `screen1b_ple.py:103–115,243–323`
copies mmap bytes through pinned cache/step storage into a device step buffer;
no mmap-derived pointer reaches the GPU. `model_runner.py:1918–1928` skips
that preparation on dummy/profile runs, consuming zero-initialized step data.
The relevant question is registration/address reachability, not a blanket
claim that every GPU/runtime can never service pageable-memory faults.

`launch.json` specifies **spawn**; `multiproc_executor.py:680–688` initializes
each child's device before loading. `q38_expert_placement.py:77–118` allocates
within that worker, wraps its pinned host allocation under its resident device,
and constructs its int64 table from local addresses. No intended cross-rank or
parent-before-fork host-pointer sharing exists. Runtime context bugs remain open.

1. **Native dispatch/runtime failure with VM closure**, possibly followed by
   the reported CCS fault: leading competing explanation, medium-low confidence.
   [Upstream v7.0 Xe](https://github.com/torvalds/linux/blob/v7.0/drivers/gpu/drm/xe/xe_pagefault.c#L146-L197)
   returns `-ENOENT` when the VM is already closed; logging follows service.
   This is a source analogy, not verified distro-binary behavior or proof of
   when the original GPU access occurred. Delayed native stacks keep it open.
2. **Compute-time invalid device write or earlier asynchronous operation**:
   similarly plausible, medium-low confidence. The recorded AccessType 1 is
   [WRITE in upstream Xe](https://github.com/torvalds/linux/blob/v7.0/drivers/gpu/drm/xe/xe_pagefault_types.h#L12-L28),
   weakening the specific “host weight read fault” claim. Output, routing,
   scratch, or runtime-owned storage could be involved. VA `0xf4725000` is below
   4 GiB but identifies no allocation by itself. Other cards faulted at
   `0xf5569ed25000`, `0xeaaa4b285000`, `0xe001f30e5000` (and adjacent pages).
   No attempt-7 pointer census survives; 0x79… addresses from another process
   are not a valid address map for these ranks.
3. **Large host-expert indirect residency/table/native codegen defect**: still
   plausible, reduced confidence after the tiny gathers. Host pointers remain
   hidden in table offsets (`fused_moe.py:871–916`); real FP8 shapes and aggregate
   registrations were not tested by those probes. Source and saved LLVM retain
   int64 offsets, so universal int32 truncation is unsupported. Runtime values,
   final machine code and indirect-access flags are unrecorded.
4. **TP4/native-context interaction or damage from the earlier same-boot fault**:
   possible, unisolated. Source excludes intentional cross-process table pointers,
   not a driver/collective defect. Four faults do not prove four independent causes.
5. **PLE mmap dereference, inherited expert pointers, graph capture, RAM-watchdog
   kill**: contradicted by saved control flow/order. These are not next-test leads.

The saved evidence settles controller/memory ordering and intended ownership;
it cannot settle the top three mechanisms. It does **not** justify calling this
a proven first access to host expert rows or treating graceful teardown as a fix.
This qualifies the leading hypothesis in the [earlier analysis](2026-10-08-attempt7-gpu-fault-analysis.md).

## Smallest next step — design only, after owner authorization

No full-model TP1 load or TP4 relaunch. Use one spawned rank, one card, one real
64-token FP8 expert layer, unchanged allocator/image/UMD and the reviewed
[graceful-teardown candidate](../reopen-20261008/overlay-fix-teardown/README.md).
Keep rank-0 layer-0 geometry: 128 experts, 27 host/101 resident; host w13/w2
88,473,600 / 44,236,800 bytes, rows `[1280,2560]` / `[2560,640]`.
Use fixed synthetic bytes/scales and deterministic routes selecting both kinds;
real alignment, quantization, w13, activation and w2 kernels. This is diagnostic,
not quality/performance evidence. Omit PLE and whole-model/collective work.

First run an all-device table control, then the mixed-host table path **only if
the control and journal remain clean**. Keep inputs/FP8 math fixed; compare
outputs exactly. Synchronize and flush UTC/monotonic receipts before/after each
kernel and each cleanup phase. Record child PID/state/exit via an external
guardian, unbuffered native stderr, and continuous kernel timestamps. Before
launch, establish whether existing kernel tracing can capture fatal-signal
delivery, process exit and VM close; retain that trace with the run. If unavailable,
label the causal separation incomplete. A fatal signal/VM close before fault supports candidate 1;
a mapped, live worker faulting during a named kernel supports candidate 2.

Save every host/device/output/scratch/table span, reconstructed/read-back table,
queue/context and available native USM-kind queries, source/image/IR hashes,
memory samples, exact outputs, signal/exit status and teardown receipts. Missing
native queries must be labeled unavailable. Control failure implicates shared
compute/dispatch; only mixed failure raises candidate 3; exit-only failure raises
lifecycle. A clean result clears only one layer/rank, not 96 allocations or TP4.

**Stop rule:** first fault, native crash, failed comparison or bounded lack of
progress ends new submissions. Preserve evidence/processes on a hang; no forced
kill, automatic retry, second arm after fault, reset or health launch. The owner
must resolve the current halt before any such run. No runnable launch is issued.
