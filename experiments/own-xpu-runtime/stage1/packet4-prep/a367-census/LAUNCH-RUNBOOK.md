# One future A367 diagnostic census arm

Adapted from the sealed replay runbook. **Nothing here was executed by the CPU
build.** This requires a new owner approval and current coordinator admission.
Each arm runs once; there is no retry, queue or automatic fallback. Start with
`graph-reference`; review it before separately admitting a conditional trace
arm. All measurements here are diagnostic, not benchmark results.

Every launch/check command is a **script file**. Do not paste process-search
patterns, runtime paths or inline Python into a host shell command: the conflict
scan can match the shell itself. Keep these commands as shown. The actual server
owns its normal process names; coordinator command lines must not mimic them.

## 1. Scope and storage

Owner/coordinator: confirm storage clearance and the correct writable RAID mount
(UUID `1498256698254816`), exclusive four-card ownership, current boot/halt
resolution and no disqualifying latches. Do not delete FAULT evidence. Only
prior-boot latches inside exact `evidence`, `incident` or `fault-archive` path
segments are exempt; current/unknown-boot/top-level latches still block.
Record actual previous teardown and wait at least 305 seconds. No preflight
from this CPU build substitutes for those facts.

From a normal-priority shell with unrestricted CPU affinity:

```bash
cd /home/steve/llm-optimizations
export FN_ARM=graph-reference
source experiments/own-xpu-runtime/stage1/packet4-prep/a367-census/prepare.sh
bash "$FN_PACKET/audit.sh"
```

Future independently admitted alternatives are `graph-census` and
`eager-census`; set the selected value before sourcing prepare. Never reuse an
output directory or mutate the arm in an admitted window. Output is
`/mnt/raid-models/bench-results/a367c-$FN_STAMP`. Require storage admission true,
60 GiB reserve plus 10 GiB planned writes. Scratch stays on local ext4 at
`/home/steve/.cache/a367-scratch/<run>`, at least 4 GiB free. No cache drops,
mount repairs, memory caps, power changes or service configuration changes.

The audit checks all replay dependencies and clean source/stage pins. Trace
arms additionally require pinned executable/DSO identities. This is not a
native health or ABI check. Do not change libraries or arithmetic to pass it.

## 2. Fresh payload and health receipts

Only after exclusive owner admission, these future scripts hash the actual
USB publisher payload and run one device health pass. They are **not CPU build
tests** and were not run here.

```bash
bash "$FN_PACKET/payload.sh"
python3 -B "$FN_PACKET/ops.py" health
nice -n 19 taskset -c 4-15,20-31 python3 -B "$FN_PACKET/ops.py" pending
```

Require all 144 payload files passing, actual USB launch path, completion within
3,600 seconds at final admission; health must show all four cards, current
boot/kernel, no previous or new faults, completion within 600 seconds at final
admission. No automated health or server retry. The durable health unit uses
no restart or kill escalation. Retain its logs. Failed/stale admission stops
this attempt and must be reviewed.

## 3. Record the exact owner sentence and window

[owner-approval.pending.json](owner-approval.pending.json) is **approved=false**.
Its exact sentence says “A367 diagnostic census”, binds the new preregistration
and seal SHA256, accepts tracer/generation memory risk, and states tracing is
diagnostic and makes no speed claim. Earlier replay approval does not admit
this packet. Proposed floor: 114,840,824 KiB; reserve remains 12,000,000 KiB.

`ops.py pending` creates an unauthorized owner-window. The owner/coordinator
records actual firmware, previous teardown, current halt resolution and
exclusive authorization; sets issue/expiry within one hour; and records the
exact new approval before setting the exception approved flag. Do not invent
facts or copy stale receipts. The selected `census_arm`, hashes and output must
stay bound. Pending flags and zero timestamps deliberately refuse admission.

## 4. Launch once and monitor through script files

```bash
bash "$FN_PACKET/launch.sh"
python3 -B "$FN_PACKET/ops.py" check
```

The unit must be nice 0 with all online CPUs; the server inherits that profile,
OMP=1. Only the client is pinned to 4-15,20-31 at nice 0. Do not inherit the CPU
build's nice19/taskset restrictions into this launch. It repeats admission after
the byte audit. Unit restart and kill escalation are disabled. A refusal is
reviewed, never retried automatically. No follow-on server is restored.

Readiness is followed by 20 seconds of fresh complete plateau samples and a
30-second sleep. Trace arms start paused, resume only for the two requests,
check the session acknowledgement, and pause in finally. Trace/ITT failures,
missing samples, faults, stale window, reserve breach or output soft-stop request
one SIGINT to the captured API PID. Tracer flags retain exec/PID semantics;
metric/KMD modes that add a supervising process are excluded. Never use a
cgroup kill or force-remove. To revoke, record STOP.json in the run directory
or revoke the owner-window. Wait for all session owners to exit and the full
305-second watch. A 300-second soft teardown overrun fails and continues
waiting; recovery is the owner's decision.

## 5. Retain outputs and analyze after exit

```bash
python3 -B "$FN_PACKET/ops.py" check
nice -n 19 taskset -c 4-15,20-31 python3 -B "$FN_PACKET/ops.py" analyze
```

Require unit exit 0 and `census-run.json` with passed/ready/clean_exit/gap_complete
true for lifecycle success. `comparison.json` records exact token prefixes or
the first differing ID; mismatch is a finding, not a gate failure. The subset
must retain realistic_final_gate=false. `write-budget.json` records the actual
after-drain size; over 10 GiB fails. The 8 GiB poll is a soft stop, not a quota.

The manifest builder requires completed exit/watch and binds raw traces plus
rank receipts. Analysis writes `census.json` and `census.md`; graph-reference
has no device census. Trace success additionally requires actual per-rank
kernel timestamps and defensible verify/draft correlation. Unknown or incomplete
coverage is reported rather than filled in. Generic kernel family names may
need reviewed source mappings. Eager results remain labelled eager. No measured
speed gain, benchmark promotion or graph-device visibility is claimed by a CPU
pass. See [tracing evidence](TRACING-FEASIBILITY.md).

Retain owner/health/payload/admission/environment/identity receipts, memory rows
with attribution timestamps, server/client logs and outputs, trace controls,
all raw process traces/markers, write-budget, stop/gap/journal evidence,
manifest, analysis and comparison. Leave the cards empty.
