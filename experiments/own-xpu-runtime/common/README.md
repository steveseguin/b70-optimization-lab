# Shared Intel Arc Pro B70 / Xe2 Bring-Up Toolkit

Reusable, lane-agnostic utilities extracted from the DeepSeek V4.1 and Inkling-2-Mini lanes so future own-engine lanes do not reinvent card locking, power/energy telemetry, shader dumps, fault checks, or ledger linting.

| Tool | Purpose |
|---|---|
| [`on-card.sh`](on-card.sh) | Exclusive per-card lock (`flock`) + host `MemAvailable` guard + oneAPI env setup for cards `0–5` (parameterized via `B70_LOCKS`, `B70_MIN_MIB`, `B70_CLAIM_FILE`). |
| [`hwmon-power.sh`](hwmon-power.sh) | Read-only telemetry logger for every Intel `xe` card (power W, energy J, active/actual MHz, PL1/PL2 throttle flags). Safe during active runs; changes zero hardware settings. |
| [`igc-dump-kernel.sh`](igc-dump-kernel.sh) | Runs a benchmark with `IGC_ShaderDumpEnable=1` into a temp directory, copies out `.asm` files matching a kernel substring, and immediately deletes the 1.5–4 GB raw dump directory. |
| [`check-journal-faults.sh`](check-journal-faults.sh) | Scans `journalctl -k` since a given timestamp for exact `xe` / GPU fault signatures (`Fault response`, `CAT error`, `engine reset`, `coredump`, `GuC.*crash`, `device inaccessible`). Exits non-zero on any hit. |
| [`lint-do-not-repeat.py`](lint-do-not-repeat.py) | Validates any lane's `DO-NOT-REPEAT.md` table (exact 4 columns `Idea \| Result \| Evidence \| Re-open when`, zero empty cells, contiguous GFM table). |

## Mandatory B70 / Xe2 Rules for New Lanes

1. **One `sycl::context(dev)` per card, always:** DPC++'s default platform context mirrors device USM 1:1 into host RAM and OOMs 15 GiB hosts.
2. **Check free VRAM before allocating:** `xe` evicts buffers into host RAM instead of failing allocations; query `sycl::ext::intel::info::device::free_memory` with `ZES_ENABLE_SYSMAN=1`.
3. **Judge prompt kernels by Joules/launch:** B70 cards hold 275 W PL2 during long prompts (~2.35–2.60 GHz); interleave A/B variants on the same card to cancel PL2 drift.
4. **Never judge multi-queue overlap with `enable_profiling`:** queue profiling serializes overlap on `xe`/L0; use unprofiled A/B timing.
5. **Never reserve card 0 for the desktop:** all healthy cards (`0–5` on `steve-TURIND8-2L2T`, `0–3` on `steve-b70s`) are authorized workers.
