# Packet49c coordinator runbook: cards0+1

The coordinator runs device commands in its admitted nice-0 systemd user unit
on cores **0–3,16–19**, with its approved `LD_LIBRARY_PATH`. The preparer runs
no GPU, health probe or service operation. Preserve OMP threads 2,
capacity 4096, split 23, draft rank 1, BF16 KV, the 30 GiB arena cap and all guards.

Only `device-cards01-a` under this packet's external build is registered.
The queue checks the full [both-chain storage budget](ARTIFACT-RETENTION.md)
before launch. No window retries, overwrites or automatic service restarts.
K windows have 90-second cooldowns and W windows 305 seconds.

## Early phase

From `/home/steve/llm-optimizations`, in the admitted coordinator unit:

```bash
P=experiments/own-xpu-runtime/stage2/packet49c-round2
OUT=/home/steve/own-xpu-runtime-results/packet49c-round2/build/device-cards01-a
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/storage_precheck.py"
bash "$P/coordinator_windows.sh" --phase early --output-root "$OUT"
```

Stop on a refused precheck. Sequence: **K0 → K1a → K1b → K2 → W0p**.
Both K1 windows run five fresh fixture processes: non-GEMV, linked dense,
split32 QSA, p49b expert kernels and the new 96-case route/HC/attention fixture.
The new fixture covers M=1 and both independently scheduled M=2 rows.
All canonical output bytes must equal the sealed CPU result. Attention
split4 workspace is separately compared with the unchanged same-device
control, because the CPU reference does not write those device partials.
K2 preserves SPEED6 choices; the explicit production overrides are checked
by K1. W0p is the oracle-free transport canary.

**Coordinator scheduling condition:** p49b may still wait for the oracle
while early 49c runs, but it holds no global launch lock. If the oracle becomes
ready, it can attempt KD automatically. Do not depend on its ETA or a foreign
engine check as a mutual-exclusion guarantee. The coordinator must ensure
exclusive windows and complete this early phase while 49b is still waiting.
If this timing cannot be assured, defer this early phase until49b completes,
or explicitly stop the waiting49b queue first as a separately chosen ordering.
The preparer has done neither. Never run both chains' GPU windows together.

CPU-only argv inspection:

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/queue_runner.py" \
  --phase early --output-root "$OUT" --plan
```

## Switch after 49c early passes, while 49b still waits

Only the coordinator performs these steps. First verify 49c has successful,
qualifying K0/K1a/K1b/K2/W0p receipts and `queue-early-complete.json`, and its
early unit has exited. Check 49b is still waiting: its completed state is exactly
`K0,K1a,K1b,K2,W0p`, no `KD` directory exists, and no KD child has launched.
A stale `running.json` from W0p is historical, not proof of a live process.

```bash
OLD=/home/steve/own-xpu-runtime-results/packet49b-gemv/build/device-cards01-a
printf '%s\n' 'Coordinator switch to qualified packet49c early chain' > "$OLD/STOP"
```

Do **not** use `systemctl stop` or signal the queue. STOP is checked within
about 5 seconds plus the oracle status-check duration; the unchanged queue
exits nonzero intentionally and releases its flock. Observe that exit:

```bash
systemctl --user show p49b-model-cards01-a.service \
  -p ActiveState -p SubState -p MainPID -p ExecMainStatus
```

Require `MainPID=0` and `ActiveState=failed` or `inactive`, check its journal
for the STOP-wait/before-launch reason, verify no KD child/output started,
and confirm the old chain lock is free:

```bash
flock --nonblock "$OLD/queue.lock" true
test ! -e "$OLD/KD"
```

If KD already started, **do not launch 49c**. The waiting-queue STOP contract is
not an active-window cancellation mechanism. Let the coordinator follow the
existing window's cooperative stop/teardown and health procedure. Never delete
KD output, clear STOP, retry a window or hard-kill an owner to force a switch.

Leave 49b's STOP, queue-state, lock file and evidence in place. The open flock
is released on queue exit; no global claim exists. The new queue admits only
its own registered path and never refuses simply because49b's chain exists.
[CPU switch tests](test_p49c_switch.py) exercise the unchanged 49b queue code
for both waiting and oracle-ready races, proving no child launch or KD
creation and successful lock reacquisition. STOP does not release 49b's disk
allowance.

Then, in a **new admitted coordinator user unit** (for example
`p49c-model-cards01-a`, same nice 0, affinity and approved library environment):

```bash
P=experiments/own-xpu-runtime/stage2/packet49c-round2
OUT=/home/steve/own-xpu-runtime-results/packet49c-round2/build/device-cards01-a
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/storage_precheck.py"
bash "$P/coordinator_windows.sh" --phase model --output-root "$OUT" --wait-oracle
```

This waits without device owners for the unchanged
`own-iq3-p49-oracle-20261017b.service`. It runs
**KD → W2m → WS → WSs → WS128x → WS128** only after completed hash validation.
Do not require `shared_oracle.py --require-complete` to succeed before queueing:
`--wait-oracle` intentionally permits an incomplete running oracle. The status
command is available for read-only inspection.

Every model receipt binds the shared completion, suite manifest, determinism
and KD-capture hashes. WS128 uses 12 prompts, 128 tokens and context 4096, requires
WS128x exactness, and retains original prompt/output hashes and timestamp
accounting. Primary: median of class medians for 99/(t100-t1); all-prompt median
is separate. The 39.422 record stays unchanged until qualified matched evidence
exists. This does not pass the separate 512-token publication gate.
