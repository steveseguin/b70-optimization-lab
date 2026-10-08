# Flash-Next Screen 1b — v5 port and CPU memory reconstruction

**No honest joint fit is established yet.** The certified placement is now
ported and its **63.609487 GB** of host buffers is validated with real-shape
CPU allocations. The rescued A367 supervisor trace now supplies a **115.87 GB whole-host
pressure increase**, already above 90 GB. It does not supply worker RSS or
complete live VRAM peaks, and does not qualify the newer runtime. The
previous assertion that placement could not help has been withdrawn.
[Evidence, formulas, configuration table and limitations](CALIBRATION.md).

The old 20 GiB allowance plus 256 MiB staging gives **85.352759 GB** for the
new placement, down from 92.237316 GB. This is an **uncalibrated sensitivity
case**, not the predicted measured peak. It passes 90 GB numerically but misses
85 GB; prediction-based execution refuses unknown phase bounds and VRAM
reserves. The load-only measurement mode below bypasses that prediction gate.

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

The generation-run watchdog polls every 250 ms and sends one SIGINT at accounted
host pressure ≥80 GB or MemAvailable ≤32 GiB. Allocation admission checks the
next buffer too. Nothing retries or escalates to hard kill. A below-85-GB
scenario can still trip this stricter watchdog. The allocation guard inside the unchanged overlay also retains these
stricter thresholds, including during calibration; it can cancel before
the external calibration watchdog reaches its 24 GiB floor.

No server, GPU, Docker run/pull/create, install, credential access, branch,
commit or host-setting change was performed. Port 8188 was never contacted.
All work remains uncommitted; concurrent LTX files and existing runs were
preserved. Generation execution needs a qualified memory receipt or resolved bounds,
and all execution needs idle cards; this packet is not authorization to displace LTX.


## Owner-approved sequence: calibrate-load → mtp1

These commands are prepared for the owner; **neither was executed in this
CPU-only follow-up**. First arrange exclusive idle cards and the existing
clean/recovered-boot admission, with at least five minutes after the previous
server stops. This controller retains its conservative whole-boot fault
refusal; the earlier recovered fault is not silently waived by calibration.
No mode displaces LTX, uses port 8188, installs anything, or pulls an image.
The pinned image must already exist. Existing `SCREEN_PRIVILEGED_FD_SCAN` and
`SCREEN_SUDO_PASSWORD_FILE` settings pass through to the systemd worker; only
the opt-in fd scan uses that existing privileged path. The sampler never does.

```sh
SCREEN_PRIVILEGED_FD_SCAN=1 python3 /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/screen.py run --mode calibrate-load --execute
```

Default output: `runs/screen1b-calibrate-load/`. Choose a fresh `--run-dir` if
that directory exists. The mode uses **the exact MTP1 launch command**, including
the ported v5 placement, unchanged weights, full 16-bit KV, graph configuration
and bounded loader. Its admission comes from the watchdog, not a predicted
complete peak. It still verifies disk, model hashes, overlay hashes, idle
cards, port ownership and the kernel journal.

An independent thread starts **before Docker launch** and samples every
**0.5 seconds**: MemAvailable, Committed_AS, each of the four workers' RSS,
container `memory.current` (also `memory.peak` when present), Mlocked and
Unevictable. RSS/cgroup/locked fields overlap; none are added to whole-host
pressure. Mlocked and Unevictable are host counters, not a complete attribution
of XPU-pinned buffers. Workers are found only in the container's cgroup.
Missing/denied fields are recorded as unknown, never zero.

Per-card free bytes are read only from Intel DRM sysfs `mem_info_vram_total`
and `mem_info_vram_used` when readable; PCI IDs and source paths are saved.
No XPU-SMI polling or device API fallback exists. If xe exposes no readable
counters, sampling skips VRAM, and the final receipt **cannot admit MTP1**
until four-card reserve evidence is available. Any reported rank below
**2 GiB free**, or host MemAvailable below **24 GiB**, latches STOP and sends
**one SIGINT**. The existing stricter loader allocation checks remain active.
Missing host observations also cancel. There is no restart or hard-kill escalation.

Only GET `/health` and GET `/v1/models` are sent. After health 200 and the
expected model ID, the controller records a **20-second plateau**, then sends
one SIGINT and waits up to 300 seconds for clean exit. No protocol client or
generation request is started. A timeout preserves the container for owner
review. Samples continue through shutdown. `calibration-load.json` contains
loading (construction through capture), plateau and shutdown peaks, raw-sample
hash, configuration identity, exit status and a recomputable verdict.

MTP1 admission requires a complete plateau with all worker/cgroup fields,
**plateau whole-host pressure × 1.15 ≤ 90,000,000,000 bytes**, observed loading
peak ≤90 GB, and **minimum free VRAM ≥4 GiB on every rank** throughout loading
and plateau. It also requires no watchdog/fault/sample failure, no sampling
gap above 1.5 seconds, and exit code zero without OOM. This is memory admission
only; quality and speed still need their own gates.

After reviewing a passing receipt and leaving the five-minute stop-to-launch
gap, use a fresh MTP1 run with that receipt explicitly supplied:

```sh
SCREEN_PRIVILEGED_FD_SCAN=1 python3 /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/screen.py run --mode mtp1 --calibration /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runs/screen1b-calibrate-load/calibration-load.json --run-dir /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runs/screen1b-mtp1-calibrated --execute
```

The gate rechecks sample hashes and recomputes the verdict. Image, overlay,
placement, model metadata, controller and runtime flags must match; only
run-directory/name and port vary. Full model hashing still runs again.
A failed/unknown receipt never unlocks generation, and this receipt cannot
admit MTP0 or MTP3. Use `--dry-run` to preview either command without operations.
