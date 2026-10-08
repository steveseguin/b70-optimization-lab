# Screen 1b CPU validation — follow-up, 2026-10-08

**99 CPU tests pass (77 existing + 22 calibration tests). Prediction-based
MTP1 admission remains REFUSED.** This is a CPU-reviewed
v5 source port and allocation census, not a GPU-fit or exact-output certificate.
The preceding 77-test packet is extended by the load-only calibration mode.

Executed from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s experiments/qwen38-flash-next-fp8-b70/reopen-20261008 -p 'test_*.py' -v
bash -n experiments/qwen38-flash-next-fp8-b70/reopen-20261008/container-entrypoint.sh
git diff --check
python3 experiments/qwen38-flash-next-fp8-b70/reopen-20261008/screen.py run --mode mtp1 --dry-run
```

The original controller, metadata, pressure-watchdog, cancellation, full
hash-bound overlay application/idempotence, PLE shard coverage and bounded-copy
tests remain. Ten additional tests cover logical row access including host
experts, signed aligned address offsets, invalid maps, final-size allocation
without a full-size intermediate, postprocessing metadata recovery/refusal,
CPU process/memlock bounds, actual real-shape measurement receipts, MTP
allocation accounting, and AST parsing of every overlay file.

The allocation and row-view tests use explicit fake tensors; no torch or GPU
import occurs. Whole-file overlay application tests use temporary copies of
pinned upstream Git objects, never the installed runtime or source checkout.
Tests cannot qualify native UVA, Triton compilation, V30 tensor-attribute
survival through execution, graph capture, sampler parity or fresh-server
behavior. The [manifest](overlay-manifest.json) seals all installed replacements
and the certified placement map.

The separate [dry buffer measurement](cpu-buffer-measurement.json) allocates
**real shapes and byte counts**, zero-fills anonymous mappings in bounded
chunks, and calls Linux `mlock` with the existing unprivileged limit. It runs
one rank at a time under a **20 GB process address-space cap**, using the same
pressure thresholds as the watchdog. Four ranks completed in about 29.3 s.
Maximum RSS **16.161030 GB**; each rank's RSS growth and locked-byte count exactly
matched its predicted buffer bytes. The sum of those sequential measurements
is **63.609487 GB**, not a simultaneous four-rank/server measurement. All locked
mappings were released. No XPU allocator or driver retention was measured.

The [reconstruction](certified-memory-reconstruction.json) now also pins the
[rescued calibration](rescued-calibration.json). The initial
[search](certified-run-search.json) missed the rescue directory. The recovered
A367 MemAvailable series establishes a 115.869876 GB historical host-pressure
increase. Absolute host peak, worker RSS and complete VRAM peaks remain unknown.
The 85.352759 GB result is only the previous 20 GiB allowance applied to the new
pins, not a calibrated prediction. Both MTP modes and five placement choices
are enumerated in [CALIBRATION.md](CALIBRATION.md).

No Docker run/pull/create, server launch, HTTP request, device enumeration,
GPU execution, installation, secret access, host-setting change, branch or
commit occurred. The process-local memory cap did not change host settings.
Port 8188, concurrent LTX files, source checkouts, installed runtimes and prior
run evidence were untouched. Work remains uncommitted on main. CURRENT.md records this CPU-only follow-up;
this work made no change to live GPU state.


## Load-only follow-up validation

The 22 new CPU tests cover meminfo kB parsing, missing fields, four synthetic
worker processes and their container cgroup, byte-valued sysfs VRAM counters,
missing VRAM, strict 24 GiB/2 GiB threshold boundaries on each rank, one-stop
watchdog behavior and its 0.5-second interval, separate phase peaks, the exact
15%/90 GB admission boundary, short/missing plateaus, loading peaks, unknown
or insufficient reserve, missing worker/cgroup accounting, shutdown failures,
sampling gaps, sample-hash/configuration binding, and historical pressure
change parsing. Controller tests prove calibration and MTP1 commands are
identical, prediction is bypassed only for measurement, one mock launch sends
only health/models GETs, the watchdog starts first, the plateau lasts 20 seconds,
and the single SIGINT is followed by verified clean exit, including when
container visibility briefly delays the stop signal. The privileged-scan
environment passthrough is mocked; no password file is opened.

The rescued summary was rebuilt on CPU, and `host-memory-prediction.json` was
regenerated and explicitly rejected again by `enforce_prediction`. Both mode
previews were run with `--dry-run`. No live sampler, endpoint or load-only
experiment ran. The original buffer allocation measurement above is historical;
this follow-up did not rerun its allocations or mlock calls.
