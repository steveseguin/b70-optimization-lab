# Packet58k: one-load one-card screen

A CPU-prepared replacement for the long **screening bracket** in packet58j.
Run production / down-tile16 + route-fast + rec-both-plus / production on card
0, lane A. Each arm loads the model once and runs the complete fixed twelve
prompts once at 128 output tokens. Every output token is compared to the
unchanged packet49 oracle, including tokens outside the timing interval.
BF16 KV, prompt resets, zero reused prompt/KV/response tokens, target-only
execution and the existing weight-cache policy remain unchanged.

**One model launch per arm does not remove K1.** Each arm first runs the two
small, fresh-process K1 fixtures (no model load), with that arm's DOWN layout.
The unchanged 12.5 GB/s threshold chooses zero-copy only if both qualify;
otherwise the model uses streamed misses. Thus there are three model loads
in the bracket, plus six bounded fixture processes. No K1 result or model
process crosses arms. There are no KD, W2m, retained-layer, or repeat-suite
model loads in this screen.

The two binaries are byte-identical copies from sealed packet58j. No native
code changed or compiled. The retained build is **39,526,592 bytes (39.53 MB)**,
under the user's 150 MB limit. `parent-build-receipt.json`, `copy-manifest.json`
and the new seal bind the parent sources, completed CPU gates, copied binaries
and current wrapper. The parent's 80 full-size startup checks and byte gates
are reused as unchanged-native evidence, not claimed as new runs.

## Planned host gap

| Item | Plan, not a new measurement |
| --- | --- |
| Each arm, including its two internal 90-second gaps | 10–12 minutes |
| Three arms plus two queue-enforced 90-second gaps | **33–39 minutes** |
| Full-model host budget, excluding reserve | **109,718,973,456 bytes (109.72 GB)** |
| Live host reserve | **8,589,934,592 bytes (8 GiB)** |
| Required `MemAvailable` before model load | **118,308,908,048 bytes (118.31 GB)** |
| Packed pinned expert weights | 48,627,712,000 bytes (48.63 GB) |
| K1 admission | 12 GiB available |
| Device bound / expert cache | 26,409,219,600 / 18,000,000,000 bytes |

These are the unchanged 58g/58j timing admission bounds, not a measured RSS
peak. All device backing, loader space, reclaimable-file residency allowance
and the reserve remain covered. The smaller 85.57 GB exactness-only admission
is not substituted for timing. A lane-B screen requiring 97 GiB cannot overlap.
Reserve a **39-minute whole-host gap**; admission waits and unusually slow
storage are outside this estimate. The old 58g receipts took about 9.8/9.9
seconds for K1a/K1b and 192.6 seconds for WS128; those historical observations
are motivation for the estimate, not a measurement of this packet. Each K1
watchdog remains 600 seconds; the model watchdog is 1800 seconds and requests
cooperative stop, never a hard kill. The estimate is not a kill deadline.

Each window obtains the same lane-A lease, holds lane B, verifies all cards
for foreign clients, checks the card-0 BDF mask before enumeration, reads the
memory-block fence, and rechecks memory after waiting for the shared drain
permit. It releases its lease after clean drain; the coordinator must keep
lane B out of the planned gap, including the 90-second gaps between windows.
An unexpected B owner causes a wait/refusal, never concurrent model pinning.
The fence, power, swap and page-cache settings are never changed.

The copied 58g refusal path drains **its own** pending shared record after a
proven pre-compute refusal with clean exit and postflight. Live/unknown owners,
missing idle proof, nonzero allocations and faults retain their markers.
No retries, resets or service restoration are implemented.

## Coordinator handoff

The only proposed queue file is
[`proposed-p58k-screen-A.txt`](../../ops/lane-queue/proposed-p58k-screen-A.txt).
It contains all three arms in order. It was planned on a temporary directory;
no live queue, service, device, fault-review receipt or coordination file was
created. The queue supplies a fresh reviewed fault receipt to each job and
uses normal lane-A timing cores. K1 children use nice 19 and helper cores.
All imports and `--plan` paths are CPU-only.

To repeat the plan without installing any queue, from the repository root:

```bash
P=experiments/own-xpu-runtime/stage2/packet58k-onecard-screen
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/queue_runner.py" \
  --arm production-before --output "$PWD/$P/evidence/card0-screen-a/production-before" \
  --plan < /dev/null
```

The proposed job file fixes the fresh output root to `evidence/card0-screen-a/`.
Do not rename old output to rerun a losing arm. Later arms validate all earlier
receipts before launching, including the boot, selections, binaries, K1
selection, complete allocation observations, native file hashes and every
token. Any failed arm stops; there is no automatic retry or alternative view.
A complete, drained loss returns success to the queue but records
`qualifies_for_full_chain: false`; it never queues a record job.

The last arm writes `screen-decision.json`. It recomputes class-balanced speed
from the six class medians, using the 99 timestamp intervals from tokens 1 to
100 after TTFT. The existing metrics also retain TTFT, wall rates, full
completion rates, prompt/output hashes and per-request results. The port must
beat both controls and the saved 24.338653323339745 tok/s record; controls must
be within 3%, and all arms must use the same K1-selected miss path.

**This single candidate launch cannot establish a speed verdict or submission.**
It only decides whether to spend time on a fresh full chain. The 128-token
cap keeps the strict realistic final gate false. No layer-byte checks or
fresh-process candidate repeat are claimed by this screen. A two-card gain is
not evidence for one card.

If the screen qualifies, retain packet58j's unchanged seven-window queue for
the later, separately scheduled submission work. Its `queue_runner.py --view
port` runs K1a / K1b / KD / W2m / WS / WS128x / WS128; use a fresh record output
and the coordinator's fresh admission. Do not feed 58k receipts to 58j's
`campaign.py record`: that command specifically expects a full 58j bracket.
The coordinator must review this screen and the fresh full-chain evidence,
including any independent repeat and promotion attestation required by the
lane, before submission. No external submission or record auto-launch is in
58k. The frozen 58j files were not edited.

## CPU checks and restoration

[CPU tests](evidence/python-cpu-gates.json): 76 pass, including mutation of all
128 token positions, both K1 miss choices, whole-host admission, masked card
ownership, memory stops, and complete window refusal/drain tests. The early
`inherited-tests.log` records adaptation of the old seven-window test fixtures;
the final source-bound receipt is `python-cpu-gates.json`.
[Temporary queue plans](evidence/queue-plans.json): all three pass, creating no
arm output. [Seal](build-receipt.json) verifies the copied native identity.

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/run_cpu_gates.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/seal.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/seal.py" --verify < /dev/null
```

Build binaries are ignored by Git. `restore_build.py` copies exactly the two
hash-matched binaries from frozen 58j, after its documented rebuild if needed.
It refuses changed binaries, insufficient disk space or an oversized copy.
The binaries retain their original source-relative RoPE constant dependency in
58j; that constant and the native sources are pinned in the seal. Keep those
frozen inputs available. No standalone/public recipe is claimed.
If a native rebuild becomes necessary, use packet94's `compile_turn.py` and
one compiler at a time under the same nice/affinity restrictions; this task
needed no compilation.
