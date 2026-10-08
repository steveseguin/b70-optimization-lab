# Flash-Next Screen 1b — native FP8 mmap adapter

**Current: attempt 6 prepared on CPU, not launched.** Attempt 5 cleared the
large host-memory shadow but failed the initial usable-VRAM check. The new
v5 mask offloads 2,600 experts/rank and uses utilization 0.90. Predicted host
pressure is **77.955 GB**; engine VRAM is **23.334 GiB/rank**, with **1.281 GiB**
headroom below the 90% line on rank 0 even after startup-unavailable memory.
These are unqualified estimates; existing memory and quality gates remain.
[Full budget, source comparison, latency sensitivity and attempt-6 command](ATTEMPT6.md).
Earlier attempt commands below are historical; use the attempt-6 command.


**Attempt 5 is prepared; nothing was launched.** All four Screen 1b modes now
set `NEOReadDebugKeys=1 EnableDeferBacking=0` in the container. These are
per-process Intel NEO driver settings, not host settings. The entrypoint
requires them before runtime imports. [LTX's October 4 measurement](../../ltx25-b70/notes/2026-10-04-host-ram-shadow-of-vram.md)
shows that they remove host backing of device buffers while keeping peer sharing.

Attempt 4's saved launch and image defaults omitted both. Its sampled pressure
peaked at **90.013 GB**, including **74.063 GB of GPUActive**, during construction;
the loader then cancelled before readiness. The new predicted host peak is
**35.505 GB**, subtracting the old **52.260 GB** residual while retaining the
10 GB runtime/remaining-driver contingency. This is an unmeasured scenario;
all memory, VRAM, health, identity and quality gates remain. **185/185 CPU tests
pass, zero skips.** The certified 115.87 GB remains a historical measurement,
but includes possible driver shadow and is not an irreducible host-buffer need.

[Memory curve, certified-lane audit, exact prediction and attempt-5 command](VALIDATION.md#attempt-5-per-process-driver-backing-cpu-only-preparation).

## Historical attempt 3/4 preparation

The following entries preserve the earlier diagnosis and commands. Attempt 4
was subsequently run by the owner; use the attempt-5 command linked above.

**attempt 3: stopped by the internal 80 GB host-memory guard during model
construction. TP1 caused the stop; TP0's expert-map traceback was a consequence.**
The first refusal records **80,005,660,672 bytes** in use and a 2,048-byte next
conversion. The sampler peaked at **79,478,317,056 bytes** just after the stop.
No expert-map geometry, dtype/device or overlay-signature error is recorded.

The fix preserves the first stop reason and exact memory counters in subsequent
cancellation errors, and records the loader exception separately. The sampler
now retains all KiB-valued meminfo counters (including GPUActive when available)
and cgroup memory.stat for the next attribution check. **This is a diagnosis and
coverage fix, not a proven RAM-fit fix.** For attempt 4, calibrate-load alone
now uses `--loading-ram-guard-gb 90` (decimal GB, also the default). The loader
cancels only when projected host use exceeds 90,000,000,000 bytes; the old
32 GiB available-memory floor does not apply in this mode. With attempt 3's
MemTotal, that leaves 34.18 GB (31.83 GiB) available. The separate watchdog
still sends SIGINT at MemAvailable <24 GiB. MTP0/MTP1/MTP3 keep their old
80 GB/32 GiB guard; MTP1's plateau +15% ≤90 GB gate is unchanged.
The parameter travels through the systemd worker into `launch.json`, loader
admission/refusal events, and `calibration-load.json` (`loading_ram_guard_bytes`).
It accepts whole decimal GB from 1 through 90, only in calibrate-load mode.
[Threshold validation](VALIDATION.md#attempt-4-calibration-loading-threshold).

The CPU rehearsal now asserts the real V30 factory → ExpertMapManager →
`determine_expert_map` path on **all four ranks**, using the actual certified v5
placement: 512 global / 128 local experts, int32 linear maps, int64 address
tables, and every one of the 48 host/resident masks. It also replays the exact
refusal counters and sibling cancellation at the expert-map assignment.
**171/171 CPU tests pass, no skips.** Full-size memory, native device behavior,
MTP construction and output parity remain unqualified.

Measured pressure rose from **5.695 GB after hashing** to **80.006 GB** after
7.408 seconds of model construction. Only **3.740 GB** of completed expert-host
allocations had receipts, versus **16.705 GB** predicted final pins. The complete
**87.765 GB** prediction remains unvalidated; no checkpoint loading, PLE binding,
ready plateau or complete allocation snapshot was reached.
[Full curve, first-cause evidence and coverage](VALIDATION.md#calibrate-load-attempt-3-memory-guard-cancellation).
[Measured samples and phase labels](evidence/attempt3-partial-memory.csv).

**Attempt 4 command, prepared only; not executed.** It requires a fresh
owner-provided health receipt and an exclusive idle-card window, with the
existing stop gap and admission checks. It is a diagnostic retry, not a claim
that the memory problem is solved. This CPU task used no GPU, Docker, server,
installation, secrets, host settings, Git branches/commits or port 8188.

```sh
SCREEN_PRIVILEGED_FD_SCAN=1 python3 /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/screen.py run \
  --mode calibrate-load --loading-ram-guard-gb 90 \
  --health-receipt /PATH/TO/FRESH-HEALTH-RECEIPT.json \
  --run-dir /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runs/screen1b-mmap-calibrate-load-20261008-attempt4 \
  --execute
```

## Attempt 2 (historical; superseded by the diagnosis above)

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

**Historical attempt-3 preparation (it subsequently ran and failed as above).** Replace the placeholder below; keep the existing idle-card,
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

The earlier, pre-driver-fix unqualified prediction was **87.765002 GB (81.737528 GiB)** of host
pressure, with **16.704864 GB** of final pins. The full 51.200246 GB table stays
file-backed. Cache metadata, staging, active-page allowance and the historical
unexplained memory residual were included. The current scenario above removes that
residual only when both driver settings are explicit. See [prediction](host-memory-prediction.json),
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

MTP0/MTP1/MTP3 guards and all watchdog thresholds stay unchanged. Calibration
uses the explicit 90 GB loading guard described above. The measured plateau margin and
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
scenario can still trip this stricter watchdog. Calibrate-load alone replaces
the loader limits with the explicit 90 GB host-use line; its independent
watchdog retains the 24 GiB available-memory hard stop.

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

Attempts 1–4 failed before readiness as recorded in VALIDATION.md. These attempt-5 commands are prepared
for the owner and **were not executed in this CPU-only fix**. First arrange exclusive idle cards and the existing
recovered-boot admission above, with at least five minutes after the previous
server stops.
No mode displaces LTX, uses port 8188, installs anything, or pulls an image.
The pinned image must already exist. Existing `SCREEN_PRIVILEGED_FD_SCAN` and
`SCREEN_SUDO_PASSWORD_FILE` settings pass through to the systemd worker; only
the opt-in fd scan uses that existing privileged path. The sampler never does.

```sh
SCREEN_PRIVILEGED_FD_SCAN=1 python3 /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/screen.py run --mode calibrate-load --loading-ram-guard-gb 90 --health-receipt /PATH/TO/FRESH-HEALTH-RECEIPT.json --run-dir /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runs/screen1b-mmap-calibrate-load-20261008-attempt5 --execute
```

This command uses the fresh `runs/screen1b-mmap-calibrate-load-20261008-attempt5/`.
The original run directory, STOP latch and failed calibration stay intact.
The controller default remains `runs/screen1b-calibrate-load/`; choose another
fresh `--run-dir` if the selected directory exists. The mode uses **the MTP1 model/runtime configuration**, with only the loading guard changed, including
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
**one SIGINT**. The loader also checks projected host use against the explicit
90 GB threshold before each admitted allocation.
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
SCREEN_PRIVILEGED_FD_SCAN=1 python3 /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/screen.py run --mode mtp1 --health-receipt /PATH/TO/FRESH-HEALTH-RECEIPT.json --calibration /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runs/screen1b-mmap-calibrate-load-20261008-attempt5/calibration-load.json --run-dir /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runs/screen1b-mtp1-calibrated --execute
```

The gate rechecks sample hashes and recomputes the verdict. Image, overlay,
placement, model metadata, controller and runtime flags must match; only
run-directory/name and port vary. Full model hashing still runs again.
A failed/unknown receipt never unlocks generation, and this receipt cannot
admit MTP0 or MTP3. Use `--dry-run` to preview either command without operations.
