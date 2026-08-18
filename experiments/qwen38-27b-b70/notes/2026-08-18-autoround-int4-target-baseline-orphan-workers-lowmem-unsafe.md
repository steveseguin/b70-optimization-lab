# UNSAFE: target-baseline launch orphaned EngineCore/TP workers → host-wide OOM

Date: 2026-08-18
Status: unsafe failure, recorded so it is not repeated. Do not relaunch the
command unchanged.

## What happened

A target-only Qwen3.8 AutoRound quality-baseline arm
(`nospec-latest-exact-native`, GPUs 0,1) was launched via
`experiments/qwen36-27b-autoround-int4-b70/validation-20260815/run-arm.sh`
into run root `/home/steve/qwen38-runs/target-exact-pyhash0-20260818`.

The server never reached `/v1/models` readiness within the 900 s timeout
(runner exit code 2, no smoke/bench/quality output).

`run-vllm-candidate.sh` then killed only `server_pid` (the API parent).
vLLM's multiprocessing children survived:

- `VLLM::EngineCore` PID 306554
- `VLLM::Worker_TP` PID 306670
- `VLLM::Worker_TP` PID 306671

The orphans kept consuming pinned/unswappable memory for ~75 minutes. At
16:32:51–16:32:53 the kernel entered repeated global OOM handling and killed
unrelated desktop/session processes before finally killing the workers. Each
worker showed ~2.15 TB total VM, ~1.55–1.60 GiB swap entries, ~7 MiB page
tables. More than 33 GiB of swap remained free throughout: the exhaustion was
pinned/unswappable or driver-visible memory, not swappable anonymous RSS, so
raising vm.overcommit would not have helped. No GPU kernel panic occurred;
the user rebooted manually because the host became unusable.

oneCCL defaults observed per process in the server log, likely material on a
15 GiB host (to be bounded experimentally, with graph-oracle validation,
before any change is trusted):

- `CCL_SYCL_TMP_BUF_SIZE=402653184` (384 MiB)
- `CCL_SYCL_SCALEOUT_HOST_BUF_SIZE=1073741824` (1 GiB)
- `CCL_SYCL_SCALEOUT_DEVICE_BUF_SIZE=1073741824` (1 GiB)

## Fix (same-day milestone)

`experiments/qwen36-27b-autoround-int4-b70/scripts/server-supervision.sh`
now supervises the server as a dedicated session/process group:

- launch via `setsid`; record leader PID and PGID;
- refuse to launch if stray `VLLM::`/EngineCore processes already exist
  (`ALLOW_STALE_VLLM=1` override);
- on normal exit, error, readiness timeout, INT, or TERM: SIGTERM the whole
  group, bounded grace, SIGKILL survivors, reap the direct child, verify the
  group is empty;
- low-memory watchdog (default: two consecutive readings below 2.5 GiB
  MemAvailable, 5 s poll) terminates the entire group and logs the event;
- cleanup/watchdog events and periodic memory snapshots recorded under the
  run directory (`supervision.log`, `server.pgid`);
- behavioral tests with dummy descendant trees:
  `experiments/qwen36-27b-autoround-int4-b70/scripts/test-server-supervision.sh`
  (all passing at introduction).

## Relaunch policy after this event

1. Readiness/smoke only first (`VALIDATION_RUN_SMOKE=1`, bench/quality off).
2. Reduce `GPU_MEMORY_UTILIZATION` from 0.95 (start 0.80–0.85).
3. Bound oneCCL buffers only after validating both graph collectives with the
   exact candidate environment.
4. Monitor MemAvailable, swap, per-process RSS/VmLck, GPU memory, worker
   count, and current-boot kernel log during the run.
