# Screen 1b CPU validation — native FP8 mmap, 2026-10-08

**126/126 CPU tests pass, no skips: prior 77 + 22 calibration + 27 new tests.**
The new prediction is **87,765,002,264 bytes**; admission remains REFUSED.

Full suite executed without installations, using an existing interpreter:

```sh
PYTHONDONTWRITEBYTECODE=1 /home/steve/.venvs/ltx25-baseline/bin/python -m unittest discover \
  -s experiments/qwen38-flash-next-fp8-b70/reopen-20261008 -p 'test_*.py'
```

Torch 2.14.0+xpu, safetensors 0.8.0 and NumPy 2.5.2 were imported for explicit
CPU tensors only. No accelerator enumeration, availability check or execution
was called. System Python still runs the stdlib suite; seven torch-dependent
checks require the existing interpreter above and otherwise skip explicitly.
No venv was modified. No original full-size allocation/`mlock` experiment was
repeated: cache fixtures are tiny and actual checkpoint probes map at most
five rows per window, including TP/shard edges and final padding.

New checks cover raw-byte equality against direct safetensors reads, random
and repeated IDs, page/shard/TP edges, cache eviction and hits, nonowner zeros,
invalid IDs, malformed/missing/truncated shards, read failure, immutable files,
metadata/cap arithmetic, mmap residency unknowns, and current-step replacement.
The original torch hash is executed on CPU and compared to an independent
wrapping-int64 mirror at EOS/request boundaries and changed draft-like inputs.
All 256 FP8 byte codes are tested through the original cast/scale arithmetic;
NaNs are compared by output bytes. The static gather's clone is checked against
in-place corruption. Storage finalizers are checked through surviving views, including the real
CPU TorchDispatchMode conversion guard.

Loading tests exercise aggregate conversion reservations, nested admission,
chunking with retained staging, actual two-process lock serialization, and
one-table cache enforcement. Allocation snapshots test UVA/model alias
suppression, expert host/device storage, deduplicated KV tensors, actual
cache/step geometry and explicit unknown driver/graph bytes. Earlier watchdog,
calibration, overlay identity/application, placement and refusal tests remain.
Only expected-value assertions for the new memory prediction were updated.

The bounded predictor was regenerated from checkpoint headers (no whole-model
hash/scan), all overlay/support hashes refreshed, and every Python overlay
parsed. Shell syntax and `git diff --check` pass. MTP0/1/3 and calibrate-load
previews use `--dry-run`; these generate commands without Docker or network
operations. [CPU receipt](cpu-adapter-validation.json).

Open runtime risks: XPU UVA/FP8 transport and graph capture parity, unchanged
certified output pins under the V30 model, actual allocator/driver peaks,
NVMe miss tails/readahead, and the existing host/VRAM admission conflict. The
implemented pre-forward fetch is synchronous; no latency overlap is claimed.
No runtime, checkpoint, LTX process or port was changed. This task made no Git commits.

## Earlier 99-test calibration pass (historical)


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
