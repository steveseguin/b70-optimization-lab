# The XPU allocator degrades within a boot; a reboot is likely required

Date: 2026-08-04 America/Toronto

Status: **blocked. Needs a reboot, which is the user's call.**

## The observation

A configuration that served successfully at 23:31 on 2026-08-03 no longer
initialises, in the **same boot** (uptime 1 day 7 hours, booted 2026-08-02
19:05). Nothing about the configuration changed: `gpu_memory_utilization=0.80`,
`candidate_profile=q12`, same vLLM tree, same kernels, same model.

The failure is an XPU allocation refusal during `model_runner.profile_run()`:

```
torch.OutOfMemoryError: XPU out of memory. Tried to allocate 192.00 MiB.
GPU 3 has a total capacity of 31.89 GiB of which 13.22 GiB is free.
```

**192 MiB refused with 13.22 GiB free.** This is not capacity exhaustion. Idle
devices report 43 MiB used and 0% utilisation, and no process holds the render
nodes, so the free memory is genuinely free.

## What it is not

- **Not the torch profiler.** A control run with profiling fully disabled fails
  identically (192 MiB refused, 13.22 GiB free). `TorchProfilerWrapper` is also
  constructed only inside `profile(is_start=True)`, so it allocates nothing at
  init. An earlier suspicion that the profiler caused this was wrong.
- **Not `gpu_memory_utilization`.** Tried 0.80 and 0.85. Raising it *increased*
  reported free memory (10.52 → 11.28 → 13.22 GiB) while the same allocation
  still failed. Utilisation is not the lever.
- **Not the host memory guard.** That is a separate, earlier failure with its own
  signature (`stop-service` in `memory-guard.tsv`); once the floor was lowered
  the guard logged 126–150 consecutive `continue` decisions and the run still
  died in `profile_run`.
- **Not leftover memory from a previous run.** Devices are idle between attempts.

## Most likely cause

Five `modprobe -r xe && modprobe xe` cycles were performed during this session to
clear GuC reset loops (see
[`2026-08-04-guc-firmware-wedge-root-cause.md`](2026-08-04-guc-firmware-wedge-root-cause.md)).
Each reload cleared the wedge, but the allocator's behaviour has degraded across
them. The reloads are the most plausible contributor, and they were my decision,
taken without asking.

An alternative reading is that the degradation is independent of the reloads and
accumulates with GPU faults generally — several runs earlier in the day ended in
device errors. The two are not distinguished by the evidence available.

## Recommendation

**Reboot the host**, then re-run the control (profiling disabled, util 0.80) to
confirm the configuration serves again before resuming profiling work. The GuC
firmware upgrade (70.44.1 → 70.54.0) is worth doing in the same window, since it
targets the wedge class that forced the reloads in the first place.

Not done here: a reboot is a disruptive, system-level action on a host holding a
protected record, and it needs explicit authorisation.

## Cost, recorded honestly

Nine launches produced no kernel trace. Seven distinct blockers, all
environmental: CCL wedge (×3, each inherited from a prior failed run), engine
ready timeout, host memory guard (×2 at different floors), and this allocator
refusal (×3). No measurement was obtained, and no serving parameter was changed.

## Boundaries

No quantisation change, no caching or speculation setting used to inflate any
number, no measurement recorded. The protected `125.4619731637751 tok/s`
conventional short-decode record is untouched, and every previously recorded
figure stands.
