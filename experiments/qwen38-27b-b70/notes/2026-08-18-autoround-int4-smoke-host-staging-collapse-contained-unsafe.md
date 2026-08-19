# UNSAFE (contained): weight-load host staging collapses 15 GiB host despite 0.85 util + watchdog

Date: 2026-08-18
Status: negative result, recorded so it is not repeated on this host. This
matches `repro/qwen38-27b-autoround-int4-b70/REFERENCE-HOST-HANDOFF.md`:
execution of full-server lanes is paused on the 15 GiB second host until the
measuring host publishes load-time host-memory peaks and a tested cgroup
limit.

## Runs

Two supervised smoke-only arms (`nospec-latest-exact-native`, GPUs 0,1,
staged graph-safe runtime, smoke=1 bench=0 quality=0):

1. `/home/steve/qwen38-runs/target-exact-smoke-memsafe-20260818`
   `GPU_MEMORY_UTILIZATION=0.95` (record.env pinned; override knob did not
   exist yet). Kernel global OOM at 19:35:46 local killed desktop/session
   processes and then the whole vLLM group (pids 11911/12123/12187/12188).
   Runner's new group cleanup then verified the group empty; no orphans.
2. `/home/steve/qwen38-runs/target-exact-smoke2-memsafe-20260818`
   `GPU_MEMORY_UTILIZATION=0.85` (new `VALIDATION_GPU_MEMORY_UTILIZATION`
   knob, confirmed effective in identity.env), watchdog floor 3.0 GiB,
   1 Hz memory telemetry. Same collapse; desktop froze; user rebooted.

## Telemetry anatomy of the collapse (run 2, 1 Hz)

Baseline after engine spawn: MemAvailable ≈ 9.2 GiB, group anon ≈ 4.5 GiB,
`Committed_AS` ≈ 19 GiB. At weight-load start (6-second window):

- `Committed_AS`: 20.3 GB → 32.9 GB (**+12.6 GiB committed**)
- MemAvailable: 8.1 GiB → 1.77 GiB
- SwapFree fell 5.8 GiB; every vLLM process's anon was fully swapped out
  (parent 1.6 GiB → swap, workers 1.6 GiB each → swap)
- `VmLck=0` in every group member at the sampled instants

The consuming memory is not process-attributed RSS and not mlock: it is
kernel/driver-side pinned staging (Level Zero host DMA staging for the
2×~9.5 GiB TP weight shards). Lowering the *device* reservation to 0.85 did
not help; the collapse is host-staging-bound, consistent with the earlier
stock-container cgroup finding (8.44 GiB model memory per rank, warmup
exceeded a 9 GiB host cgroup).

## Watchdog lesson

The collapse completes in ~6 s and immediately stalls every process in
direct reclaim, including the watchdog itself; a 2-reading × 5 s poll cannot
react, and SIGTERM cannot run while the group is stuck in allocation. A
reactive watchdog is insufficient for this failure mode on this host —
prevention (cgroup scope limit, sequential/pinned-free loading) is required.
No further full-server launches on this host until the measuring host
provides item 5 of the reference-host handoff (peak host RSS, peak swap,
staging behavior, smallest tested cgroup limit, fail-closed abort).

## Containment results (positive)

- Process-group supervision worked: run 1 ended with `stop_group complete:
  group empty`, no orphan EngineCore/Worker processes (contrast with the
  16:32 orphan event earlier the same day).
- `run-vllm-candidate.sh` now exits 2 (not 0) when the server dies before
  readiness; `run-arm.sh` maps missing outputs to distinct rc 7/8/9.
- Both GPUs report normal PCIe state on the current boot; no GPU reset or
  kernel panic occurred in either run. The failure class is host OOM
  pressure only.
