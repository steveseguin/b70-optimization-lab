# One-load diagnostic screens

`screen.py` reuses a sealed engine and dispatch. It builds no native code and
does not edit, reseal or write caches into a parent packet. Packet 57 and the
packet 58 chain retain device ownership until their coordinator releases it.
Preparation and `--plan` are CPU-only. Only the coordinator runs a device screen.

The two-card profile starts one persistent rank pair on physical cards 0+1,
loads each rank once, checks the incident-retrospective prompt's 64 generated
tokens against packet 49, resets request state, then runs all 12 fixed prompts
at 128 tokens. Every emitted token must match the same oracle. It uses the
sealed native controller, target split 23/25, draft rank 1, context 4096, BF16
KV, token timing, and `retain-steps none`. There is one final teardown of the
pair, with no cooldown or additional model launch between requests.

**Sealed one-card interface limitation:** packet 58 accepts at most 12 requests
and one shared cap per launch. It cannot execute a separate 64-token request
and then twelve 128-token requests. `--incident-prefix` explicitly chooses the
compatible alternative: check the first 64 tokens of incident-retrospective,
the first 128-token suite request. The supervisor reads complete flushed timing
lines while the owner runs and saves `incident64.json`. All 12 full responses
are then checked against the oracle. This limitation was raised with the owner;
the explicit flag keeps the choice visible. Without the flag, one-card launch
is refused. A separate 13th request needs a new binary, outside this wrapper.

One-card is target-only on physical card 0, with the same sealed 18 GB immutable
expert-weight cache. The conservative screen default is copy-before-use
(`--miss-path streamed`); a coordinator may explicitly select `zero-copy` for
that experiment. The cache can persist, but KV, recurrent state, prompt and
response data reset per request. Hit/miss cycles and acceptance are **null / not
applicable** on this target-only path, not fabricated MTP statistics.

Both profiles use the WS128 metric implementation unchanged: 99 intervals
between generated events 1 and 100, class medians then median across classes,
all-prompt median, p10, mean, TTFT, wall rate, acceptance and hit/miss cycles.
Prompt/output hashes and per-event timestamps remain available. The incident
check is excluded from suite metrics. Every receipt and summary is labeled
**screen**, diagnostic and ineligible for submission. A promising screen must
run its full sealed chain, including fresh-owner repeats, before submission.
The repeated two-card incident prompt is separated by a full state reset; this
screen makes no cold-suite promotion claim. CPU priority is nice19 throughout,
including native ranks; this differs from the historical nice0 record runs.

## Coordinator commands

Run only after the protected chains finish and fresh ownership, host memory,
storage and journal admission pass. `REVIEWED_THROUGH` must already contain the
coordinator's actual **past UTC** review boundary for this boot. Never fill it
with an automatic current time. Keep the approved `LD_LIBRARY_PATH`.

Inside a coordinator-owned `screen-*` systemd user unit, from the repository
root, with `Restart=no`, `SendSIGKILL=no`, `KillMode=process`,
`TimeoutStopSec=infinity` and `ExitType=cgroup`:

```bash
nice -n 19 taskset -c 4-15,20-31 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B experiments/own-xpu-runtime/stage2/screen/screen.py \
  --profile tp2 --lineage experiments/own-xpu-runtime/stage2/packet56-draft-prefix \
  --authorized-device-window --faults-reviewed-through "$REVIEWED_THROUGH" \
  --output experiments/own-xpu-runtime/stage2/screen/evidence/packet56-a
```

The one-card command, with the interface limitation explicitly selected:

```bash
nice -n 19 taskset -c 4-15,20-31 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B experiments/own-xpu-runtime/stage2/screen/screen.py \
  --profile onecard --lineage experiments/own-xpu-runtime/stage2/packet58-onecard \
  --incident-prefix --miss-path streamed \
  --authorized-device-window --faults-reviewed-through "$REVIEWED_THROUGH" \
  --output experiments/own-xpu-runtime/stage2/screen/evidence/packet58-a
```

Append `--plan` to either command for a CPU-only seal/oracle check and printed
native command. It needs no unit and creates no output, queries no journal,
does no device discovery and loads no model. No command above was executed as
a device window during preparation. Use new output names for separately
authorized experiments; never use a new name as an automatic retry.

The optional `--binary`, `--dispatch` and `--seal` arguments accept another
sealed compatible candidate. Defaults are the lineage's
`build/device/own-rt-iq3`, `dispatch-speed6.json` and `build-receipt.json`.
The candidate must preserve the profile's controller ABI, arithmetic, fixed
topology, selection contract and memory envelope. A different allocation
budget needs a reviewed safety-profile change, not a silent seal exception.

## Safety and retained evidence

The wrapper uses packet 56's passive supervision and packet 58's closed
environment and memory checks. It requires blocks **54 and 56 offline** and
records 53/55/57. It checks visible Xe clients, reserves output storage above
the existing 8 GB free floor, verifies the CPU seal and oracle bindings, and
rechecks memory and storage before launch. Two-card needs 97 GiB available;
one-card retains the exact packet 58 host-shadow budget, about 118.31 GB.
Unknown environment variables are refused without printing their values.

The journal and PF_EXITING-aware process-memory sensor run every 250 ms. Host
available memory must stay above 8 GiB; the one-card GPUActive and pinned-host
bounds remain enforced. A fault, unavailable sensor, timeout or stop request
causes cooperative SIGTERM, never a kill or restart. Five seconds of journal
postflight follow exit. An owner that cannot drain stays under its user unit
for the coordinator, with exit status 75 and a durable latch. The screen never
clears latches, changes memory blocks or host settings, or recovers a driver.
The two-card inner controller retains its stop-descriptor and drain protocol.

Admission reserves 1.1 GB for a two-card window (one raw state snapshot at a
time, inherited verified state retention, request logs and cache allowance),
or 256 MiB for one card. No weight or build copy is made. Screen locks, latches,
rank caches and run outputs live here, outside sealed packets. The final
window receipt binds identities, environment, oracle, wrapper sources, logs,
per-request results and teardown evidence. Failed evidence stays in place.

## Duration and CPU tests

Today's retained WS128 start/stop receipts measured **191.05 s for packet 49d**
and **188.51 s for packet 56**, including their complete windows. Adding the
brief's approximately four-minute KD duration gives about **7.2 minutes**;
**7–8 minutes** is a conservative two-card planning estimate because it counts
loading twice. The target is under 15 minutes including load. This screen has
not been timed on a device. The recorded basis is [duration-basis.json](duration-basis.json).
One-card duration is unmeasured; the two-card estimate does not transfer to it.
The 3,600 s / 7,200 s watchdogs are stop limits, not duration predictions.

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B -m unittest discover \
  -s experiments/own-xpu-runtime/stage2/screen -p 'test_*.py' -v
```

Tests use fake owners and small CPU fixtures. See [lean preparation](LEAN-CPU.md)
and the [task note](../../../../notes/2026-10-17-own-runtime-screen-window.md).
