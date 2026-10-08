# Screen 1b CPU validation — follow-up, 2026-10-08

**77 CPU tests pass. Memory admission remains REFUSED.** This is a CPU-reviewed
v5 source port and allocation census, not a GPU-fit or exact-output certificate.
The preceding 67-test packet is superseded by this follow-up.

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

The [reconstruction](certified-memory-reconstruction.json) pins the available
certification sources. Missing raw A364–A367 directories are recorded in
[the read-only search](certified-run-search.json). Host peak, per-worker RSS
and per-rank VRAM weights/graph measurements remain null, not invented zeroes.
The 85.352759 GB result is only the previous 20 GiB allowance applied to the new
pins, not a calibrated prediction. Both MTP modes and five placement choices
are enumerated in [CALIBRATION.md](CALIBRATION.md).

No Docker run/pull/create, server launch, HTTP request, device enumeration,
GPU execution, installation, secret access, host-setting change, branch or
commit occurred. The process-local memory cap did not change host settings.
Port 8188, concurrent LTX files, source checkouts, installed runtimes and prior
run evidence were untouched. Work remains uncommitted on main; CURRENT.md is
unchanged because there was no change to live GPU state.
