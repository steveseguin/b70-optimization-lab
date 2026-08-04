# Launching a long-context run: the four defaults that must be overridden

Date: 2026-08-04 America/Toronto

Status: **derived from five consecutive failed launches, each blocked by a
different default.** Every failure looked like a model or kernel problem and
none of them were.

## The recipe

```bash
LAGUNA_LONG_CANDIDATE_PROFILE=q12 \
LAGUNA_LONG_CASE_IDS=laguna-lc-32640-early \
LAGUNA_GPU_UTIL=0.80 \
VLLM_ENGINE_READY_TIMEOUT_S=1800 \
LAGUNA_MIN_MEM_AVAILABLE_KB=5242880 \
LAGUNA_LOW_SWAP_MIN_MEM_AVAILABLE_KB=6291456 \
LAGUNA_MIN_SWAP_FREE_KB=2097152 \
./run_laguna_long_context_baseline.sh candidate "$RUN_DIR"
```

## Why each one

**`LAGUNA_GPU_UTIL=0.80`.** The launcher defaults to `0.90`. Every measured arm
in this campaign ran at `0.80`; at `0.90` the engine loads the model fully,
prepares the DFlash draft projections, and then dies during KV-cache allocation
with a bare `RuntimeError: cancelled` that names no cause. Confirmed by diffing
`identity.txt` against a run that produced a `bench.json`.

**`LAGUNA_MIN_MEM_AVAILABLE_KB=5242880`.** The script default is `12582912`
(12 GiB) and has been since the guard was added on 2026-08-02, but every
successful long-context run passed 5 GiB explicitly. Loading the 67 GiB
checkpoint drives `MemAvailable` down transiently -- successful runs bottomed
out at **5.0 GiB** -- so the 12 GiB default kills the service mid-load. The
failure is silent: no OOM killer entry, no segfault, no traceback, just workers
that vanish. The only evidence is `stop-service` in `memory-guard.tsv`.

**`VLLM_ENGINE_READY_TIMEOUT_S=1800`.** The 600s default is not enough to stream
the checkpoint with a cold page cache, and `env -i` in the runner means the
variable must be whitelisted in `common_env` to reach the service at all.

**Swap thresholds** simply accompany the memory-guard change; the guard consults
them together.

## Do not bother pre-warming the page cache

Reading the checkpoint into cache first (72 GiB warmed in 14 s) does not help.
The pages are reclaimed under load, the guard still sees `MemAvailable` fall,
and the extra pressure is if anything counterproductive. Fix the threshold
instead.

## Reload the driver between failed runs

A run that dies leaves orphaned GuC jobs, and the **next** run then wedges at
CCL init -- stopping at exactly line 79 of `server.log`, the topology-recognition
warning, where a healthy run proceeds to `Starting to load model` in the same
second. This is reproducible: r4 ended with 78 reset events, r5 wedged at line
79 immediately after.

Recovery is unbind-all-four plus `modprobe -r xe && modprobe xe`. See
[`2026-08-04-guc-firmware-wedge-root-cause.md`](2026-08-04-guc-firmware-wedge-root-cause.md)
for the signature, the standing GuC 70.44.1 vs 70.54.0 firmware gap, and the
safety checks before reloading.

Killing a wedged run needs `SIGKILL`; workers blocked inside a CCL collective do
not respond to `SIGTERM`, and the runner's own cleanup can take minutes.

## Checking a run is actually progressing

`server.log` size is not a liveness signal during weight loading -- the
safetensors progress bar writes carriage returns that may not reach the file, so
a healthy load looks identical to a hang. Use the line count instead: **79 lines
and static means the CCL wedge**, anything past that means it is loading.

## Boundaries

None of these are serving parameters in the sense that matters to a measurement.
`gpu_memory_utilization=0.80` is the value every recorded arm used, so matching
it is required for comparability rather than a change. The rest are host-side
guards and timeouts. The protected `125.4619731637751 tok/s` conventional
short-decode record is untouched.
