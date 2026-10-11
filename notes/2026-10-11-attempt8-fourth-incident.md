# Flash-Next attempt 8: fourth incident — 2026-10-11

**Weights loaded on all four ranks. Startup failed during the profile/dummy
forward inside KV-memory initialization, before graph capture or readiness.
Fault-class verdict: unknown.** The recorded ordering does not establish the
October 10 abrupt-exit cause, and does not establish an mmap-PLE access fault.
This resembles attempt 7's unresolved full-model startup incident.

This review used CPU only, nice 19 and `OMP_NUM_THREADS=2`. The only container
operation was `docker logs --timestamps` on the existing exited container.
No GPU/device, server, launch, systemd, port 8188, LTX unit, host setting or
recovery operation occurred. No scratch was created. Original run receipts,
FAULT and the owner's acceptance receipt were left unchanged.

## Identity and evidence

Run: `experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runs/screen1b-mmap-calibrate-load-20261011-attempt8`.
Unit recorded by the run: `flashnext-screen1-20261010T204330`.
Container: `flashnext-screen1-screen1b-mmap-calibrate-load-20261011-attempt8`.
Boot: `4aafe57b-a54f-4bfd-b4ed-9f1cbb8830c7`, kernel `7.0.0-39-generic`.

The [saved evidence](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/fourth-incident-20261011/)
includes original container/kernel logs, a newly obtained timestamped container
log, byte-identical receipt copies, compressed full memory samples, selected
loader events with original line numbers and full-source hashes, and comparison
excerpts. [Index](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/fourth-incident-20261011/index.json)
records SHA256 and original receipt write times. `receipts/` below means that
bundle; original run-relative filenames are preserved there.

Model hashing **passed at 00:45:38 UTC**, official revision
`bcd9f01ddc9cff2316eb84281bebcd5b058bddce`, 144 root files, 131 shards,
185,563,783,127 bytes. This is fresh payload evidence for this run, not a repair
of the historical A367 receipt mismatch. Image:
`vllm/vllm-openai-xpu@sha256:e4446310b1d30015e8fdc1a0a2ef1669ac6bef857cbe772487571ed5c1a926a9`.
The application receipt records **50 changed files**, base
`ced6857afa0ea7b2e3f0846a62e1394e90f15607`, manifest
`daf50d2391549a9fb5c03ee2cf3a69e763cc44e621fdaf35e4b06529c7142b69`.
The phase-related source files below were checked against that manifest.

This is the experimental v0.30.0 Screen 1b mmap-PLE line: TP4/EP4, MTP1,
16-bit-family KV, 376,569,856 KV bytes/rank, 64 batched tokens, 4,352 context,
FULL_DECODE_ONLY capture sizes 1/2, compilation NONE, utilization 0.90,
attempt-6 placement, 1 GiB PLE cache/rank, exact large pinned allocations,
`NEOReadDebugKeys=1 EnableDeferBacking=0`, 96 GB loading guard.
It is not the certified A367 runtime/recipe or a performance/quality result.

## Timeline

Times are UTC on October 11. Kernel logs use October 10 `-04:00` local time;
**20:56:50 local = 00:56:50 UTC**. Kernel-window precision is one second.
Docker timestamps are log reception times, not native instruction times.
Allocation JSON has no embedded wall timestamp: the table deliberately labels
its preserved filesystem write times, corroborated by loader monotonic events.
Those write times are not reconstructed from Git checkout mtimes.

| Event | UTC | Receipt / evidence |
| --- | --- | --- |
| Fresh four-card preflight passes | 00:43:22–00:43:28 | `health-engine-window-20261011T004322Z.json` |
| Model hash completes, pass | 00:45:38 | `model-verification.json:completed_utc` |
| Container starts | 00:45:40.881980587 | `container-exit.json:StartedAt`; controller `started-utc.txt` says 00:45:40 |
| Rank 1 load_complete 0000 / 0001 writes | 00:55:10.067487 / 00:56:05.111964 | allocation files; loader-478 lines 114800 / 117212 |
| Rank 2 load_complete 0000 / 0001 writes | 00:55:11.806729 / 00:56:05.002088 | allocation files; loader-513 same line numbers |
| Rank 3 load_complete 0000 / 0001 writes | 00:55:13.119189 / 00:56:05.183880 | allocation files; loader-548 same line numbers |
| Rank 0 load_complete 0000 / 0001 writes | 00:56:00.362847 / 00:56:41.504127 | allocation files; loader-451 same line numbers |
| Model runner reports complete, ranks 3 / 2 / 1 | 00:56:08.431327 / .555187 / .778568 | timestamped container lines 246 / 250 / 255 |
| Model runner reports complete, rank 0 | 00:56:45.291018 | container line 342; 20.87 GiB, 518.475773 seconds |
| KV layout setup | 00:56:45 | container lines 343–347 |
| First kernel fault; all four cards fault/reset in this second | **00:56:50** | kernel lines 1–9; CCS, first address `0x0000e001f30e5000`, ASID 258 on 23:00.0 |
| Rank 0 FP8 MoE config warning received | 00:56:50.563688 | container line 348; same second as fault, no finer ordering available |
| Controller STOP write / successful SIGINT completion receipt write | **00:56:51.927722 / 00:56:52.084539** | original mtimes in index; signal receipt monotonic `172601.297999738`, rc 0 |
| Four unranked segfault banners received | 00:57:08.039248 / .039415 / .461995 / .462244 | timestamped container lines 349 / 403 / 457 / 511 |
| Worker death reported | 00:57:38.757466 | container line 565, VllmWorker-1, exit code unknown |
| EngineCore failed to start | 00:58:27.958844 | container lines 567–613, cancelled RPC |
| API reports engine initialization failure | 00:58:35.871592 | container line 728 |
| Container exits 1, no OOM kill | **00:58:47.411366140** | `container-exit.json:FinishedAt`, `OOMKilled=false` |
| Coordinator writes fourth-incident FAULT | 00:59:06 | saved copy of existing FAULT, not modified |
| Bounded postflight passes all four cards | 00:59:35–00:59:42 | postflight receipt, no probe-window fault lines |

The two snapshots per rank correspond to successive loader completions (target
then MTP loading), not two independent successful starts. `load_drained` follows
each snapshot; no `rank_teardown_complete` event is present in the saved loader
streams. `graceful-stop.json` records successful **signal-command completion**,
not successful graceful native teardown. Its code writes monotonic time after
the SIGINT command returns; the actual signal delivery time is not recorded.
The EngineCore cancellation event is monotonic `172601.170074718`, before
that receipt. Thus **first fault → controller cancellation/SIGINT → reported
segfaults/engine failure → exit** is the saved ordering; placing the reported
engine failure before SIGINT would be incorrect.

## Phase at the first fault and causal limit

[container.log](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/fourth-incident-20261011/container.log)
lines **578–588** and **630–640** place the pending call in
`_initialize_kv_caches -> determine_available_memory` (collective RPC).
Lines **342–348** place this after loading, KV layout selection and entry into
FP8 MoE setup. No completed profile, graph capture or ready message follows.

The applied `overlay/vllm/v1/worker/xpu_worker.py:24` inherits Worker;
`gpu_worker.py:542–545` calls `model_runner.profile_run()` even with explicit
KV bytes. V2 `gpu/model_runner.py:939–958` calls
`_dummy_run(self.max_num_tokens, skip_attn=True, is_profile=True)`.
**The supported phase is the 64-token startup profile/dummy forward inside
KV initialization, before graph capture.** Explicit KV bytes skip automatic
KV sizing but do not skip this profile/warmup forward. This is not the later
graph-capture warmup, a generated response, or evidence of a particular
faulting kernel. Native stacks only identify Torch boxed Python dispatch.

Crucially, `gpu/model_runner.py:1918–1928` gates `b70_pre_forward` with
`if not dummy_run`: this profile path skips the host mmap-PLE row-fetch hook.
The load snapshots report zero PLE hits/misses and zero mapped resident bytes
at that moment. They do not measure later accesses. Model execution still
uses initialized PLE step buffers and the experimental expert/UVA machinery;
the logs cannot identify which allocation or outstanding command faulted.
Calling this a proven mmap file-row access fault is unsupported.

The kernel records CCS `-ENOENT`, CAT errors and resets on **23/27/43/47:00.0**.
Timed-out jobs name host PIDs **1280780/1280817/1280911/1281001**, respectively
(kernel lines 1093/1120/1114/1095), not just PID 1280817. The 1,178-line saved
window was reported as 222 fault-class lines. An explicit recount finds
110 fault responses +101 CAT lines +4 resets +4 timed-out jobs +4 coredump
creation messages = **223**; a broad `coredump` substring also counts six
trace/path mentions (229). These are filter-dependent line counts within
one fourth incident, not hundreds of independent incidents. The postflight's
237 earlier-boot lines use its own whole-boot filter and are not a new fault.

At kernel line 1096, an order-9 GFP_ATOMIC page allocation fails; lines
1112–1121 identify GuC log/devcoredump snapshot allocation. This is recorded
after the first fault in the recovery trace, not evidence that a model OOM
initiated the incident. No OOM-killed container or memory-guard trip is recorded.
Ample MemAvailable does not guarantee a contiguous atomic allocation succeeds.

The [October 10 reproduction](../experiments/qwen38-flash-next-fp8-b70/notes/2026-10-10-exit-fault-reproduced.md)
was a tiny exact-readback **BCS** probe with immediate `os._exit`, followed
70.669 ms later by a fault. Here full TP4 **CCS** faults precede the recorded
stop and crash reports. The shared -ENOENT/CAT/reset vocabulary alone does
not prove a shared cause. A native crash/VM closure reported late is still
possible; Docker reception times and kernel service times do not exclude it.
An in-flight compute/address/lifetime defect is also possible. **Unknown** is
the causal verdict; neither abrupt-exit class nor adapter access fault is proven.

## Attempts 6 and 7

[Saved comparison excerpts](../experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/fourth-incident-20261011/comparison.json)
retain source hashes and original line numbers.

| Attempt | Failure and scope | Sampled host peak / minimum available, decimal GB |
| --- | --- | --- |
| 6, October 8 | During construction, rank 1 admission rejects 89,975,808,000 +196,608,000 =90,172,416,000 bytes against 90 GB; server lines 219/300. No load_complete snapshot; exit 1, not OOM-killed. | 90.059751424 / 34.119380992 |
| 7, October 8 | Loading completes; first CCS fault at 21:11:18.369060 UTC during the same KV/profile call, before controller SIGINT completion and reported crashes; exit 1. | 79.208165376 / 44.970967040 |
| 8, October 11 | Loading completes with the teardown overlay; same startup phase fails, four-card CCS incident; exit 1. No readiness/plateau/generation. | 75.447590912 / 48.731533312 |

Attempt 7's [ordering audit](../experiments/qwen38-flash-next-fp8-b70/notes/2026-10-09-attempt7-ordering.md)
already separates its startup fault from exit-probe evidence. Attempt 8
repeats that broad startup pattern despite applied cooperative teardown; it
does not demonstrate that the teardown remedy itself caused or prevented the
initial fault. Attempt 6 stopped earlier and cannot act as a passing forward
control. None supplies an exact-output or performance qualification.

## Host memory and admission

Values are bytes; GB means decimal 10^9. Accounted pressure is MemTotal minus
MemAvailable, a whole-host measure, not worker RSS. MemTotal is 124,179,124,224.

| Observation | MemAvailable | Accounted pressure |
| --- | ---: | ---: |
| Before hashing | 118,942,818,304 | 5,236,305,920 |
| After hashing, before load | **119,046,037,504** | 5,133,086,720 |
| Sampled loading maximum pressure | **48,731,533,312** | **75,447,590,912** |

The peak is sample 488, monotonic `172173.051341620` (during loading, earlier
than the first fault). Relative availability decline from the post-hash
baseline is **70,314,504,192 bytes**, not the total 75.448 GB pressure.
Each rank's load_complete receipts count **14,171,275,264 pinned tensor bytes**
and **434,086,598 pageable metadata bytes**: four-rank totals
**56,685,101,056** and **1,736,346,392**. The pinned value counts unique retained
storage; `allocator_bytes_measured=false`. The pageable value is calculated
from instantiated adapter geometry, not a separate RSS measurement. Neither
is an allocator high-water measurement. The mmap payload is 12,800,061,440
bytes/rank of file-backed address space, not that much resident RAM.

Global staging peaks at **268,431,360 bytes** (256 MiB minus 4,096), with an
empty live map at end. Sampled cgroup peak is **59,570,315,264 bytes**;
max sampled current is 59,558,641,664. Loading worker RSS maxima, ranks 0–3:
2,782,289,920 / 3,131,670,528 / 3,132,256,256 / 3,129,548,800 bytes.
These peaks need not coincide and overlap with other counters; do not add
cgroup/RSS/pins to whole-host pressure. Calibration has 1,343 loading samples,
235 shutdown samples, no plateau, unknown per-card free-VRAM reserve,
`watchdog_reason=null`, `ready=false`, `clean_exit=false`, `passed=false`,
and zero generation requests. This is a sampled incomplete-startup maximum,
not a proven full-serving bound or a safe revised admission floor.

The [memory admission revision](../experiments/own-xpu-runtime/stage1/packet4-prep/MEMORY-ADMISSION-REVISION.md#measured-on-2026-10-11-attempt-8)
now explicitly corrects the earlier claim that attempt 8 would be matched
certified-line evidence. Its declared floor remains 133,542,784 KiB; the
default and guards are unchanged. Applying an approval bound to the old
document hash to this appended document would be invalid.

## Authorization trail and owner decision

The [third-incident acceptance repin](2026-10-11-third-incident-acceptance-repin.md)
now links this outcome. The original owner archive receipt at
`experiments/ltx25-b70/data/resume-20261008/fault-archive-20261011T003614Z-owner-accept-receipt.json`
remains byte-identical, SHA256
`c2947a5065aeb27bd88938ed09cb8801043646e2e4d8f5e433ff8da7807ba2f0`.
It admitted the engine window after the third incident, with any further fault
halting that window. The later 00:43:22 health receipt satisfied the timing
issue in the CPU preview; attempt 8 was then actually run by the coordinator.
The fourth incident ends that admission. The saved FAULT copy records the
coordinator's controlled stop and halt; successful postflight does not reopen
it. LTX remains stopped under the owner's existing instruction.

**Recommend the owner keep the window halted and authorize a reboot before
any further GPU work**, consistent with repeated faults on this boot. This is
a decision request, not a performed or queued reboot. Do not lower the A367
floor or admit fixture extraction from this failed experimental run. After
owner resolution, the next native proposal should localize the full-model
profile failure with timestamped worker/native lifetime and operator/address
evidence; it needs its own bounded plan/admission, not an unchanged attempt-9
retry or another immediate-exit probe. CPU source review can continue without
reopening the window. No quality judgement, recipe promotion or speed claim
follows from these receipts.

Validation for this documentation commit: parsed and hash-checked saved
receipts, checked phase source against the applied manifest, recomputed memory
peaks and sums, checked timeline/log lines, local links and `git diff --check`.
No runtime tests or native experiments were rerun.
