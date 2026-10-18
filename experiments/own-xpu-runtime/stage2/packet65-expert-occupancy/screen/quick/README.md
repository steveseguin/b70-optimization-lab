# Packet65 quick token screens

Ready for coordinator execution; no device result yet. This path asks whether
an expert choice improves end-to-end token rate before spending device time
on the whole-host 30% class-latency gate.

The existing `v3-packet64-lanes` and `v3-attr` wrappers do not admit packet65's
placement-1 views, and their live entry points admit only lane B. Packet65's
original wrapper sources are themselves bound by all five selection seals.
Therefore this additional copy lives under `screen/quick/`; no existing sealed
file, selection, model binary, or frozen tree changes. `quick_seal.py` checks
both the original wrapper seal and this wrapper's new source closure.

`screen.py`, `devices.py`, and `tp2_worker.py` are focused copies of packet65's
wrapper. `lane_admission.py`, `chain_devices.py`, and `drain_gate.py` come from
the lab's frozen `screen/v3-packet64-lanes` protocol. The only change to that
reservation implementation adds diagnostic `screen` to lane A's permitted
single-lane windows. Existing whole-host timing holds still block lane B.
The original worker request/reset/teardown flow is unchanged.

Each screen takes its own cooperative A or B lease and its own legacy v3 lock,
then releases only after exactness, process exit, native device isolation and
postflight pass. Failure retains its active marker for coordinator review.
B may compute under a proven live A exactness permit, following the existing
protocol; it waits during a whole-host timing hold. A refuses an existing A
owner rather than retrying it. The coordinator schedules these jobs when the
corresponding lane is available. This preparation does not queue any job.

The fixed masks expose physical cards 0+1 on A and 2+3 on B as native cards
0+1. Foreign clients on the selected pair still fail admission and monitoring.
The other pair is allowed. Full BF16 KV, packet49 tokens, incident64, all twelve
128-token prompts, the 97 GiB admission floor, 8 GiB live host reserve and
anonymous-memory guard remain. Actual drains still serialize under the shared
v3 teardown lock with at least 60 seconds after the previous completed drain.
The runner adds 90 seconds between screens (five gaps). It starts no services,
retries nothing, never skips a failed screen, and forwards stop only to its
current child. No hard kill or service restoration is used.

The per-screen watchdog stays **3,600 seconds**, more than 4x the expected
210-second screen. Expected lane time is 28.5 minutes plus admission/drain
contention, roughly 30 minutes; this is an estimate, not a timeout or measured
result. Parallel teardown/host contention may affect diagnostic rates; compare
only against the two controls on that same lane and confirm a winner later.

| Lane | Cards | Cores | Order |
| --- | --- | --- | --- |
| A | 0+1 | 0-3,16-19 | production, wide64, wg64, wg128, prefetch64, production |
| B | 2+3 | 4-7,20-23 | production, prefetch64, wg128, wg64, wide64, production |

[Jobs A](jobs-A.txt) and [jobs B](jobs-B.txt) use the six-field `v3-lane3.sh`
format: `out|lineage|seal|binary|dispatch|placement`. Use this directory's
`run.py`, not the temporary old runner: it selects the new wrapper, explicitly
uses token timing and placement 1, and stops on every failure. Evidence is
written below packet65's existing `screen/evidence/`, with unique `p65-quick-*`
names. Both production screens are fresh processes. All six output paths must
be unused. Do not reuse or delete finished paths for a rerun.

## CPU checks

From the repository root:

```bash
P=experiments/own-xpu-runtime/stage2/packet65-expert-occupancy
Q="$P/screen/quick"
nice -n 19 taskset -c 8-15,24-31 python3 -B "$Q/quick_seal.py" --verify </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$Q/run.py" --lane A --jobs "$Q/jobs-A.txt" --plan </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$Q/run.py" --lane B --jobs "$Q/jobs-B.txt" --plan </dev/null
```

[CPU tests](cpu-tests.log) include mocked complete job orders, stop-on-failure,
concurrent lane leases, stale-owner refusal, timing holds, selected-device
isolation, class accounting, token mismatch, and the full 13-request worker
flow. No CPU model runs. [Plans A](plans-A.json), [plans B](plans-B.json) and
[validation receipt](validation.json) bind the CPU preparation.

## Coordinator commands

Run from `/home/steve/llm-optimizations` after the coordinator admits the two
lanes. Set `FAULT_REVIEW` to the current reviewed boot-bound receipt; the
wrapper checks it before and during the run. The existing coordinator file
supplies the approved library path. These commands create the two independent
nice0 units and return immediately so both lanes can run together.

```bash
cd /home/steve/llm-optimizations
P=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet65-expert-occupancy
Q="$P/screen/quick"
source /tmp/claude-1000/-home-steve/fn-run/p49.env
: "${FAULT_REVIEW:?Set the coordinator reviewed boot-bound receipt path}"
: "${P49_LDP:?Approved coordinator library path required}"

systemd-run --user --unit=screen-p65-quick-A \
  --property=Restart=no --property=SendSIGKILL=no --property=KillMode=process \
  --property=ExitType=cgroup --property=TimeoutStopSec=infinity --property=Nice=0 \
  --property=WorkingDirectory=/home/steve/llm-optimizations \
  /usr/bin/taskset -c 0-3,16-19 /usr/bin/env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$P49_LDP" \
  /usr/bin/python3 -B "$Q/run.py" --lane A --jobs "$Q/jobs-A.txt" \
  --fault-review "$FAULT_REVIEW" --authorized-device-window </dev/null

systemd-run --user --unit=screen-p65-quick-B \
  --property=Restart=no --property=SendSIGKILL=no --property=KillMode=process \
  --property=ExitType=cgroup --property=TimeoutStopSec=infinity --property=Nice=0 \
  --property=WorkingDirectory=/home/steve/llm-optimizations \
  /usr/bin/taskset -c 4-7,20-23 /usr/bin/env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$P49_LDP" \
  /usr/bin/python3 -B "$Q/run.py" --lane B --jobs "$Q/jobs-B.txt" \
  --fault-review "$FAULT_REVIEW" --authorized-device-window </dev/null
```

After both units complete:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B "$Q/compare.py" </dev/null
```

The helper verifies the finished artifacts, lane/drain proof, model selection,
packet49 oracle and all 13 token streams. It recomputes each request rate as
`99 / (t100 - t1)`, takes the median within each of the six prompt classes,
then the median across classes. Each lane's denominator is the arithmetic
mean of its two production screen rates. Missing/failed evidence is refused;
changed output prints FAIL. Incident64 is checked but not included in speed.
These are 128-token diagnostic screens, not public speed or final quality
results. A winner still needs the whole-host class-latency campaign and full
qualification. The default selection stays production.
