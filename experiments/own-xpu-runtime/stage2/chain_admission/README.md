# Lane admission for the next sealed chain

CPU-prepared support for a **new, unsealed** chain wrapper and a new lane-B
screen wrapper. No existing packet, screen seal, GPU job, service or output
directory is changed by these files. Device qualification is pending.

The chain always exposes native cards **0 and 1**, physically
`0000:23:00.0` and `0000:27:00.0`. Lane B exposes its own native cards 0 and 1,
physically `0000:43:00.0` and `0000:47:00.0`. The fixed five-key mask follows
the lab's [screen v3 device code](../screen/v3/devices.py): filter BDF paths
before DRM opens, then apply the Level Zero/oneAPI selectors. Passive sysfs
checks require exactly the registered pair. Native owners use fresh private
driver homes, and fdinfo checks bind every PID to its start ticks.

| Window | Admission | Timing interpretation |
| --- | --- | --- |
| K0, K1a, K1b, K2, KD | Cards 0+1; B may screen | K2 operator timings remain diagnostic dispatch evidence |
| W0p, WS, WS128x, WS64x, W2m-exact | Cards 0+1; B may screen | Exactness only; concurrent timings cannot support a speed claim |
| WS128, WSs, W2m, W2m-speed, WS64 | Whole host | Hold B before launch through teardown and postflight |
| Remaining registered W2 variants | Whole host | Conservative exclusion for timing/diagnostic paths |
| Unknown name | Refuse | Register the policy before sealing |

WSs and W2m carry timing in the reference chain, so both always hold the host.
There is no CLI option to downgrade a timing window. If a future candidate
uses an exactness window's timings for a claim, upgrade its policy before
sealing. The existing quality, BF16 KV, oracle, memory, storage, fault,
watchdog, cooldown and submission gates remain mandatory.

Admission checks **client presence**, including idle clients, rather than
engine-counter growth. Unknown Xe PCI identities refuse. Known B clients
are retained in exactness evidence. As in v3, inaccessible foreign processes
are counted and require coordinator ownership review; fdinfo cannot rule out
hidden clients belonging to another UID. All GPU-capable drivers must
participate in this protocol before overlapping these windows. An old
uncooperative launcher can defeat advisory locks; the live scan will refuse
visible conflicts, but is not a substitute for coordinator ownership.

## Coordination file protocol

All adopted wrappers share this directory; never give each packet its own:

```text
/home/steve/own-xpu-runtime-results/coordination/chain-lanes-v1/
  protocol.lock
  lane-A.lock
  lane-B.lock
  active-lane-A.json
  active-lane-B.json
  hold-lane-B
```

The last three files contain JSON with protocol version, unique token,
window, scope, boot ID, PID and process start ticks. Their presence is the
reservation; a PID alone is never enough to discard one. Lock files are
persistent inodes and must never be unlinked/replaced.

1. A reserves `lane-A.lock` and writes its active marker under
   `protocol.lock`. For a timing window it also writes `hold-lane-B` **before**
   waiting on `lane-B.lock`.
2. B checks the hold and reserves its lock under that same `protocol.lock`,
   before invoking **one** screen. If the hold exists, it waits between
   screens. It does not stop the current screen, pre-acquire the next lease,
   or reserve a whole batch.
3. B keeps its lease through native teardown, the existing postflight and a
   passive check that its pair is empty. `run_lane_b_screen()` verifies the
   fresh v3 window/summary and worker exit before removing B's marker.
4. A's timing window waits for B's lock and confirmed marker removal, then
   checks the whole host. It keeps B's lock and the hold until its own owners
   have exited and its existing postflight has passed.
5. Successful completion removes only matching-token markers and releases
   lane locks under `protocol.lock`. B can then take its next lease.

The default admission wait is bounded to 1,800 seconds. STOP, fresh journal
faults or cancellation end an admission attempt; nothing is killed or
restarted. Failed/uncertain owners, a timeout, an interrupted attempt and
process death retain markers. A new process never deletes a marker because
its PID vanished or its boot is old. The coordinator must retain the failed
evidence, establish actual owner exit/device health, and archive the exact
stale markers before a newly authorized attempt. No recovery, reboot, service
or reset operation is implemented here.

## Keep the shared drain gate

The helpers share v3's existing `teardown.lock` / `teardown-state.json` under
`screen/v3`, including the 60-second gap. A holds that permit for a whole
window because fixture and KD binaries exit on their own; Python cannot
intercept their teardown. B can compute concurrently, but waits for the
permit before draining. Native code and stop handling are unchanged.

**The companion B-wrapper patch is required.** Original v3 prelaunch
admission treats any incomplete drain marker as a refusal. The new wrapper
allows B to start computing only when that marker belongs to a live,
PID/start-tick-bound A exactness reservation, and A's lease, B's lease and the
shared drain lock are held. The ownership snapshot uses `protocol.lock` so
A completing cannot race marker reads. Actual B teardown still uses the
original lock, completion check and 60-second gap. A crash, missing lock,
different token, reused PID or timing reservation cannot gain this exception.

This conservative permit can delay B's completion. That wait still counts
against B's existing 3,600-second watchdog and native deadlines; the patch
does not extend them. The coordinator must check the planned overlapping
window duration. A narrower permit needs a native fixture exit barrier and
separate qualification. Very short fixture owners can also finish between
fdinfo samples; missing proof fails closed. CPU tests do not certify native
filter behavior or complete-chain usability.

## Adopt before the first seal

Use a fresh wrapper directory for packet 62, 63 or a later bundle. If its
screen candidate is already sealed, bind that candidate as an immutable
parent of a separate new chain wrapper. **Never apply this to packet61x,
an existing sealed packet, an active chain or its build view.** The patches
are templates; candidate identity, paths and registered outputs still need
their normal first-seal preparation.

Copy these four files directly into the new chain wrapper and into a new
standalone B screen wrapper derived from v3:

```text
chain_devices.py
lane_admission.py
drain_gate.py
window_adapter.py
```

Apply [integration.patch](integration.patch) to the new chain's `window.py`,
`pipeline.py` and `queue_runner.py`. Apply
[screen-integration.patch](screen-integration.patch) to the new B wrapper's
`conditions.py` and `screen.py`. Run `git apply --check` first. No patch is
applied to the reference during preparation. The B successor stays at the
same directory depth as v3 so existing relative imports remain valid, and
must retain all v3 dependencies and CPU checks. Its device entry is B-only,
standalone; the original `--plan` path remains side-effect-free. A crossover
driver is outside this recipe.

The recipe implements these hooks:

- Insert the fixed mask **after** the existing closed-environment gate; give
  fixture/KD owners and pipeline ranks fresh native driver homes.
- Route every fixture, KD and model owner through `Watch.mark_launched`,
  poll isolation from `Watch.check`, and prove mapped ranks after both READY
  replies and before any model request.
- Bind the final admission sidecar to the complete original window receipt,
  including its source/build identity and launched PIDs. Revalidate that
  binding in both prerequisite checks and the queue's success check. A failed
  final isolation/drain check changes the window to `passed=false`.
- Wrap each B screen with `run_lane_b_screen()`, preserve old v3 fault latches,
  and use the live-A prelaunch exception without relaxing actual teardown.

Both new seals must include all four helper files, patched entry points and
their tests. Packet61-style `chain_seal.py` and v3 `cpu_seal.py` already include
top-level Python sources; verify the resulting source map. Do not import the
mutable shared helper directory at runtime or reseal an existing packet.
Update candidate submission checks to call `verify_receipt` for every
chain window they consume; an unbound old receipt is not new-policy evidence.
Record the wrapper, mask, fresh driver homes and concurrency policy in the
new benchmark identity. No historical result is rewritten.

The retained patches use [reference.json](reference.json), pinned to
`597c4946ecc0e588c715986b038fda1ba3f0d0ce`. To adapt a changed **unsealed**
wrapper, `recipe.py --reference DIRECTORY` prints a checked chain diff;
add `--screen` for the B-wrapper diff. It never writes into that directory.
Unknown integration points refuse. Review the generated diff before applying.

## CPU validation

From the repository root:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/chain_admission/test_lane_admission.py -v
```

The tests use temporary proc/sysfs trees, local file locks, a short CPU-only
child that exits itself, and a bounded thread for the completion race. They
apply both patches only in scratch directories, verify the pinned reference
hashes and compile the patched sources in memory. No GPU library, device
probe, service or model process runs. See [CPU evidence](evidence/cpu-validation.json)
and the [task note](../../../../notes/2026-10-17-own-runtime-lane-aware-chain.md).
The [CPU closeout](CPU-PREPARATION-CLOSEOUT.md) records the remaining device
questions and the conditions for the next step.
