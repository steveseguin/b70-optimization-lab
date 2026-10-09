# Slab probe with the host user-mode driver overlaid (2026-10-09 02:27 UTC): same fault at process exit

Remedy A from `2026-10-09-runtime-comparison.md`: the twelve host libraries (NEO 26.18.38308, IGC 2.34.4,
Level Zero 1.28.2, GMM, opencl-clang, zlib, zstd) bind-mounted over the image's resolved files, LD_LIBRARY_PATH
`/usr/local/lib:/opt/ucx/lib:/opt/venv/lib`, receipt identity `FLASHNEXT_PROBE_UMD=host-26.18.38308`. CPU ABI check
passed first (`probe/remedy-a-abi-check-20261009.json`). Fresh four-card receipt
`postflight-after-121-20261009T0227Z.json` (taken after the five-minute gap following the 121-frame LTX stop).
Receipts: `reopen-20261008/runs/probe-indirect-hostumd-20261009/`.

| | image driver (01:39 UTC) | host driver overlay (02:27 UTC) |
|---|---|---|
| gather bytes | equal (expected hash) | equal |
| launches / syncs | 1 / 1 | 1 / 1 |
| watcher read after readback | clean | clean |
| fault | 01:39:27.868140Z, `-ENOENT`, bcs reset, VA 0x…d556a74c0000 | 02:27:32.185140Z, `-ENOENT`, bcs reset, VA 0x…d556aa350000, ASID 23 |
| guardian's postflight request (right after the worker's `os._exit`) | 01:39:27.868464Z | 02:27:32.185534Z |

The fault line is logged **0.3–0.4 ms before** the guardian's postflight timestamp, which the guardian takes
immediately after `wait()` on the worker returns; the worker ends with `os._exit` while the pinned host slab, the
UVA view, the device buffers, the Triton module and the Level Zero queue/context are all still live. Both runs
fault at the worker's death, on the blitter engine, at a device virtual address that belongs to neither the device
buffers nor the host slab. The user-mode driver version does not change this.

## Reading

- The MoE addressing is cleared (twice byte-correct). The runtime version (NEO/IGC/L0) is cleared as the sole
  factor. What remains is the **exit lifecycle**: an abrupt process exit with live USM host mappings and a live
  queue, torn down by the xe kernel driver (7.0.0-39) while a blitter job or the VM teardown still references a
  mapping. The 14:04 UTC Screen 1 incident was an OOM kill (abrupt exit) with a bcs `-EBUSY` fault; the LTX venv
  processes exit gracefully (SIGINT, normal interpreter exit) and have never faulted on this boot. Attempt 7
  (ccs CAT errors on all four cards at the first forward) does not obviously fit and is being re-read.
- Second incident of boot 4aafe57b: `FAULT.json` set (receipt copy in `data/resume-20261008/`), health probe
  after it passed on all four cards (`postflight-after-second-probe-fault-20261009T0230Z.json`; cards healthy,
  4 fault-class lines in the boot's journal, all from the two probes). No GPU launches until the owner decides.
- Prepared next (CPU, Codex): the `--clean-exit` probe variant (ordered release, synchronize, normal exit) and an
  `--exit-after-sleep` control; the interpretation table is preregistered in `probe/README.md`. If the clean exit
  is clean, the production fix is graceful teardown ordering in the container entrypoint and the vLLM worker
  shutdown, not an allocator or kernel change.
