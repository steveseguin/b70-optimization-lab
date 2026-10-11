# Packet 4 memory admission revision — owner decision pending

2026-10-10, CPU-only review on steve-b70s. **A lower floor that admits this
boot is not supported by the recovered A367 evidence.** The proposal is
133,542,784 KiB, including the packet's fixture allowance. This is an owner
decision, not an approval, a proven fit, or permission to launch. The existing
120,000,000 KiB default remains unchanged unless an owner receipt is supplied.

## Current memory and the exclusion

[Raw observation](driver/memory-observation.json), 20:50:23 UTC:
MemTotal **121,268,676 KiB**, MemAvailable **116,192,088 KiB**, GPUActive
**112 KiB**. Linux labels these counters kB but uses 1,024-byte units.
The reviewer separately recorded MemAvailable **116,384,560 KiB** around
20:50 UTC, with roughly 1 GB process RSS. The old floor exceeds those
observations by 3,807,912 and 3,615,440 KiB respectively; normal sampling
variation does not remove the capacity problem.

`/home/steve/AGENTS.md`, “RAM replacement deferred” (2026-10-06), explicitly
keeps memory blocks 53–57 and `b70-offline-bad-memory.service` unchanged, with
no RAM replacement in 2026. Read-only sysfs observation confirms all five
blocks offline, each 2,147,483,648 bytes. No service command was used.

Arithmetic: 5 × 2 GiB = **10,485,760 KiB excluded**;
121,268,676 + 10,485,760 = **131,754,436 KiB** reconstructed without that
exclusion. This is not a measurement of historical A367 MemTotal. On this
boot the old floor leaves only 1,268,676 KiB of MemTotal for everything outside
MemAvailable, while the observed difference is 5,076,588 KiB. Idle RSS alone
cannot explain kernel memory or prove additional reclaimability. No cache,
swap, power or offlining setting was changed; no attempt to reclaim was made.

## What A367 actually recorded

The tracked [A367 supervisor trace](../../../qwen38-flash-next-fp8-b70/reopen-20261008/evidence/a367-host-pressure.tsv)
and [rescued calibration receipt](../../../qwen38-flash-next-fp8-b70/reopen-20261008/rescued-calibration.json)
contain 1,241 samples (trace SHA256
`683f7a9888f71e4c734c18a24741453ce8be5774c728d0903eccc6d1a65e669e`).

| Observation | MemAvailable KiB | UTC |
| --- | ---: | --- |
| First supervisor sample, immediately before successful launch | 129,321,820 | 2026-09-13 03:49:10 |
| Minimum | 16,167,644 | 2026-09-13 04:11:42 |
| Observed decline | **113,154,176** | 115,869,876,224 bytes |

The [A364/A367 note](../../../qwen38-flash-next-fp8-b70/notes/2026-09-13-a364-native-exact-gdn-certification-result.md)
records the successful A367 relaunch at 03:49:14 UTC after an earlier frozen
attempt. The frozen launcher checks 120,000,000 KiB but does not print the
accepted gate sample. That exact shell sample was not found; the first
supervisor sample is the nearest saved launch observation, not a fabricated
exact gate read. The trough follows model loading (approximately 04:02:11 UTC).
It cannot be dismissed as a short-lived initial loader copy.

The [host-memory reconstruction](../../../qwen38-flash-next-fp8-b70/notes/2026-10-08-host-memory-reduction-design.md)
identifies 63,609,487,360 bytes of host tensors: FP8 PLE 51,200,245,760,
expert rows 11,137,843,200, and token embedding 1,271,398,400 bytes.
The remaining 52,260,388,864 bytes are unattributed. The 115.87 GB is a measured
whole-host availability decline, **not peak worker RSS**. No usable A367 peak
worker RSS or GPUActive split survives; the rescued receipt explicitly leaves
worker RSS as null and contains no GPUActive series. Do not sum the tensor subtotal and that whole-host delta.

## Multi-card host RAM shadow and EnableDeferBacking

The [host stability guide](../../../../docs/host-stability-and-fault-diagnosis.md#host-ram-that-vanishes-while-a-multi-gpu-process-runs)
records the multi-card host RAM shadow: GPU buffers shared under deferred
backing hold system pages counted in GPUActive, outside process RSS.
Its real-server **92.6 GiB GPUActive**, reduced to **3.6 GiB** using
`NEOReadDebugKeys=1 EnableDeferBacking=0`, is **LTX evidence**, not an A367
measurement or an amount we may subtract from Flash-Next's budget.

The [later Flash-Next validation](../../../qwen38-flash-next-fp8-b70/reopen-20261008/VALIDATION.md)
records V30 Attempt 4 construction pressure **90.013 GB**, including
**74.063 GB GPUActive**, worker RSS maxima **2.779–2.782 GB each**, and a
**11.514 GB cgroup peak**. That was not a completed load or the A367 runtime.
It explicitly labels removing A367's unattributed 52.260 GB as an assumption,
not measured savings. Packet 4's allowlisted environment does not enable
these debug settings. This revision neither inserts them nor borrows their
possible savings. A changed allocation path needs separate evidence and review.

## Proposed need-plus-margin floor

The machine-readable declaration below is checked by the driver, and the
owner receipt must bind this entire document's SHA256 and exactly this value.

```text
proposed_minimum_mem_available_kib: 133542784
```

Formula (all terms KiB):

```text
A367 observed need = 129321820 - 16167644 = 113154176
Existing A367 loaded-state reserve                 = 12000000
Packet fixture allowance (4 ranks × 2 GiB)         =  8388608
Proposed admission = need + reserve + allowance    = 133542784
                                                   = 136747810816 bytes
Delta from A367 admission = +13542784 KiB
```

The reserve comes from the certified MTP1 supervisor's 12,000,000 KiB live
floor, also documented in the [MTP1 context preregistration](../../../qwen38-flash-next-fp8-b70/notes/2026-09-13-a375-a376-32k-context-ladder-prereg.md).
The allowance conservatively budgets the full registered 8 GiB fixture cap
for new CPU copies/writeback; it is a planning allowance, not a measured peak
or proof that temporary serialization never adds another copy. No savings
are credited for eager mode, the shorter response or omitted graph capture.
This is a conservative planning floor from one historical trace, not a bound
on every future load. The reserve covers uncertainty as well as shutdown room.

The proposed floor exceeds current MemTotal by **12,274,108 KiB** and the
observed MemAvailable by **17,350,696 KiB**. Even omitting fixture allowance,
need plus reserve is 125,154,176 KiB, above current total. Merely subtracting
the excluded 10 GiB from the old floor removes capacity without reducing
model demand. **There is no evidence-backed lower passing floor in this
packet.** Approval of this proposal would therefore still refuse this boot;
a lower floor requires a revised need calculation backed by matched evidence,
a new document hash and a new explicit owner decision. Keep the memory
exclusion in place. RAM replacement is not proposed.

## What a floor set too low risks

Pinned host tensors and GPUActive backing are not ordinary reclaimable page
cache. A low admission floor can cause reclaim stalls, swap pressure, OOM,
abrupt worker loss, GPU teardown faults, a frozen host and lost/unflushed
receipts. A cooperative stop is not instantaneous protection: the
[August graph attempt 7](../../../qwen38-flash-next-fp8-b70/notes/2026-08-28-tp4-mtp0-current-piecewise-graph-attempt7-result.md)
lost 9,025,608 KiB between samples, triggered stop at 25,947,668 KiB, and
recorded 18 TTM failures and nine OOM invocations/kills before cleanup.
The [October 8 OOM](../../../qwen38-flash-next-fp8-b70/notes/2026-10-08-screen1-mtp1-host-oom-result.md)
records a 67.9 GB unit peak and 12.6 GB victim RSS; neither counts every host
allocation. Host freezes have several established causes, so these numbers
do not attribute every freeze to RAM pressure. Packet 4's fault watcher does
not enforce a live memory-pressure reserve; the reserve here is an admission
budget, not a newly implemented runtime watchdog.

## Owner decision and receipt

The [runbook](WINDOW-RUNBOOK.md) gives the exact approval step. The checked-in
[receipt template](driver/admission-revision.pending.json) is deliberately
unapproved and refused. No genuine owner approval was supplied or manufactured.
The CPU tests create temporary synthetic approvals solely to exercise validation
and remove them afterward. The driver requires the exact approval sentence,
document hash, declared floor, owner designation, host and current boot; it
preserves the receipt and the delta in the run identity. This validates an
owner-supplied declaration, not a cryptographic signature of a person's identity.
The separate owner-window flag must pin the receipt hash. Existing halt,
fresh-health, payload, teardown-gap and capacity checks still apply.

## Path to matched evidence (reviewer note, 2026-10-10 21:05 UTC)

The historical trace behind the 133,542,784 KiB need was recorded before the
host-RAM shadow fix (`NEOReadDebugKeys=1 EnableDeferBacking=0`, see the
multi-card host-RAM shadow notes) and before the 10 GiB memory exclusion. The
Flash-Next lane already has the measurement that produces matched evidence: the
preregistered **attempt 8 calibrate-load** run
(`reopen-20261008/screen.py run --mode calibrate-load --loading-ram-guard-gb 96`),
which loads the certified TP4 line under a loading RAM guard and records the
real peak host demand on this boot. The first authorized window therefore runs
in this order: health receipt, attempt 8 calibrate-load, revised need
calculation from its receipt, owner approval receipt for the derived floor,
then the fixture extraction. No floor is lowered without that measurement.


## Measured on 2026-10-11 (attempt 8)

**Attempt 8 is not matched need evidence for a lower A367 admission floor.**
This corrects the preceding reviewer paragraph's description of the run as
“the certified TP4 line.” The run used the experimental Screen 1b mmap-PLE
adapter, v0.30.0 runtime, attempt-6 expert placement, exact large pinned
allocation policy and per-process `NEOReadDebugKeys=1 EnableDeferBacking=0`.
Its overlay applied 50 files, manifest
`daf50d2391549a9fb5c03ee2cf3a69e763cc44e621fdaf35e4b06529c7142b69`.
A fresh official-model hash receipt passes; shared weight identity does not
make this the certified A367 recipe, arithmetic or memory path.

[Incident/timeline and interpretation](../../../../notes/2026-10-11-attempt8-fourth-incident.md)
and [saved receipts/index](../../../qwen38-flash-next-fp8-b70/reopen-20261008/evidence/fourth-incident-20261011/index.json)
preserve the evidence from
`runs/screen1b-mmap-calibrate-load-20261011-attempt8/` in the reopen lane.
`receipts/host-memory-samples.jsonl.gz` is a lossless compressed copy of the
complete sampled series; its uncompressed SHA256 matches calibration.

| Measured host counter | Bytes | Decimal GB |
| --- | ---: | ---: |
| MemTotal | 124,179,124,224 | 124.179124224 |
| MemAvailable before hashing | 118,942,818,304 | 118.942818304 |
| Accounted pressure before hashing | 5,236,305,920 | 5.236305920 |
| MemAvailable after hashing / before load | **119,046,037,504** | **119.046037504** |
| Accounted pressure after hashing | 5,133,086,720 | 5.133086720 |
| Maximum sampled loading accounted pressure | **75,447,590,912** | **75.447590912** |
| Minimum sampled MemAvailable | **48,731,533,312** | **48.731533312** |
| Availability decline from post-hash baseline to trough | 70,314,504,192 | 70.314504192 |
| Sampled cgroup memory peak | 59,570,315,264 | 59.570315264 |
| Global bounded staging peak | 268,431,360 | 0.268431360 |

Host pressure means **MemTotal minus MemAvailable**; it includes the initial
host baseline. The 70.314504192 GB decline subtracts that baseline. The peak
occurs at sample 488, monotonic `172173.051341620`, during loading. Minimum
available memory is 45.385 GiB; total peak pressure is 70.266 GiB. These are
sampled observations, not guarantees between samples or later in startup.

| Rank at load_complete (both snapshots) | Pinned retained tensor bytes | Pageable metadata bytes |
| --- | ---: | ---: |
| 0 | 14,171,275,264 | 434,086,598 |
| 1 | 14,171,275,264 | 434,086,598 |
| 2 | 14,171,275,264 | 434,086,598 |
| 3 | 14,171,275,264 | 434,086,598 |
| Total | **56,685,101,056** | **1,736,346,392** |

The pinned figures count unique retained tensor storage, with
`allocator_bytes_measured=false`; actual allocator backing/retention peaks
are unmeasured. The pageable figures are metadata counts calculated from the
instantiated mmap/cache geometry, not separately observed RSS. Each rank maps
12,800,061,440 file-backed payload bytes; mapped resident bytes and PLE
hits/misses are zero in these load snapshots. Mapped address space is not a
resident-memory allocation. `staging-live.json` ends with an empty live map;
its peak is 256 MiB minus 4,096 bytes. Cgroup, worker RSS, pinned storage and
host counters overlap and peak at different times: do not sum them.

All four ranks finished weight loading, then all four cards faulted during
startup's KV-initialization profile/dummy forward. Calibration records
`ready=false`, `clean_exit=false`, `passed=false`, zero generation requests,
1,343 loading samples, 235 shutdown samples, no 20-second plateau and unknown
per-card free-VRAM reserves. `watchdog_reason=null`: failure was the GPU fault,
not the 96 GB loading guard. The container exited 1 without an OOM kill.
Kernel recovery also reported a failed atomic allocation for a GuC coredump
snapshot; available RAM alone does not prove every allocation could succeed.

These data document the experimental adapter's incomplete startup and improve
its own budget evidence. They establish neither complete startup/serving demand
nor matched demand for A367 plus packet-4 fixture capture. No floor reduction,
new margin formula or fixture authorization follows. The declared
**133,542,784 KiB** proposal, existing **120,000,000 KiB** default, exclusions
and all guards remain unchanged. A revised floor still needs matched runtime,
placement, driver/allocation settings, completed phase/peak evidence, fixture
allowance, a reviewed need-plus-margin calculation and a new document-bound
owner receipt. This append changes the document hash; an older approval hash
must not be reused. The fourth-incident window remains halted for the owner.
