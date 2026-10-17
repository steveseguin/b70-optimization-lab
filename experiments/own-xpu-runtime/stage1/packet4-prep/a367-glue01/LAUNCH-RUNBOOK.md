# Coordinator sequence: control, candidate, comparison

These are future coordinator commands. None ran during the CPU build. Use the
committed sealed packet and existing exclusive ownership of all four cards.
Record current storage clearance, firmware and actual previous teardown time.
Do not execute historical wrappers. Do not change power, memory, swap or caches.

The coordinator records approval under the owner's standing instruction in this
brief. `owner-approval.pending.json` supplies the exact sentence binding both arms,
the preregistration and seal. `fill` records it in each fresh window; it does not
invent firmware, teardown or ownership observations. No new approval question is
needed for this authorized preparation. The build leaves all windows uncreated.

Use a normal-priority unrestricted coordinator shell. The script-file commands
keep conflict terms out of shell argv. CPU steps use nice 19 and coordinator cores;
`launch.sh` creates the durable normal-priority server unit. A restricted parent
is refused. No command below is a loop or retry.

Before control, wait until 305 s after the actual previous complete teardown. Set
`FN_PREVIOUS_TEARDOWN` to that observed Unix time and `FN_FIRMWARE` to the observed
firmware identity (not a placeholder). Clear no latches. Storage admission must
pass on the approved RAID mount. Source/metadata audit precedes full payload
hashing; health runs last so its 600 s freshness clock survives final admission.

```bash
cd /home/steve/llm-optimizations
export FN_ARM=control
export FN_PREVIOUS_TEARDOWN='<observed-unix-time>'
export FN_FIRMWARE='<observed-firmware>'
source experiments/own-xpu-runtime/stage1/packet4-prep/a367-glue01/prepare.sh
bash "$FN_PACKET/audit.sh"
bash "$FN_PACKET/payload.sh"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$FN_PACKET/ops.py" health --exclusive --halt-resolved
nice -n 19 taskset -c 4-15,20-31 python3 -B "$FN_PACKET/ops.py" pending
nice -n 19 taskset -c 4-15,20-31 python3 -B "$FN_PACKET/ops.py" fill --exclusive --halt-resolved
bash "$FN_PACKET/launch.sh"
```

`prepare` creates the fixed two-arm campaign once. `health` first refuses any
extra current-boot fault and any conflicting owner; it performs one bounded
four-card probe, with no retry. It accepts the earlier pair only through the
sealed resolution. Fresh payload completion must be within 3600 s; fresh health
end within 600 s at final launch admission. `fill` authorizes at most 3600 s and
records the 114840824 KiB floor, 12000000 KiB reserve and exact approval sentence.
Neither a successful CPU build nor the historical probe replaces fresh health.

Wait for the control unit to exit, including its full 305 s watch. Run:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B "$FN_PACKET/ops.py" check
```

Require unit exit 0, `glue01-run.json` passed/nonmock/ready/clean_exit/
all_owners_gone/gap_complete, `comparison.exact=true`, complete battery and no
new fault. Control failure blocks candidate. Preserve every result and latch;
never delete a claim to repeat the arm. No background follow-on launch is queued.

Candidate uses the same fixed campaign. Its previous stop is read and hash-bound
from control. A new health check must **start after control's 305 s gap**, and a
new payload receipt, output directory and owner window are required:

```bash
export FN_ARM=candidate
source experiments/own-xpu-runtime/stage1/packet4-prep/a367-glue01/prepare.sh
bash "$FN_PACKET/audit.sh"
bash "$FN_PACKET/payload.sh"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$FN_PACKET/ops.py" health --exclusive --halt-resolved
nice -n 19 taskset -c 4-15,20-31 python3 -B "$FN_PACKET/ops.py" pending
nice -n 19 taskset -c 4-15,20-31 python3 -B "$FN_PACKET/ops.py" fill --exclusive --halt-resolved
bash "$FN_PACKET/launch.sh"
```

The byte gate runs inside candidate warmup on the already-initialized four-rank
communicator. It is not a separate device job. Any byte/graph/source mismatch
prevents the timed suite and candidate qualification. No profiler runs. After
the candidate unit has exited and completed its own 305 s watch:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B "$FN_PACKET/ops.py" check
nice -n 19 taskset -c 4-15,20-31 python3 -B "$FN_PACKET/ops.py" compare
```

Comparison independently rechecks exact pins, both lifecycles, identity/campaign
bindings, operator receipts and ordering. Report class-balanced 99-interval and
all-prompt medians, TTFT, acceptance and full-response wall times. Device step
counts/times stay unavailable where no measured evidence exists. Speed is not a
gate. Flat within about 3% closes this small lever; a faster pair still needs
further fresh-server determinism and promotion evidence before any headline.

A new fault fails the run and, on this resolved boot, is a second incident:
preserve the evidence and tell the owner a reboot is needed. Never retry. One
SIGINT goes to the captured API PID; teardown waits for all session owners with
no kill escalation, then watches 305 s even on failure. Overrun or stuck clients
require coordinator recovery. Leave the cards empty; restore no service.
