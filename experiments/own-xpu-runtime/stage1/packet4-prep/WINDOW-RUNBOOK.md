# Flash-only extraction window — CPU prepared, admission blocked

**NOT READY to launch on the current host.** The [worker driver](driver/README.md)
is implemented and CPU-tested. The [read-only environment audit](driver/environment-audit.json)
found three concrete admission blockers: the default A367 kernel stage is absent,
`MemAvailable` is below A367’s 120,000,000 KiB floor, and the current host has a
`FAULT.json` halt. Nothing in this packet resolves those conditions or authorizes
GPU work. No GPU, model server, container or systemd unit was used in preparation.

This runbook supersedes the earlier “worker driver missing” item for **one
Flash-Next diagnostic screen only**. The older adapter manifest’s internal-state,
reference-normalization, 27B and full-census gaps remain open. They are not gates
for the deliberately selected layer-0 outer boundary, and are not claimed fixed.

## Exact pending admission

1. Locate and admit all **18 A367 loadable kernel-stage files**, including the
   rebuilt `_xpu_C.abi3.so` with SHA256
   `6b95dc90c25bb0f9c2503805e4184648ddcac089ec54ec65fe7eeb13ab2b097b`.
   The default `/mnt/usb-models/qwen38-build/runtime-gdn-roundstate-bbae3c5-b70`
   is absent. `--stage` may name an existing byte-identical copy. Do not download,
   mount, rebuild, edit the venv or substitute the reopen extension in this task.
2. Meet the original **120,000,000 KiB MemAvailable** admission floor. The audit
   records the observed lower value. Do not lower the floor or change swap,
   page cache, memory offlining or power settings. A revised memory admission
   would need its own justified packet; this code does not accept one silently.
3. The owner resolves the halt. All known `FAULT.json` files must be absent;
   this strict driver also refuses any earlier fault-class line on the boot.
   It never clears evidence, archives a halt, resets a driver or reboots.
4. Supply the owner-window flag, a fresh passing four-card health receipt,
   fresh full-payload verification receipt, and at least **305 seconds since
   all previous native owners completed teardown**. The owner flag binds these
   receipts, the boot, output directory and preregistration hash. No ltx*,
   ComfyUI or vLLM process may be running. This driver never contacts port 8188
   or operates any LTX unit.

The [A367 guide](../../../../repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913/README.md)
records a **host venv**, not a certified image. The driver uses
`/home/steve/.venvs/vllm-xpu/bin/python`, puts the byte-verified A367 source and
rebuilt extension first on `PYTHONPATH`, and checks all 75 patch-seal members,
the frozen four-script packet, 2,305 source Python files, the tuned map and
placement, model metadata, runtime versions and collective-library hashes.
The venv’s ordinary editable vLLM mapping points elsewhere; every spawned
process checks the actual import location. No historical launcher is executed.

## Registered run

[preregistration.json](driver/preregistration.json) fixes the command, limits,
selection, evidence hashes and every delta; [driver-seal.json](driver/driver-seal.json)
pins its bytes and the implementation. [Driver documentation](driver/README.md)
contains the source-line proof and receipt formats.

- A367 model/revision, TP4/EP4, MTP1, BF16 activations/KV/inter-row state,
  4,352 capacity, 64-token prefill chunks, placement, UVA offload, tuned kernels
  and oneCCL selectors stay pinned.
- Eager execution replaces graph capture; the guard refuses graph entry points
  before model construction. `--worker-cls packet4_worker.ExtractionWorker`
  registers exactly once in each worker. The unchanged original forward runs
  once and returns its original object.
- Only layer 0’s outer decoder boundary is selected. Record the first naturally
  observed M1/M2/M6 dispatch; omit other shapes and draft/warmup calls. Positions
  come from the same CPU scheduling arrays as the certified runner. N/K describe
  this boundary’s feature width, not a projection-shape census. No internal
  GDN row state, KV slice, acceptance/rollback or fused intermediate is invented.
- Each rank has **2 GiB including a 4 MiB receipt reserve**, totaling **8 GiB**.
  The recorder cap excludes that reserve; the supervisor checks final total.
  No full weights or cache pools are copied. A cap failure makes the run VOID.
- Send `incident-retrospective` from the frozen realistic suite once, using the
  same chat template (`enable_thinking=false`), greedy seed 20260609/top_p 1,
  no system message, no prefix reuse, and **max_tokens=64**. Token IDs come
  directly from the response. Exact equality to **the first 64 IDs** of the
  frozen 512-token answer is mandatory, with cache count zero and length stop.
  A missing, shorter, longer or different array marks every rank **VOID**.
  This is explicitly not full-oracle parity or a realistic final gate.
- The host watcher starts before launch, polls the full kernel journal at
  0.5-second intervals, preserves fresh fault evidence, and requests one stop.
  Journal errors fail closed. No fault is cleared; no retry or recovery launch.
- SIGINT is sent once to the captured server PID. Spawn-time guards replace
  vLLM’s two force-termination cleanup paths with cooperative joins; process
  managers signal their own children once, workers exit via the original death
  pipe and original synchronized cleanup. A 300-second overrun is recorded and
  remains waiting for manual recovery; there is no SIGKILL fallback. Startup
  failures and incomplete rank teardown cannot produce a successful receipt.
- Final evidence requires all rank cleanup receipts, disappearance of all
  session owners, and a new kernel read after exit. The completed stop receipt
  sets the next workload’s earliest start to **305 seconds later**. Scratch is
  removed only after ownership is proved gone. Otherwise it is retained with
  an explicit recovery receipt. Leave the cards empty.

`nice=19`, `OMP_NUM_THREADS=2` (A367 used 1), private cache/IPC/evidence paths,
no Torch trace, and nonstream response delivery are declared diagnostic
changes. No timing from the instrumented run is a speed measurement.

## Commands, only after the pending admission is resolved

Before reserving GPU time, print the exact CPU-only plan and audit the existing
runtime files. `$WINDOW` names a **nonexistent** output directory with an existing
parent. `--stage` is required if the byte-identical stage has another location.

```bash
bash experiments/own-xpu-runtime/stage1/packet4-prep/driver/run_extraction_window.sh --plan --output "$WINDOW"
bash experiments/own-xpu-runtime/stage1/packet4-prep/driver/run_extraction_window.sh --audit --output "$WINDOW" --stage "$A367_STAGE"
```

The **first command inside the owner’s authorized, idle window**, after the
previous teardown gap, creates a fresh health receipt outside `$WINDOW`:

```bash
nice -n 19 env OMP_NUM_THREADS=2 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/ltx25-b70/scripts/check-four-card-health.py "$HEALTH_RECEIPT"
```

That command uses GPUs and was **not run** in preparation. It cannot resolve a
halt by itself. The coordinator then supplies the reviewed owner flag and
payload receipt described in [driver/README.md](driver/README.md), and runs:

```bash
bash experiments/own-xpu-runtime/stage1/packet4-prep/driver/run_extraction_window.sh --execute --owner-window "$OWNER_WINDOW" --health-receipt "$HEALTH_RECEIPT" --payload-receipt "$PAYLOAD_RECEIPT" --stage "$A367_STAGE" --output "$WINDOW"
```

No automatic unit is created. The coordinator must keep this authorized run
in a durable owner-controlled terminal; do not place it in an agent shell
that can kill the process tree. If a future approved service wrapper is used,
it must have no automatic restart or hard-kill timeout. Preparation performs
no systemd operation and ships no unit.

After complete clean teardown, the coordinator can collect the usual fresh
health-after receipt separately. It is not an automatic recovery attempt.
A fault follows the owner’s recovery policy and halts this window.

## Final time budget and gate

Reserve **45 minutes**, Flash only: 6 minutes for initial gap/admission,
2 for bounded health, 20 for one load and one request, 5 for graceful cleanup,
5 for final health/evidence and 7 contingency. Full payload verification and
source/binary admission are completed before the slot; health is rechecked
immediately before the single launch. Cleanup may exceed its five-minute soft
budget to avoid unsafe forced exit; the overrun makes the run incomplete.

A successful receipt means only a clean **64-token diagnostic extraction** with
all four rank receipts. Raw operator comparisons remain **UNTESTED** until
independent reference normalization exists. Full U1–U7 internal-state coverage,
all twelve full answers, same/fresh-process repeats, eager neutrality beyond
this prefix, natural M6 or separate replay, 27B extraction and the packet-3
native smoke each require later work. They are not additional launches in this
45-minute window. No benchmark or promotion is made here.
