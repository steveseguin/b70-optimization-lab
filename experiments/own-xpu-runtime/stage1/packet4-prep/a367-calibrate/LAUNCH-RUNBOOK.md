# One A367 zero-generation calibration: exact future launch sequence

**Not executed during resealing.** Only the owner/coordinator may run these
steps after storage admission and recording the owner's approved memory
exception against the new seal.
Run once, no queue/retry or automatic follow-on. Fixture extraction is excluded.
Use the committed reseal and retain all receipts. No power, memory, swap,
page-cache, service-configuration, model, stage or compute-selector change is
part of this sequence. No old owner-window or exception sentence survives.

## 1. Owner storage and scope admission

The owner repairs and admits `/mnt/raid-models` first. Do not inspect it while
repair is in progress. After clearance, use this one new run name; its final
output directory must not already exist. The 10 GiB write allowance below is a
planning budget for logs, Torch trace and private caches, not a measured demand.
It is additional to the unchanged 60 GiB free reserve. Root receives only small
JSON/log receipts and the per-run cache/rpc scratch
(`/home/steve/.cache/a367-scratch/<run>`, removed after owners exit); keep root
growth below 2 GB. All bulky run/trace output
lands on repaired RAID. A missing/read-only mount or I/O error refuses the run.

```bash
cd /home/steve/llm-optimizations
set -euo pipefail
FN_STAMP=$(date -u +%Y%m%dT%H%M%SZ)
FN_RECEIPTS="$PWD/data/2026-10-16-flash-next-a367-reseal/window-$FN_STAMP"
FN_OUTPUT="/mnt/raid-models/bench-results/a367-$FN_STAMP"  # short: vLLM ipc paths must stay <= 107 chars
FN_UNIT="fn-a367-calibrate-$FN_STAMP"
FN_HEALTH_UNIT="fn-a367-health-$FN_STAMP"
mkdir "$FN_RECEIPTS"
nice -n 19 ionice -c 3 taskset -c 4-15,20-31 python3 -B \
  scripts/check-storage-headroom.py "$FN_OUTPUT" --require-mount /mnt/raid-models \
  --min-free-bytes 60GiB --planned-write-bytes 10GiB \
  > "$FN_RECEIPTS/storage.json"
mkdir -p /mnt/raid-models/bench-results
test ! -e "$FN_OUTPUT"
export FN_RECEIPTS FN_OUTPUT FN_UNIT
```

Require exit 0 and `admitted=true`, correct repaired mount/source and owner
clearance of its I/O errors. Space admission alone is not a storage-health test.
The coordinator reserves all four cards, resolves any current halt, checks
process ownership and preserved FAULT latches, and records the actual previous
teardown time. Wait at least 305 seconds after that teardown. Do not remove
latches to obtain admission. The launcher rejects conflicting owners, faults,
wrong boot or an unresolved halt; no CPU prep result waives these gates.
The October 16 owner decision exempts only prior-boot latches beneath an exact
`fault-archive`, `evidence`, or `incident` directory segment below a watched
root. Top-level, current-boot, missing/unreadable-boot and ordinary run latches
still block. Preserve all latches. Read the current boot afresh after reboot;
retain `admission.json` with both checks' path/hash/boot records and its hash
binding in `environment.json`.

## 2. CPU plan and byte audit before the fresh health clock

These inspect the clean export and certified stage without runtime imports.
They never read the protected old source or rescue archive. All 75 patch/bundle,
2,305 source, 18 stage, collective, runtime metadata and model metadata checks
must pass. The audit explicitly retains the failed historical comparison and
the passing pinned reconciliation. It does not substitute for payload re-hash.

```bash
nice -n 19 ionice -c 3 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2 python3 -B \
  experiments/own-xpu-runtime/stage1/packet4-prep/a367-calibrate/a367_calibrate_load.py \
  --plan --output "$FN_OUTPUT" > "$FN_RECEIPTS/plan.json"
nice -n 19 ionice -c 3 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2 python3 -B - <<'PY_AUDIT'
import os, sys
from pathlib import Path
sys.path.insert(0, 'experiments/own-xpu-runtime/stage1/packet4-prep/a367-calibrate')
import a367_calibrate_load as c
p = c.verify_seals()
audit = {}
c.w.verify_environment(c.paths(), p, audit, calibration=True)
c.w.write(Path(os.environ['FN_RECEIPTS']) / 'environment-preflight.json', audit)
PY_AUDIT
```

The static loader review excludes only the inactive optional sleep allocator:
its historical `.9` dependency is unavailable on the selected search path,
its import failure is caught, sleep is off, and no allocator instance is used.
Do not enable sleep, substitute that DSO, add a newer compiler path, or change
selectors to make labels match. The admitted path retains the `.8` libraries.
This static review is not a claim of native startup/ABI success.

## 3. Fresh USB payload receipt, then one health pass

Hash all 144 publisher files on the actual USB launch path. Require exit 0,
all individual rows passing and `passed=true`. The helper pins both manifest
identities and verifier code. Its completion must be **no more than 3,600 seconds
before launch**. No NVMe-path receipt or historical preparation receipt qualifies.

```bash
FN_PAYLOAD="$FN_RECEIPTS/payload.json"
FN_HEALTH="$FN_RECEIPTS/health.json"
FN_OWNER="$FN_RECEIPTS/owner-window.json"
export FN_PAYLOAD FN_HEALTH FN_OWNER
nice -n 19 ionice -c 3 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2 python3 -B \
  scripts/verify-flash-next-a367-launch-payload.py --receipt "$FN_PAYLOAD" \
  > "$FN_RECEIPTS/payload.log"
```

Only inside the owner's current exclusive device window, perform the health
pass after the long CPU/hash work. This is a device action, not CPU preparation.
It visits each card once and does not retry; it has no hard device-call timeout.
Do not wrap it in a force-killing timeout. The durable unit has no restart or
kill escalation. Wait for its exit before admitting the model.

```bash
systemd-run --user --unit="$FN_HEALTH_UNIT" --wait --pipe \
  --property=Restart=no --property=KillMode=process --property=KillSignal=SIGINT \
  --property=SendSIGKILL=no --property=TimeoutStopSec=infinity \
  --property=RuntimeMaxSec=infinity --working-directory="$PWD" \
  /usr/bin/nice -n 19 /usr/bin/ionice -c 3 /usr/bin/taskset -c 4-15,20-31 \
  /usr/bin/env OMP_NUM_THREADS=2 \
  /home/steve/.venvs/vllm-xpu/bin/python3 -B \
  "$PWD/experiments/ltx25-b70/scripts/check-four-card-health.py" "$FN_HEALTH" \
  > "$FN_RECEIPTS/health.log" 2>&1
```

Require a passing four-card receipt, current boot/kernel, all four distinct
ranks passing, zero earlier boot faults and zero during-probe faults. Its end
must be **within 600 seconds at the final launch recheck**, after the repeated
byte audit. A failed/stale gate stops the attempt; no automated health/server
loop. A fault follows the owner's recovery policy, with evidence preserved.

## 4. Exact new owner approval and window

[owner-approval.pending.json](owner-approval.pending.json) contains the approved numeric
114,000,000 KiB exception and regenerated post-reseal sentence. It deliberately
remains `approved=false`. The owner has already approved the numeric exception;
the coordinator will record that approval against the new seal using the owner's
verbatim words, then set the actual window's exception to `approved=true`. A different number
requires different exact text and a new owner decision. The 12,000,000 KiB live
reserve and 120,000,000 KiB default never change. This proposal accepts unknown
loading risk; it is not a measured safe floor or fixture approval.

Generate a **pending, unauthorized** owner-window with current hashes:

```bash
nice -n 19 ionice -c 3 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2 python3 -B - <<'PY_WINDOW'
import json, os, sys
from pathlib import Path
sys.path.insert(0, 'experiments/own-xpu-runtime/stage1/packet4-prep/a367-calibrate')
import a367_calibrate_load as c
w = c.w
pending = w.read(c.HERE / 'owner-approval.pending.json')
assert pending['calibration_memory_exception']['owner_approval_text'] == c.calibration_approval_text(114000000)
owner = dict(schema='own-xpu-runtime.packet4.owner-window.v1', authorized=False,
    halt_resolved=False, host='steve-b70s',
    boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
    issued_unix=0, expires_unix=0, previous_teardown_completed_unix=0,
    preregistration_sha256=w.sha(w.PREREG), purpose='a367-calibrate-load',
    calibration_preregistration_sha256=w.sha(c.REG), calibration_seal_sha256=w.sha(c.SEAL),
    admission_revision_sha256=None, health_path=os.environ['FN_HEALTH'],
    health_sha256=w.sha(os.environ['FN_HEALTH']), payload_sha256=w.sha(os.environ['FN_PAYLOAD']),
    output=os.environ['FN_OUTPUT'], firmware='OBSERVED-FIRMWARE-REQUIRED',
    pci_ids=['0000:23:00.0','0000:27:00.0','0000:43:00.0','0000:47:00.0'],
    calibration_memory_exception=pending['calibration_memory_exception'])
path = Path(os.environ['FN_OWNER'])
with path.open('x') as stream:
    json.dump(owner, stream, indent=2)
    stream.write('\n')
PY_WINDOW
```

The owner/coordinator supplies actual firmware and previous teardown facts,
sets issued/expires times (at most one hour; allow the full 45-minute slot),
records actual halt resolution and exclusive authorization, and sets the
exception's approved flag **only when recording the owner's actual approval
against the new seal**. Leave the
reviewed hashes, USB receipt, output and PCI identities bound to this window.
No timestamp, approval, fault resolution or firmware observation is invented.
The pending file above is refused until these owner actions are complete.

## 5. One durable calibration unit

Re-run storage admission immediately before launching; retain its receipt.
The existing parent must remain available and the output must remain absent.
There is no automatic restart, hard kill, host memory cap or follow-on job.
The priority/affinity settings apply to the coordinator and its children.

```bash
nice -n 19 ionice -c 3 taskset -c 4-15,20-31 python3 -B \
  scripts/check-storage-headroom.py "$FN_OUTPUT" --require-mount /mnt/raid-models \
  --min-free-bytes 60GiB --planned-write-bytes 10GiB \
  > "$FN_RECEIPTS/storage-at-launch.json"
systemd-run --user --unit="$FN_UNIT" \
  --property=Restart=no --property=KillMode=process --property=KillSignal=SIGINT \
  --property=SendSIGKILL=no --property=TimeoutStopSec=infinity \
  --property=RuntimeMaxSec=infinity --working-directory="$PWD" \
  /usr/bin/nice -n 19 /usr/bin/ionice -c 3 /usr/bin/taskset -c 4-15,20-31 \
  /usr/bin/env OMP_NUM_THREADS=2 \
  /usr/bin/python3 -B \
  "$PWD/experiments/own-xpu-runtime/stage1/packet4-prep/a367-calibrate/a367_calibrate_load.py" \
  --execute --owner-window "$FN_OWNER" --health-receipt "$FN_HEALTH" \
  --payload-receipt "$FN_PAYLOAD" --output "$FN_OUTPUT"
```

Admission repeats ownership/health/floor/payload checks after the byte audit.
A refusal must be reviewed, not retried automatically. To revoke a running
window, place `STOP.json` in the run directory or revoke its owner-window; the
supervisor requests one SIGINT to its captured API PID. Do not kill the cgroup.
The supervisor waits past the 300-second soft teardown deadline if needed;
that overrun fails the result and requires owner recovery, never escalation.

## 6. Post-exit watch and retained evidence

The supervisor first proves **all session owners have exited**, reads the
kernel log again, writes `stop.json`, then keeps its journal watcher running
for **305 seconds**. Wait for the durable unit to finish. Read its state and
retain its journal without restarting it:

```bash
systemctl --user show "$FN_UNIT" -p ActiveState -p SubState -p Result -p ExecMainStatus
journalctl --user -u "$FN_UNIT" --no-pager > "$FN_RECEIPTS/unit.log"
```

Success requires unit exit 0 plus `calibration.json` with `passed=true`,
`ready=true`, `clean_exit=true`, `gap_complete=true`, `generation_requests=0`
and no failure; `stop.json` must say `all_owners_gone=true`, returncode 0 and
record the next-launch time. Retain admission/identity/environment, owner/health/payload
copies, samples, bootstrap receipts, server log and before/latest kernel logs.
A FAULT/STOP/teardown-incomplete marker, missing rank sample, sampling gap or
incomplete watch gives no memory proposal. Preserve all evidence and leave
cards empty. No automatic recovery, new health pass or second model launch.

Only a complete clean receipt permits `derive_floor.py`; its proposal still
needs a separate reviewed document and exact owner approval before fixtures.
Startup health and sampled memory are the only claims from this calibration;
there is no output-quality or performance result.
