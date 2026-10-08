# Flash-Next Screen 1b — v5 port and CPU memory reconstruction

**No honest joint fit is established yet.** The certified placement is now
ported and its **63.609487 GB** of host buffers is validated with real-shape
CPU allocations. The surviving certified receipts do not contain worker RSS
or host/VRAM peaks, so a ±10% server-peak calibration is unavailable. The
previous assertion that placement could not help has been withdrawn.
[Evidence, formulas, configuration table and limitations](CALIBRATION.md).

The old 20 GiB allowance plus 256 MiB staging gives **85.352759 GB** for the
new placement, down from 92.237316 GB. This is an **uncalibrated sensitivity
case**, not the predicted measured peak. It passes 90 GB numerically but misses
85 GB; execution also refuses unknown phase bounds and VRAM reserves.

| V30 placement | Pins GB | Nonpin host room below 85 GB | MTP1 / MTP0 static reserve upper bound, GiB | Server peak |
| --- | ---: | ---: | ---: | --- |
| Certified v5 | 63.609 | 21.391 GB | 2.140 / 2.796 | Unknown |
| Lab long-context v5 | 68.731 | 16.269 GB | 3.225 / 3.881 | Unknown |
| 1,000 host expert rows/rank | 72.132 | 12.868 GB | 4.232 / 4.888 | Unknown |
| 1,100 host expert rows/rank | 74.099 | 10.901 GB | 4.690 / 5.345 | Unknown |
| 1,200 host expert rows/rank | 76.065 | 8.935 GB | 5.148 / 5.803 | Unknown |

Reserve is the worst rank, assuming historical rank0 capacity on all cards,
**before** graph/runtime/allocator overhead; it is not promised free VRAM.
All alternatives use native host PLE, full 16-bit KV at **376,569,856
bytes/rank**, **FULL_DECODE_ONLY**, length **4,352**, TP4/EP4. None qualifies.
The default remains the certified mask with MTP1 to minimize differences while
resolving memory accounting; it is not labelled as a fitting selection.

The v5 port creates final resident/host expert tensors directly, keeps every
expert callable through the loader row map and Triton address table, retains
full block scales and logical expert counts, and checks parameter replacement.
It also restores input-embedding UVA and selects compilation NONE, utilization
0.92 and the certified 12.25 GiB generic offload budget. PLE coverage, bounded
serialized copies, the independent watchdog and graceful drainage remain.
[Overlay hashes](overlay-manifest.json), [phase bounds](memory-bounds.json),
[prediction](host-memory-prediction.json), [CPU tests](VALIDATION.md).

Compared with the certified lane, the NVIDIA-derived V30 model, native kernels,
GDN, compiler, collective and tuning context differ. Compared with stock V30,
this includes the already-pinned Lumnus XPU Python changes plus lab storage,
loader and shutdown changes. Native wheel and sampler are unchanged by this
port. Output parity, actual XPU pointers, graph pools and server fit remain
untested. No speed/quality promotion follows from CPU tests.

Preview without Docker, GPU or network operations:

```sh
python3 /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/screen.py run --mode mtp1 --dry-run
```

Exact requested execution command — **not run, currently refuses admission**:

```sh
python3 /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/screen.py run --mode mtp1 --execute
```

The fallback CPU measurement was implemented and run:

```sh
python3 experiments/qwen38-flash-next-fp8-b70/reopen-20261008/dry_buffers.py \
  --output experiments/qwen38-flash-next-fp8-b70/reopen-20261008/cpu-buffer-measurement.json
```

It constructs OS-locked buffers one rank at a time, with a 20 GB process
address-space cap and pressure checks. Maximum RSS was **16.161030 GB**;
locked bytes matched the formula exactly and all mappings were released.
It does not use or measure the XPU pinned allocator. Missing archived RSS,
host-peak and VRAM pool receipts are listed in the calibration note.

The unchanged watchdog polls every 250 ms and sends one SIGINT at accounted
host pressure ≥80 GB or MemAvailable ≤32 GiB. Allocation admission checks the
next buffer too. Nothing retries or escalates to hard kill. A below-85-GB
scenario can still trip this stricter watchdog. No threshold was relaxed.

No server, GPU, Docker run/pull/create, install, credential access, branch,
commit or host-setting change was performed. Port 8188 was never contacted.
All work remains uncommitted; concurrent LTX files and existing runs were
preserved. Future execution needs separately resolved memory bounds and idle
cards; this packet is not authorization to displace LTX.
