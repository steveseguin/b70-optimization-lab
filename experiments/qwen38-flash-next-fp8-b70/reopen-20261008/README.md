# Flash-Next Screen 1b — native FP8 mmap adapter

**attempt 2: failed at worker init: the loader guard mistook a device-only
RoPE conversion for host staging and rejected 402,653,184 bytes (384 MiB).**
TP0 triggered the stop; TP1's `LoadCancelled` was a consequence. Available host
RAM stayed at or above **95.081541632 GB**; the container exited 1, without OOM.

Fixed in `overlay/vllm/screen1b_guard.py:268`: same-device XPU conversions and
payload-free meta conversions pass through unchanged. CPU conversions and
host/device transfers keep their staging cap, cancellation and cleanup checks.
The meta case was another startup blocker found by the new rehearsal.

**163/163 CPU tests pass, no skips**, including four logical-rank rehearsals
through the real V30 model and loader, an old-guard failure reproduction, and
nine conversion checks. The rehearsal uses the actual config with smaller
sizes, real CPU tensor arithmetic, tiny synthetic checkpoint weights, and
emulated device allocation/transport and CCL metadata. It covers the vision
and language constructors, PLE mmap binding, v5 placement, weight staging,
post-load processing, row-byte checks and allocation receipts. It cannot
qualify native XPU kernels, CCL, graph capture, full-size memory or output parity.
[Detailed coverage, limits and evidence](VALIDATION.md#calibrate-load-attempt-2-worker-init-failure).

**Attempt 3 is prepared, not launched. A fresh owner-provided health receipt is
required.** Replace the placeholder below; keep the existing idle-card,
five-minute stop gap and admission checks. This CPU-only task made no commits
and did not operate Docker, devices, servers, secrets, host settings or port 8188.

```sh
SCREEN_PRIVILEGED_FD_SCAN=1 python3 /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/screen.py run \
  --mode calibrate-load \
  --health-receipt /PATH/TO/FRESH-HEALTH-RECEIPT.json \
  --run-dir /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runs/screen1b-mmap-calibrate-load-20261008-attempt3 \
  --execute
```

## Attempt 1 (historical)

**calibrate-load attempt 1: failed at worker init: re-entrant copy dispatch
double-reserved staging space and triggered the 120-second allocation-lock
timeout.** The 16:44–16:51 UTC attempt exited 1 at 16:50:55 UTC, before readiness.
The loader's bounded UVA copy called `copy_` under its own `CopyMode`; the mode
bounded that same copy again. A 268,431,360-byte reservation left just 4,096
bytes of the 256 MiB budget, causing thousands of tiny copies. Rank 1 recorded
157,290 reservations; ranks 0 and 2 timed out while waiting for the lock.
The later EngineCore error was the wrapper, not the cause. Host MemAvailable
bottomed at **106,956,197,888 bytes (106.956 GB, about 107 GB)** and
`OOMKilled=false`; this attempt does not establish the model's memory fit.

The overlay now marks only an already-admitted leaf copy so its dispatch hook
passes through without a second reservation. It restores the marker on error.
The byte cap, rank serialization, cancellation checks and timeout remain.
**149/149 CPU tests pass, no skips**, including four new real CPU dispatch tests
that construct the UVA offloader with stubbed pin/platform interfaces. Three
of those checks failed against the original code. Overlay hashes are refreshed;
entrypoint and controller behavior need no change. [Diagnosis and validation](VALIDATION.md#calibrate-load-attempt-1-worker-init-failure).
No launch occurred during this fix. Attempt 1's raw receipts remain unchanged.

**CPU implementation complete; runtime qualification remains open.** PLE now
uses the original safetensors shards through read-only mmap, a fixed **1 GiB
pinned raw-row clock cache per rank (4 GiB total)**, and small stable step
buffers. The original hash, TP ownership, int8 byte reduction and scale/cast
arithmetic remain. No PLE requantization or checkpoint rewrite occurs.

The updated unqualified prediction is **87.765002 GB (81.737528 GiB)** of host
pressure, with **16.704864 GB** of final pins. The full 51.200246 GB table stays
file-backed. Cache metadata, staging, active-page allowance and the historical
unexplained memory residual are included. See [prediction](host-memory-prediction.json),
[shared inputs](memory-contract.json), and [latency/exactness design](../notes/2026-10-08-host-memory-reduction-design.md).
The 4 GiB page allowance is an assumption, not an enforced page-cache ceiling.

**Earlier adapter validation: 126 CPU tests passed (77 + 22 + 27).**
Tests include direct safetensors reads of random/adversarial synthetic rows
and small actual checkpoint boundary reads. They do not qualify XPU transport,
graph replay, V30 arithmetic or generated outputs. The synchronous pre-forward
fetch puts misses on the critical path; no overlap or speedup is claimed.
[Validation and exact command](VALIDATION.md).

The loader serializes copy sections across ranks and caps aggregate live
staging at **256 MiB**, retaining CPU conversion reservations through storage
lifetime. Final expert placement and full 16-bit KV are unchanged. At load and
capture completion, `allocations-rank<N>.json` records unique pinned/device
storage by group, observed mmap RSS (or null), actual geometry, and prediction
inputs. `loader-<pid>.jsonl` and `staging-live.json` retain allocation events
and the global staging peak. Graph/driver/private-runtime allocations remain
unqualified. The overlay manifest seals the adapter, loader, contract and
predictor before the container entrypoint can apply them.

MTP0/MTP1/MTP3 commands, calibrate-load behavior and watchdog thresholds stay
unchanged. The **80 GB/32 GiB internal guard**, measured plateau margin, and
known **4 GiB/card reserve conflict** still block any claim of admission.
The next-attempt command below has **not been executed**. This task made no commits; no GPU, Docker, server, installation, secret, host setting or
port 8188 operation occurred.

## Earlier full-PLE memory reconstruction (historical)


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
These historical alternatives use native host PLE, full 16-bit KV at **376,569,856
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
python3 /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/screen.py run --mode mtp1 --health-receipt /PATH/TO/FRESH-HEALTH-RECEIPT.json --execute
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


## Same-boot fault admission

`--health-receipt PATH` is required for any `--execute` action when the boot
journal contains a GPU fault or unexplained host stall. After one fault,
keep the evidence and use the result of the one bounded
[`check-four-card-health.py`](../../ltx25-b70/scripts/check-four-card-health.py)
probe. Screen reads that JSON; it never runs a recovery probe or reboots.

The checks mirror local LTX packet 115's `launch/serve-encoder.py`: receipt
schema, current boot ID, end time strictly less than six hours old, no faults
during the probe, and complete passing copy/GEMM evidence for xpu:0–3.
Only fault lines **older than the receipt end time** are admitted. The boundary
second is refused too because the probe records whole seconds. GPU fault
lines separated by at most 60 seconds form one incident; two or more incidents
anywhere in this boot refuse launch regardless of receipt, with an explicit
message that the owner must decide about rebooting.

`Xe device coredump has been deleted` is housekeeping and is ignored in both
admission and monitoring. Creation, timeout, reset and other GPU fault lines
still stop the run. LTX's specific known xe GuC host-stall classification is
retained; it never exempts a GPU fault. Timestamps include timezone and
microseconds, avoiding local/UTC ambiguity and an admission-to-start gap.

The worker rechecks admission after model hashing. Its run directory retains
`journal-admitted-faults.txt`, the complete preflight journal, and a copy and
SHA-256 of the health receipt. Startup, generation, calibration plateau and
postflight check for new faults after the admission cutoff; a new fault uses
the existing single-SIGINT shutdown, without retry or hard-kill escalation.

The commands below require a **fresh owner-provided health receipt**. The
attempt-1 receipt was used historically for attempt 2; it is not reused here.
A receipt does not waive memory, storage, idle-card, port or stop-gap checks.
These commands were not executed in this CPU-only change.

Synthetic CPU tests cover clean boot, recovered first incident, new fault,
second incident, deletion, receipt evidence/age, host-stall classification,
worker argument forwarding, live fault monitoring and graceful shutdown.
All **19 new tests pass**. The full system-Python suite ran **145 tests: 138
passed, seven existing dependency-related skips**; `git diff --check` passed:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s experiments/qwen38-flash-next-fp8-b70/reopen-20261008 -p 'test_journal.py' -v
```

## Owner-approved sequence: calibrate-load → mtp1

Attempts 1 and 2 failed as recorded above. These attempt-3 commands are prepared
for the owner and **were not executed in this CPU-only fix**. First arrange exclusive idle cards and the existing
recovered-boot admission above, with at least five minutes after the previous
server stops.
No mode displaces LTX, uses port 8188, installs anything, or pulls an image.
The pinned image must already exist. Existing `SCREEN_PRIVILEGED_FD_SCAN` and
`SCREEN_SUDO_PASSWORD_FILE` settings pass through to the systemd worker; only
the opt-in fd scan uses that existing privileged path. The sampler never does.

```sh
SCREEN_PRIVILEGED_FD_SCAN=1 python3 /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/screen.py run --mode calibrate-load --health-receipt /PATH/TO/FRESH-HEALTH-RECEIPT.json --run-dir /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runs/screen1b-mmap-calibrate-load-20261008-attempt3 --execute
```

This command uses the fresh `runs/screen1b-mmap-calibrate-load-20261008-attempt3/`.
The original run directory, STOP latch and failed calibration stay intact.
The controller default remains `runs/screen1b-calibrate-load/`; choose another
fresh `--run-dir` if the selected directory exists. The mode uses **the exact MTP1 launch command**, including
the ported v5 placement, native FP8 mmap adapter, unchanged weights, full
16-bit KV, graph configuration and bounded loader. Its admission comes from the watchdog, not a predicted
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
SCREEN_PRIVILEGED_FD_SCAN=1 python3 /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/screen.py run --mode mtp1 --health-receipt /PATH/TO/FRESH-HEALTH-RECEIPT.json --calibration /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runs/screen1b-mmap-calibrate-load-20261008-attempt3/calibration-load.json --run-dir /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runs/screen1b-mtp1-calibrated --execute
```

The gate rechecks sample hashes and recomputes the verdict. Image, overlay,
placement, model metadata, controller and runtime flags must match; only
run-directory/name and port vary. Full model hashing still runs again.
A failed/unknown receipt never unlocks generation, and this receipt cannot
admit MTP0 or MTP3. Use `--dry-run` to preview either command without operations.
