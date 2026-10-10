# Screen 1b CPU validation — native FP8 mmap, 2026-10-08

## Teardown application and probe preparation, 2026-10-09

The reviewed `overlay-fix-teardown/teardown.patch` applied cleanly with
`git apply --directory=experiments/qwen38-flash-next-fp8-b70/reopen-20261008`.
All 15 applied files exactly match the review's after-hashes and copies.
[Source-bound application receipt](evidence/teardown-applied-20261010/application.json).
The patch, copies, base sources, original review receipts and saved runs are
unchanged. The live manifest verifies **50 overlay files and 12 support pins**.
Image: `vllm/vllm-openai-xpu@sha256:e4446310b1d30015e8fdc1a0a2ef1669ac6bef857cbe772487571ed5c1a926a9`.
Overlay manifest SHA-256:
`21f4a79c000aa4cf9772082379b486384f5ac8bc1a38210c96c567f555ef7648`.
Patch SHA-256:
`3a9ea39d03d5888ed4c05eadd40c083216bfbe58dc6e35caeee2068d1fb71f62`.

Only application-related test fixtures changed: retained-module registration,
explicit mocked runners for `DeferredStop`, clean container-state JSON and
synthetic four-rank completion receipts passed through the real validator.
The frozen patch builder and application test now read their preimage from
Git `08b6217e8a8a85aede148863e44cd0f4194d1d78`, so applying the reviewed patch
does not rewrite its provenance. Historical result pins were not relabeled.

| CPU suite | Passed | Skipped | Total | Evidence |
| --- | ---: | ---: | ---: | --- |
| Lane | 207 | 6 | 213 | [Receipt](evidence/teardown-applied-20261010/lane.json), [log](evidence/teardown-applied-20261010/lane.log) |
| Existing slab probes | 25 | 1 | 26 | [Receipt](evidence/teardown-applied-20261010/probe.json), [log](evidence/teardown-applied-20261010/probe.log) |
| Reviewed teardown | 49 | 0 | 49 | [Receipt](evidence/teardown-applied-20261010/teardown.json), [log](evidence/teardown-applied-20261010/teardown.log) |
| New first-forward probe | 35 | 0 | 35 | [Receipt](evidence/teardown-applied-20261010/first-forward.json), [log](evidence/teardown-applied-20261010/first-forward.log) |

The combined probe discovery also passes: **60 passed, one prohibited skip,
61 total**, including the 35 new tests ([receipt](evidence/teardown-applied-20261010/probe-combined.json),
[log](evidence/teardown-applied-20261010/probe-combined.log)). Across the four
suite components above: **316 passed, seven skipped**, zero failures/errors.
The new tests use fake device/kernel objects and mocked child supervision;
they do not import Torch or allocate production-sized buffers. Coverage includes
geometry/routes, source pins, stage instrumentation, control-to-mixed refusal,
ordered teardown, valid rank receipt requirements, native-exit classification,
and no-kill timeout preservation. Independent source review found and corrected
cleanup timestamp order and retained exception tracebacks before these results.

The six lane skips are the real-checkpoint boundary test and all five
worker-init rehearsals (protected storage / `torch.xpu`). The seventh skip
is `test_guardian_records_native_signal_without_runtime_imports`: it kills
its child with SIGALRM and violates this task's explicit **never kill processes**
rule. Thus the earlier 26/26 probe result is preserved as historical evidence;
this restricted run honestly reports **25 passed, one skipped**. No GPU calls,
container operations, model server, device access, process kills or host setting
changes occurred. OMP, MKL and OpenBLAS were each limited to one thread.

```sh
p=experiments/qwen38-flash-next-fp8-b70/reopen-20261008
python3 -B "$p/overlay-fix-teardown/build_patch.py" --check
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 /home/steve/.venvs/ltx25-baseline/bin/python -B "$p/overlay-fix-teardown/run_cpu_tests.py" lane
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python3 -B "$p/overlay-fix-teardown/run_cpu_tests.py" probe # existing + first-forward
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python3 -B "$p/overlay-fix-teardown/run_cpu_tests.py" teardown
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python3 -B -m unittest discover -s "$p/probe" -p test_first_forward_probe.py -v
```

[Concrete prepared commands and preregistered interpretation table](probe/README.md#prepared-for-2026-10-10-written-2026-10-09).
The owner has resolved the boot halt by accepting continued operation, with
GPU work serialized behind LTX. The existing watcher's two-incident gate
still refuses that boot and needs coordinator reconciliation before execution;
no fault marker was removed and no admission check was weakened here.
First fault ends submissions: no retry, second arm, reset or automatic health
launch. Native queue/mapping release, full-model exact outputs, TP4 behavior
and clean fresh-runtime repetition remain unqualified.

## Attempt 7: exact large pinned allocations

**213/213 CPU tests pass, zero skips**, including all four rank rehearsals.
Sealed-package dry run and link checks pass.

Selected the owner-permitted torch allocator configuration alternative. No
native allocator, slab ownership change, placement edit or kernel change.
All aliases are set before Python import; entrypoint requires them and torch
2.13. Requests above 1 MiB bypass rounding and are not cached after free.
CPU receipts distinguish exact payload, prior rounded blocks and source-derived
allocator request bytes; they never label those as measured native reservations.

The synthetic packing comparison checks raw uint8/FP8/BF16 bytes, 512-byte base
alignment, contiguous subviews, shared storage, row strides and signed UVA
address-table reconstruction. The four-rank real model/loader rehearsals run the
selected separate-tensor path with the new policy in their environment. Native
pinning/USM, full-size peak, MTP/capture retention and native output gates remain
open. Snapshot tests use large logical sizes without allocating large buffers.
Additional checks cover all launch modes, conflicting legacy aliases, missing
configuration, 1 MiB boundaries, source hashes, exact versus old-size receipts,
96 GB boundary/cancellation and unchanged normal-mode/MTP1 gates.

Reproduce the complete suite and the budget without any accelerator operation:

```sh
SCREEN1B_CPU_EVIDENCE_DIR=experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/attempt7-exact-pins-cpu-rehearsal \
PYTHONDONTWRITEBYTECODE=1 /home/steve/.venvs/ltx25-baseline/bin/python -m unittest discover \
  -s experiments/qwen38-flash-next-fp8-b70/reopen-20261008 -p 'test_*.py' -v
python3 -B experiments/qwen38-flash-next-fp8-b70/reopen-20261008/attempt7_budget.py
```

[Test log](evidence/cpu-attempt7-exact-pins-tests.log),
[four-rank receipts](evidence/attempt7-exact-pins-cpu-rehearsal/),
[exact budget, source comparison and prepared command](ATTEMPT7-BUDGET.md).
No GPU, Docker, server, install, secret, Git branch/commit, host setting or
port 8188 operation was performed. Existing historical results below are intact.


## Attempt 6: VRAM placement and CPU verification

The new mask preserves every certified host expert row and extends each rank
to 2,600 rows. Utilization is 0.90. The predictor seals the new placement,
checks offload bytes against the memory contract, validates context/chunk/graph
geometry, and separately reports engine-only and startup-inclusive headroom.
Qualified phase bounds and measured admission gates remain unchanged.
**193/193 CPU tests pass, no skips**, including all four rank rehearsals.
Sealed-package dry run, focused local-link checks and `git diff --check` pass.
[Budget and exact next command](ATTEMPT6.md),
[startup source audit](evidence/attempt6-startup-source-audit.md),
[device census](evidence/attempt6-budget-source-audit.md),
[CPU test log](evidence/cpu-attempt6-tests.log),
[four-rank rehearsal receipts](evidence/attempt6-cpu-rehearsal/).

```sh
SCREEN1B_CPU_EVIDENCE_DIR=experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/attempt6-cpu-rehearsal \
PYTHONDONTWRITEBYTECODE=1 /home/steve/.venvs/ltx25-baseline/bin/python -m unittest discover \
  -s experiments/qwen38-flash-next-fp8-b70/reopen-20261008 -p 'test_*.py' -v
```

No runtime was launched and no commits were made. Historical validation and
failed-attempt receipts below remain intact.


## Attempt 5: per-process driver backing (CPU-only preparation)

**185/185 CPU tests pass, zero skips. New predicted host peak: 35.505 GB
(33.066 GiB), unmeasured.** Attempt 4 confirmed the missing host-memory
attribution: its saved `launch.json` and image defaults contain neither
`NEOReadDebugKeys` nor `EnableDeferBacking`. At the sampled host-pressure peak
of **90.013 GB**, `/proc/meminfo` recorded **74.063 GB of GPUActive**. Only
**15.950 GB** of that pressure remained after subtracting GPUActive; RSS and
cgroup figures overlap and are not added to it.

Every Screen 1b mode now passes `NEOReadDebugKeys=1 EnableDeferBacking=0`
explicitly into the container, before Python/driver initialization. The
entrypoint refuses missing or different values. Spawned workers inherit them.
These are **Intel NEO per-process driver settings**, not host settings. They
remove deferred host backing while retaining peer sharing; they do not select
new arithmetic, weight precision or KV precision. The measured precedent is
[LTX's October 4 host-shadow note](../../ltx25-b70/notes/2026-10-04-host-ram-shadow-of-vram.md).
Flash-Next still needs its own runtime and exact-output qualification.

The [attempt-4 analysis](evidence/attempt4-driver-shadow.json) includes input
hashes, environment checks and the certified-path search. The
[full memory curve](evidence/attempt4-partial-load.csv) joins samples to loader
allocation events by monotonic time. Seconds are relative to the first
`load_begin`; all memory columns below are decimal GB.

| Constructor seconds | Phase | MemAvailable | Host pressure | GPUActive | Completed expert-device allocations |
| ---: | --- | ---: | ---: | ---: | ---: |
| 0.028 | construction | 109.933 | 14.246 | 3.290 | 0.000 |
| 1.029 | construction | 101.199 | 22.980 | 9.876 | 3.662 |
| 2.029 | construction | 88.034 | 36.145 | 20.824 | 11.198 |
| 4.029 | construction | 65.591 | 58.589 | 43.110 | 30.735 |
| 6.035 | construction | 48.674 | 75.505 | 58.685 | 43.996 |
| 8.040 | construction, sampled peak | 34.167 | 90.013 | 74.063 | 56.520 |
| 14.041 | cancellation/drain | 117.882 | 6.297 | 0.000 | 56.520 cumulative |

The 17 construction samples correlate pressure with GPUActive at 0.99938,
and completed device allocations with GPUActive at 0.99935 (Pearson).
This establishes the timing and direct driver-memory attribution; it is not
an exact one-byte-per-device-byte census. The completed expert events omit
other/in-flight allocations and allocator retention; live VRAM counters were
unavailable. Cumulative allocation events do not fall when buffers are freed.
`server.log` places model construction at 18:46:46 UTC, PLE initialization at
18:46:47 and cancellation at 18:46:55. No checkpoint-load completion, capture
or readiness was reached. Rank 2's first refusal, between sampler ticks, saw
**90.384 GB**, slightly above the half-second sample peak. Worker RSS maxima
were 2.779–2.782 GB each; the cgroup peak was 11.514 GB (9.773 GB at the host
peak). GPUActive returned to 114,688 bytes during drainage. The guard stopped
construction without OOM or GPU fault, but container exit was **1**, and the
calibration receipt correctly remains failed rather than claiming a successful
clean calibration.

### Revised prediction and certified-lane interpretation

The old model carried `115.869876224 - 63.609487360 = 52.260388864 GB`
as an unexplained historical residual. The new scenario subtracts **only that
52.260 GB term**, conditional on both explicit container settings. It does
not subtract the entire device footprint from actual host buffers or subtract
GPUActive twice. The [prediction](host-memory-prediction.json) retains:

| Component | GB |
| --- | ---: |
| Final pinned buffers, including 4 GiB PLE cache | 16.704864256 |
| PLE metadata | 1.736346392 |
| Active file-page allowance | 4.294967296 |
| Nominal host baseline | 2.500000000 |
| Runtime/remaining-driver contingency | 10.000000000 |
| Aggregate bounded staging | 0.268435456 |
| **Predicted peak** | **35.504613400** |

Thus **87.765002264 - 52.260388864 = 35.504613400 GB**. Attribution of the
old residual is an assumption supported by attempt 4 and LTX, not an A367
GPUActive measurement. The 10 GB contingency remains for runtime differences,
private memory and remaining driver memory (LTX with the setting still peaked
at 3.6–3.7 GiB of driver memory). The nominal 2.5 GB baseline is below attempt
4's 4.929 GB post-hash baseline; this is an illustrative scenario with a
contingency, not a strict upper bound. Active file pages are not capped at the
allowance. `host_peak_bytes` remains null and prediction status **REFUSED**
until qualified bounds or a valid calibration supply the missing evidence.
The historical full-PLE/default-backing sweep stays labeled separately.

The requested search was:

```sh
rg -n 'NEOReadDebugKeys|EnableDeferBacking' repro/ results/ experiments/qwen38-flash-next-fp8-b70/tools/ patches/
```

It found **no Flash-Next occurrence**, including the frozen A367 launcher
and certification/replay paths. The sole match is an unrelated Gemma shim's
passthrough allow-list for `NEOReadDebugKeys`; it does not set either value.
There is no recorded evidence that the certified lane enabled the fix.
The older launcher can inherit shell variables, so absence from these saved
files cannot prove the contents of an unrecorded parent environment.

The certified **115.870 GB** remains the observed whole-host pressure change
under its original configuration. It is consistent with substantial driver
shadow, and is **not evidence of irreducible host tensor/RSS demand** or a
valid unchanged allowance for this new allocation policy. Do not rewrite the
old measurement or claim a measured corrected A367 peak. Four times 29.5 GiB
is **118 GiB = 126.702 GB**, a rough device-footprint scale, not an amount that
can safely be subtracted from the 115.870 GB measurement. CPU evidence alone
does not justify removing the PLE adapter or changing certified placement.

### Gates and CPU verification

All existing gates remain: 90 GB calibration loading guard, 24 GiB available
hard stop, 2 GiB/card emergency stop, 20-second plateau, plateau ×1.15 ≤90 GB,
4 GiB/card admission reserve, complete accounting and sample-gap checks,
model/overlay hashes, idle-card ownership, health receipt, journal, stop gap,
full 16-bit KV, output/quality gates and single graceful shutdown. The known
VRAM reserve conflict and missing live VRAM readings are still open.
Calibration and MTP1 identities match with these settings; older receipts
cannot admit the changed environment. Other generation modes retain their
80 GB / 32 GiB watchdog limits. No failed receipt is upgraded.

Six new CPU tests cover all four modes against a conflicting parent
environment, receipt identity, missing/wrong/duplicate environment values,
bounded prediction credit, and entrypoint refusal/acceptance before runtime
imports. The full suite includes four real-model CPU construction rehearsals.
[Full 185-test log](evidence/cpu-attempt5-driver-tests.log).
The [attempt-5 CPU dry run](evidence/attempt5-calibrate-load-dry-run.txt),
entrypoint shell syntax, `git diff --check` and `tools/check-doc-links.py`
also pass. Raw attempt-4 input hashes were rechecked unchanged.

```sh
PYTHONDONTWRITEBYTECODE=1 /home/steve/.venvs/ltx25-baseline/bin/python -m unittest discover \
  -s experiments/qwen38-flash-next-fp8-b70/reopen-20261008 -p 'test_*.py' -v
python3 experiments/qwen38-flash-next-fp8-b70/reopen-20261008/analyze_partial_load.py \
  experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runs/screen1b-mmap-calibrate-load-20261008-attempt4 \
  --output experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/attempt4-partial-load.json
```

### Attempt-5 command — prepared, not executed

Use a fresh health receipt and exclusive idle cards, observing the existing
five-minute stop gap. This is a load-only measurement with no generation.
The driver settings are supplied by the controller; no host exports are needed.

```sh
SCREEN_PRIVILEGED_FD_SCAN=1 python3 /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/screen.py run \
  --mode calibrate-load --loading-ram-guard-gb 90 \
  --health-receipt /PATH/TO/FRESH-HEALTH-RECEIPT.json \
  --run-dir /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runs/screen1b-mmap-calibrate-load-20261008-attempt5 \
  --execute
```

All attempt-4 raw receipts remain unchanged. No GPU, Docker, server, install,
secret, host-setting, port-8188 or Git branch/commit operation was performed.

## Attempt 4 calibration loading threshold

CPU-only change, 2026-10-08. Calibrate-load now defaults to the explicit
`--loading-ram-guard-gb 90` parameter (decimal GB). The systemd worker passes
it into the overlay as `B70_SCREEN1B_CALIBRATE_LOAD_RAM_GUARD_BYTES=90000000000`.
Only this mode replaces both old loader limits (80 GB host use / 32 GiB
available) with projected host use **>90,000,000,000 bytes**. Exactly 90 GB
is allowed, matching the admission ceiling. At attempt 3's MemTotal this
corresponds to 34.18 GB / 31.83 GiB available; no fixed 31 GB approximation
is used. The parameter accepts integer GB from 1 to 90; other modes reject it.

The threshold is retained in `launch.json`, admitted/refused loader events
(`pressure_limit_bytes`, `available_floor_bytes`, `calibrate_load`), and
`calibration-load.json` (`loading_ram_guard_bytes`). Model/runtime identity
normalization excludes only this calibration guard environment entry so the
receipt remains comparable to MTP1; other runtime settings remain identity-bound.
Both overlay payload hash pins were refreshed. Old run receipts are untouched.

The independent 0.5-second watchdog still sends one SIGINT at MemAvailable
<24 GiB. Cancellation reporting, memory-attribution sampling, generation-mode
limits and the **plateau ×1.15 ≤90 GB** MTP1 gate remain unchanged. No memory
fit or completed plateau is claimed. This supersedes the prior recommendation
to retry attempt 4 under the same 80 GB guard. The prepared command with a
placeholder health receipt is in the [README](README.md).

**179/179 CPU tests passed, zero skips**, including all four real-model CPU
construction rehearsals. Eight new tests cover attempt 3's pressure, exact
and over-limit boundaries (including projected growth and the old available
floor), configurable limits, invalid arguments, mode isolation, receipt fields
and first-cause retention. Existing controller tests now check worker argument
forwarding, `launch.json` recording and MTP1 identity equivalence; watchdog
and plateau-margin regression tests still pass.
[Full test log](evidence/cpu-attempt4-threshold-tests.log).

```sh
PYTHONDONTWRITEBYTECODE=1 /home/steve/.venvs/ltx25-baseline/bin/python -m unittest discover \
  -s experiments/qwen38-flash-next-fp8-b70/reopen-20261008 -p 'test_*.py' -v
```

No GPU, Docker, server, install, secret, host-setting, branch/commit or port
8188 operation occurred. Attempt 4 was not launched.

## Calibrate-load attempt 3: memory-guard cancellation

**attempt 3: the internal host-memory guard stopped TP1 during construction;
TP0 encountered that shared stop in `determine_expert_map`.** It is not an
expert-map failure. The unit/hash stage began at 18:09 UTC; the container receipt
runs **18:11:45.808–18:14:46.052 UTC**. No readiness, OOM, output or memory-fit
claim follows. `container-exit.json` records exit 1, `OOMKilled=false`.

### First cause, not traceback print order

The complete [server log](runs/screen1b-mmap-calibrate-load-20261008-attempt3/server.log)
shows TP1 at lines 306–395: `Fp8MoEMethod.create_weights` → v5
`allocate_weight` → CPU int64 address-table `.to(resident.device)` → guarded
conversion → `check_admission`. Its exception is **“next allocation exceeds
early stop margin”**, not a dtype or shape exception.

`loader-477.jsonl:271` records the first refusal at monotonic
**357096.617205949**: MemTotal **124,179,132,416**, MemAvailable
**44,173,471,744**, next bytes **2,048**. Subtraction gives
**80,005,660,672 bytes** already in use; projected pressure is
**80,005,662,720**, above the existing **80,000,000,000** limit. Available RAM
was still above the separate 32 GiB floor. The tiny address-table transfer
was where the excess was detected, not the source of 80 GB of consumption.
TP1 writes the first `cancel_requested` at **357096.618303304**. TP2, TP0 and
TP3 follow. TP0's lines 455–493 end in **“cancellation latched”**, while waiting
for copy admission at V30's expert-map slice assignment. The later parent and
EngineCore failures are consequences. The external calibration watchdog did
not trigger (`watchdog_reason=null`); the internal allocation guard did.

The map and both assignment operands are int32. Its 512 entries map this
rank's consecutive 128 global IDs to local IDs 0–127, leaving all other entries
−1. The v5 int64 table separately stores byte-address offsets and preserves
all 128 logical experts despite fewer device-resident rows. There is no
traceback evidence for geometry mismatch, an int64/device bug, or signature
drift. V30's map function is unchanged. The existing rehearsal already went
through the real constructors, but did not assert this call or use the actual
certified masks; a four-layer tiny fixture cannot exercise full-size pressure.

### Fix and explicit regression coverage

[screen1b_guard.py](overlay/vllm/screen1b_guard.py) now carries the first STOP
writer's reason into every later cancellation error. Memory refusals include
observed/projected pressure and requested growth; `load_failed` retains the
exception type and message. Later failures do not replace the original STOP.
Missing or partially written reasons still cancel safely. Both overlay pins
were refreshed. Thresholds, allocation arithmetic and placement are unchanged.

[calibration.py](calibration.py) additionally retains all KiB-valued meminfo
fields (including GPUActive/GPUReclaim if available) and cgroup memory.stat in
future samples. Counter units are retained: memory.stat includes byte values
and event counts. Missing attribution stays unknown. These overlapping fields
are never added to pressure and do not change admission. Attempt 3 did not
save these fields during construction, so driver/private-memory attribution
cannot be recovered from that run.

[worker_init_rehearsal.py](worker_init_rehearsal.py) now explicitly selects
linear placement and loads the hash-bound **actual** `placement-certified-v5.json`.
For each rank it executes and checks:

- Four real factory → ExpertMapManager → V30 `determine_expert_map` calls in
  reduced-size model construction, with exact values, int32 type, logical
  device, 512 global/128 local counts and no optional mask.
- All 48 certified layer masks against the real map, covering every local ID
  exactly once. The four constructed layers check actual host/resident sizes,
  preserved logical counts and int64 address tables. Synthetic weights verify
  at least one host and one resident row from the actual first-layer mask.
- The exact attempt-3 MemTotal/MemAvailable/2,048-byte admission refusal, without
  allocating those bytes, followed by a sibling STOP injected immediately
  after real `torch.arange` and caught at the real expert-map assignment.
  The resulting traceback must name `expert_map_manager.py` and the first
  memory-refusal reason. All of this uses CPU storage and emulated transport.

Four successful constructor maps plus 48 explicit map checks per rank make
**208 successful real-map calls**, plus four negative cancellation replays.
The pressure replay is synthetic evidence for guard behavior, never a memory
measurement. Original attempt-2 old-guard failure coverage remains. The
existing no-native-kernel/CCL/graph/MTP/full-size/output-parity limitations apply.
[Four rank receipts and traces](evidence/attempt3-cpu-rehearsal/).

### Partial measured host-RAM curve

The reproducible [analysis script](analyze_partial_load.py) reads the complete
364 half-second samples and all six loader logs, hashes its inputs, and joins
by monotonic time. [JSON analysis](evidence/attempt3-partial-memory.json),
[all measured points, bytes](evidence/attempt3-partial-memory.csv).
“In use” below means **MemTotal − MemAvailable**, not RSS plus pins. Seconds
are relative to the first `load_begin` (357089.209523809), not unit launch.
No point is extrapolated. The source sampler called the entire run “loading”;
the reconstruction separates cancellation/drain from construction.

| Observed stage | Seconds from construction | Bytes in use | Completed v5 parameters |
| --- | ---: | ---: | ---: |
| Before model hash | — | 5,701,885,952 | 0 |
| After model hash | — | 5,695,090,688 | 0 |
| Last startup sample before constructor | −0.230 | 14,722,813,952 | 0 |
| Early construction | 0.270 | 17,237,245,952 | 0 |
| Construction | 1.271 | 25,797,988,352 | 16 |
| Construction | 2.271 | 38,961,741,824 | 43 |
| Construction | 3.271 | 48,535,633,920 | 72 |
| Construction | 4.271 | 56,847,196,160 | 98 |
| Construction | 5.271 | 64,798,928,896 | 118 |
| Construction | 6.277 | 71,692,849,152 | 139 |
| Last sampler point before refusal | 7.277 | 78,731,689,984 | 162 |
| TP1 allocation-refusal observation | 7.408 | **80,005,660,672** | 164 completed receipts |
| Sampler peak, already cancelling | 7.777 | 79,478,317,056 | 164 |

The refusal's available RAM is **44.173 GB**; the sampler minimum is
**44.701 GB**. The user's “about 75 GB” is **79.478 decimal GB / 74.02 GiB**
in the sampler, using this host's actual 124.179 GB MemTotal. The first
refusal is **80.006 GB / 74.51 GiB**. Half-second sampling alone missed it.

Final completed v5 receipts are:

| Rank / PID | Last completed layer (zero-based) | Parameters | Host bytes | Device tensor bytes |
| --- | ---: | ---: | ---: | ---: |
| 0 / 450 | 17 | 36 | 742,195,200 | 10,582,425,600 |
| 1 / 477 | 22 | 46 | 1,096,089,600 | 13,374,259,200 |
| 2 / 512 | 19 | 40 | 865,075,200 | 11,717,836,800 |
| 3 / 547 | 20 | 42 | 1,037,107,200 | 12,174,950,400 |
| Total | — | 164 | **3,740,467,200** | **47,849,472,000** |

Rank 1 was constructing layer 23 when it refused. These are completed tensor
allocation events, not RSS or measured VRAM residency; the in-progress
allocation is absent. There are **no `allocations-rank*.json` snapshots**:
those are emitted after load completion, which was never reached. There are
no PLE mmap/index/coverage events. The checkpoint-copy, postprocessing, MTP,
KV, capture and ready phases were not reached. The shared staging ledger is
empty after drain, with peak **268,431,360 bytes**, below its 268,435,456-byte cap;
all **263** reservations across the four workers have matching releases.

Container memory.current peaked at **11,503,972,352 bytes** (memory.peak
**11,504,226,304**). Separate per-rank RSS peaks were **2,770,513,920 /
2,770,341,888 / 2,772,836,352 / 2,783,797,248 bytes**. These overlap and peak at
different instants; neither their sum nor the cgroup total explains whole-host
pressure. Mlocked/Unevictable also do not account for all driver-managed pins.
The missing RAM categories remain unattributed, not assigned to a guessed leak.

### Comparison with the prediction

| Quantity | Prediction | Attempt-3 observation |
| --- | ---: | ---: |
| Whole-host complete peak | 87,765,002,264 bytes, illustrative | 80,005,660,672 bytes at partial construction |
| Host baseline | 2,500,000,000 bytes assumed | 5,695,090,688 bytes after hashing |
| Final pins | 16,704,864,256 bytes | 3,740,467,200 bytes in completed expert-host events only |
| Global staging cap | 268,435,456 bytes | 268,431,360-byte ledger peak |
| Construction phase bound | Unknown (`null`) | Partial peak observed; phase incomplete |
| Later phases / final fit | Unknown | Not reached |

Pressure increased **74,310,569,984 bytes** from the post-hash baseline. The
partial observation is only **7,759,341,592 bytes below** the illustrative
complete peak, while many layers and later phases remain. That difference is
not spare memory or a prediction error estimate. The measured baseline alone
exceeds the assumed baseline by 3,195,090,688 bytes. Do not scale partial
layers to a complete load, substitute historical full-PLE candidate rows for
the mmap adapter, or mark the 87.765 GB scenario calibrated/passing.

**The memory-fit blocker is unresolved.** The guard performed its intended
job. There is no supported expert-map patch that fixes it, and this CPU-only
work does not establish which unmeasured allocation owns the remaining host
pressure. The next diagnostic command is in the README, using fresh
`attempt4` and `/PATH/TO/FRESH-HEALTH-RECEIPT.json`; it was not run and may stop
at the same guard. A fresh receipt does not waive exclusive ownership, memory,
five-minute stop gap or VRAM checks. Attempt 3's failed receipt cannot admit
MTP1. Raw run files and the prediction are preserved unchanged.

### CPU validation

**171 passed, zero failures, zero skips** in the existing LTX interpreter:
163 previous tests, four first-cause checks, three raw-receipt reconstruction
checks and one added memory-attribution test; all four rehearsal tests now
include the new real-map and pressure coverage. System Python discovers 171:
146 pass, 25 dependency skips. The initial run caught a reporting-test mistake:
it expected the post-cancellation sampler peak in the pre-refusal interval;
the assertion was corrected to 78,731,689,984 bytes, and the full suite rerun.
[Final log](evidence/cpu-attempt3-tests.log),
[initial log](evidence/cpu-attempt3-tests-initial.log),
[validation receipt](evidence/cpu-attempt3-validation.json).

```sh
SCREEN1B_CPU_EVIDENCE_DIR=experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/attempt3-cpu-rehearsal \
PYTHONDONTWRITEBYTECODE=1 /home/steve/.venvs/ltx25-baseline/bin/python -m unittest discover \
  -s experiments/qwen38-flash-next-fp8-b70/reopen-20261008 -p 'test_*.py' -v

python3 experiments/qwen38-flash-next-fp8-b70/reopen-20261008/analyze_partial_load.py \
  experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runs/screen1b-mmap-calibrate-load-20261008-attempt3 \
  --output experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/attempt3-partial-memory.json
```

No device, Docker, server, installation, secret, host-setting, branch/commit
or port 8188 operation occurred. The live LTX lane was untouched.

## Calibrate-load attempt 2: worker-init failure

**attempt 2: failed at worker init: device-only RoPE conversion incorrectly
charged to the host staging cap.** The 17:21–17:26 UTC run is preserved in
[runs/screen1b-mmap-calibrate-load-20261008-attempt2/](runs/screen1b-mmap-calibrate-load-20261008-attempt2/server.log).
The first cause is TP0, `server.log:255–279`: QSA → `get_rope` →
`MRotaryEmbedding` → `RotaryEmbeddingBase.__init__:61`, `cache.to(dtype)`.
The overlaid `screen1b_guard.py:267–274` (attempt-2 lines) charged every
`aten._to_copy` as host staging, including this XPU FP32→BF16 cache conversion:
`LoadCancelled: conversion exceeds 256 MiB: 402653184`.
The real config gives 262,144 positions × 4 (MRotary's cache extension) × 64
rotary dimensions × (4-byte source + 2-byte destination) = 402,653,184 bytes.
The rank-0 loader receipt records `unbounded loader conversion` at monotonic
354224.473663639. TP1 reports cancellation at 354224.48018927; its placement
`torch.empty(..., device='meta')` frame is where it noticed STOP, not the cause.
The [calibration receipt](runs/screen1b-mmap-calibrate-load-20261008-attempt2/calibration-load.json)
records minimum MemAvailable **95,081,541,632 bytes**; exit was 1 and
`OOMKilled=false`. No readiness or fit was established.

The fix is [screen1b_guard.py](overlay/vllm/screen1b_guard.py), beginning at
line 268. It preserves the original operation for conversions staying on the
same XPU and for destinations on `meta` (metadata without storage). The latter
also matters: the rehearsal exposed V30's `record_metadata_for_reloading` →
`capture_layer_to_meta` → `tensor.data.to("meta")` as another erroneous staging
charge. Host→host, host→device, device→host, and cross-device conversions still
use the bounded ledger. STOP is checked before either exemption. The copy
re-entry fix, 256 MiB production cap, admission thresholds and launch flags
are unchanged. Both manifest hashes for the guard were refreshed.

### Real-source worker-init rehearsal

[worker_init_rehearsal.py](worker_init_rehearsal.py) imports the overlay first
and missing files from `/home/steve/src/lumnus-20261008/vllm`, without modifying
either the clone or any installed package. Existing LTX Python provides torch
2.14.0+xpu on CPU; missing Python dependencies come from the existing
`/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages` through a read-only
fallback path (no `.pth` execution or installation). No official-image Python
execution or official-wheel compatibility is claimed. Each receipt pins every
imported vLLM source file and the actual model `config.json` by SHA-256.

The four isolated CPU processes execute:

- Real `DefaultModelLoader.load_model` → guarded load → `create_model` →
  `initialize_model` → `Qwen4ExpForConditionalGeneration`, including a small
  vision tower, HC, three GDN layers, PLE, one QSA/MRotary layer and FP8 MoE.
- Real `Fp8MoEMethod.create_weights`, v5 host/resident allocation, address
  tables and restored metadata: 512 global/128 local experts, eight placed
  parameters per rank. The small placement fixture uses host rows 0, 2, 127
  in each layer. Actual CPU storage is aligned to 256 bytes for the table.
- Real default-loader lazy safetensors iteration, global PLE index validation,
  mmap cache binding, skipped PLE payloads, shard-coverage checks, parameter
  loaders, and post-load processing. Fifteen synthetic tensors cover four
  PLE shards, its FP32 scale, input embedding, and gate/up/down weights for
  both host and resident experts. Loaded rows are checked against their bytes.
- Real PLE hash, mmap row gathering and pre-forward step replacement with two
  input sequences; owned rows match original synthetic FP8 bytes and nonowned
  rows are zero. No full forward or generated-answer claim follows.
- Real allocation receipts and bounded staging, with a reduced **1 MiB** test
  cap to force chunking. Live reservations must drain to zero; all four rank
  snapshots include expert pins, PLE cache/steps and explicit unknown runtime
  memory. The tiny contract is labeled `fixture_only`; these are not physical
  XPU pin or memory-fit measurements.

Only hardware interfaces are substituted: platform capability/selection,
CPU-backed logical XPU allocations/transfers/UVA, pin labels, synchronization,
memory-counter query and CCL group metadata. Native kernels raise if called;
accelerator initialization/query entry points are blocked. Model constructors,
config parsing, loader, PLE adapter, placement and guard are not mocked.
Process-local cache paths use temporary directories and imports are offline.

Sizes are deliberately reduced (four target layers, one vision block, hidden
128, vocabulary 256, PLE 2,816 rows × 160 bytes, 5,120-byte row cache/rank,
32 step tokens, RoPE maximum 8,192). Expert count, PLE head width, native FP8
and BF16 types, and the relevant constructor branches stay intact. The
rehearsal does **not** cover the MTP draft constructor, real distributed worker
startup/IPC, native XPU allocator/pins/UVA addresses or kernels, CCL transport,
graph capture, the complete original checkpoint, full-size memory pressure,
output identity, performance, or official-image dependency/ABI differences.
It is a startup regression test, not runtime qualification.

The hash-pinned old guard (`e1940e561f559cf92b846c94380da2b270674332` Git blob,
SHA-256 `f34291011176d86fcd1ce36908f90d26fa7422c744ace2f47cf9324a3e8e73cf`)
fails inside the **real MRotary constructor**, at `cache.to(dtype)`, with
12,582,912 bytes against the reduced 1 MiB cap. The fixed guard passes all
four ranks. [Negative traceback](evidence/attempt2-cpu-rehearsal/attempt2-guard-negative.log),
[rank 0](evidence/attempt2-cpu-rehearsal/rank0.json),
[rank 1](evidence/attempt2-cpu-rehearsal/rank1.json),
[rank 2](evidence/attempt2-cpu-rehearsal/rank2.json),
[rank 3](evidence/attempt2-cpu-rehearsal/rank3.json).

### Validation and next command

**163 passed, zero failures, zero skips:** 149 previous checks + nine conversion
checks + four full rehearsal ranks + one old-guard negative control.
System Python: **163 discovered, 138 passed, 25 dependency-related skips**.
[Validation receipt](evidence/cpu-attempt2-validation.json).

```sh
SCREEN1B_CPU_EVIDENCE_DIR=experiments/qwen38-flash-next-fp8-b70/reopen-20261008/evidence/attempt2-cpu-rehearsal \
PYTHONDONTWRITEBYTECODE=1 /home/steve/.venvs/ltx25-baseline/bin/python -m unittest discover \
  -s experiments/qwen38-flash-next-fp8-b70/reopen-20261008 -p 'test_*.py' -v
```

Attempt 3 — **prepared only; fresh owner-provided health receipt required**:

```sh
SCREEN_PRIVILEGED_FD_SCAN=1 python3 /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/screen.py run \
  --mode calibrate-load \
  --health-receipt /PATH/TO/FRESH-HEALTH-RECEIPT.json \
  --run-dir /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runs/screen1b-mmap-calibrate-load-20261008-attempt3 \
  --execute
```

The placeholder is intentional. No health probe or launch was run. Both failed
run directories and their STOP latches remain untouched. Existing five-minute
gap, idle-card and health/memory admission checks still apply. No Docker, GPU,
server, install, secret, host-setting, branch, commit or port 8188 operation
occurred. Concurrent LTX work was preserved.

## Calibrate-load attempt 1: worker-init failure

**calibrate-load attempt 1: failed at worker init: re-entrant copy dispatch
double-reserved staging space and triggered the 120-second allocation-lock
timeout.** No ready plateau or generation occurred. Exit 1 at
2026-10-08 16:50:55.184240446 UTC; `OOMKilled=false`.

Read all 520 lines of [server.log](runs/screen1b-mmap-calibrate-load-20261008/server.log)
and parsed all **331,109 loader receipt rows** plus all 554 host samples.
The failing chain is `UVAOffloader._make_cpu_data` at
`overlay/vllm/model_executor/offloader/uva.py:89` → `bounded_copy` →
`target.copy_` → `CopyMode.__torch_dispatch__` → `bounded_copy` again.
In attempt 1's `overlay/vllm/screen1b_guard.py`, the unprotected call was
line **192**, the second interception **253**, and the resulting lock timeout
**130**. The source fix is in [screen1b_guard.py](overlay/vllm/screen1b_guard.py).

Rank 1 (PID 477) reserved **268,431,360 bytes**, leaving **4,096 bytes** under
256 MiB. The second interception split the already-budgeted copy into 4,096-
and 2,048-byte transfers, each with ledger writes and synchronization. Its
embedding copy occupied the lock for about **114 seconds** and it recorded
**157,290 reservations** overall. Rank 3 then took the lock; ranks 0 and 2 hit
their 120-second wait at 16:50:48 UTC and latched STOP. Other workers' cancelled
exceptions and EngineCore's `core.py:1375` message follow that failure.
All reservations were released. No allocation-pressure refusal occurred.

The host trace minimum is **106,956,197,888 bytes available (106.956 GB)**;
the external watchdog did not trip. This is a loader control-flow failure,
not evidence of memory exhaustion or of a successful full-model fit.
The [failed calibration](runs/screen1b-mmap-calibrate-load-20261008/calibration-load.json)
and all original receipts are preserved, including their original identity hashes.

Fix: a thread-local marker covers just the admitted leaf `copy_`. The loader's
copy hook passes that operation through to lower dispatch layers without
reserving the same bytes twice. A `finally` restores the marker even on errors;
the outer owner still synchronizes and releases the reservation. Ordinary
copies and conversions remain guarded. No increase to the staging cap or
lock timeout; no change to entrypoint or `screen.py` is needed. The overlay
manifest now seals the corrected guard.

[Four new CPU regressions](test_copy_dispatch.py) import and construct the real
UVA offloader inside the real loader `TorchDispatchMode`, with tiny CPU tensors
and stubbed pin/platform/synchronization interfaces. They cover exact-cap
copies, row-rounding remainders, ordinary copies after an explicit copy,
dtype conversion, exact data, reservation counts, and exception cleanup.
Against the old guard, three tests failed (two count mismatches and one
`no transient staging headroom` exception); all four pass after the fix.
Existing two-process serialization, retained-conversion, cancellation,
overlay application, health-receipt and calibration tests also pass.

Full suite: **149 passed, zero failures, zero skips** using the existing
interpreter below. System Python: **149 discovered, 138 passed, 11
dependency-related skips**. All 47 overlay hashes verify; all overlay Python
parses; shell syntax and `git diff --check` pass. The attempt-2 command was
previewed with `--dry-run` only. [CPU validation receipt](evidence/cpu-worker-init-validation.json).
No installs or accelerator calls. No GPU/runtime qualification is claimed.

```sh
PYTHONDONTWRITEBYTECODE=1 /home/steve/.venvs/ltx25-baseline/bin/python -m unittest discover \
  -s experiments/qwen38-flash-next-fp8-b70/reopen-20261008 -p 'test_*.py' -v
```

Next attempt (prepared only; fresh result directory):

```sh
SCREEN_PRIVILEGED_FD_SCAN=1 python3 /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/screen.py run --mode calibrate-load --health-receipt /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runs/screen1b-mmap-calibrate-load-20261008/postflight-after-calibrate.json --run-dir /home/steve/llm-optimizations/experiments/qwen38-flash-next-fp8-b70/reopen-20261008/runs/screen1b-mmap-calibrate-load-20261008-attempt2 --execute
```

That receipt passed all four cards; its start is **17:14:58 UTC**, its end
**17:15:04 UTC** on October 8. The six-hour admission age is measured from the
end, expiring at **23:15:04 UTC**. Existing same-boot/new-fault, idle-card,
stop-gap and other admission checks still apply. No health probe or launch
was run during this fix; no secrets or port 8188 were accessed.

## Earlier adapter CPU validation

**Earlier adapter validation: 126/126 CPU tests passed, no skips.**
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
