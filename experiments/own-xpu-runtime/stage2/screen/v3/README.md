# Screen v3: independent masked pairs

CPU preparation only. No GPU window has run through v3 yet. The coordinator
must confirm the recorded native fdinfo proof and exact outputs on the device.
V1/v2 sources, seals and results are unchanged.

V3 accepts v1-compatible **two-card** lineages, including lean screen seals
and packet59c's selected directories. The candidate supplies its sealed binary,
dispatch, selection and memory plan. Packet56's fixed Python controller is
bound into the **wrapper's** seal; a candidate does not need `pipeline.py`,
`suite.py` or `storage.py`. Explicit `--binary`, `--dispatch` and `--seal`
overrides retain all hash checks. Packet57 attribution remains an explicitly
declared diagnostic timing mode. The one-card profile remains in v1.

| Lane | Physical cards / PCI buses | CPU cores | Nice | Native card indices |
| --- | --- | --- | --- | --- |
| A | 0+1 / `0000:23:00.0`, `0000:27:00.0` | `0-3,16-19` | 0 | 0, 1 |
| B | 2+3 / `0000:43:00.0`, `0000:47:00.0` | `4-7,20-23` | 0 | 0, 1 |

## Isolation and admission

Each native process receives a fixed, wrapper-generated environment:

```text
NEOReadDebugKeys=1
FilterBdfPath=0000:2                 # lane A; 0000:4 for lane B
ZE_ENABLE_PCI_ID_DEVICE_ORDER=1
ZE_AFFINITY_MASK=0,1
ONEAPI_DEVICE_SELECTOR=level_zero:0,1
```

The BDF filter is necessary: Intel's installed driver version,
`26.18.38308.1`, applies it **before opening** matching DRM nodes in
[`Drm::discoverDevices`](https://github.com/intel/compute-runtime/blob/26.18.38308.1/shared/source/os_interface/linux/drm_neo.cpp#L670-L762).
The ordinary affinity mask filters the resulting two-device list. Thus lane B
also passes native `--card 0` and `--card 1`, not 2 and 3. This is library
configuration, with no replacement engine, interposition shim or native build.

Before a launch, passive symlink/sysfs checks require the BDF prefix to match
**exactly** the lane's two registered Xe devices. Missing by-path entries,
extra matching devices, or a different PCI/driver mapping refuse. There is no
unfiltered fallback. An `igdrcl.config` in the working directory also refuses.
Caller-supplied selectors and debug options remain forbidden by the original
closed-environment gate; v3 inserts only the five fixed values above. Native
driver-cache homes are new directories under this run's adapter, as in v1.

Foreign-client admission reads `/proc/*/fdinfo`. It refuses clients on either
lane PCI, or an Xe client whose PCI cannot be identified. Known clients on the
other pair are recorded and allowed. Unreadable foreign entries remain
explicitly subject to coordinator ownership review, as in v2.

After each native launch, `DeviceMonitor` binds the PID to its start ticks and
samples its fdinfo. Both ranks must show their mapped device, and no foreign
or unidentified Xe handle, **before the incident request**. Their union must
be exactly the lane pair. The monitor continues at up to four samples/second
and checks again before teardown. It saves parsed fdinfo (FD, PCI and client
ID), PIDs, start ticks, masks and failures in `run/device-isolation.json`.
Unreadable own-rank fdinfo, PID reuse or a later foreign handle fails closed.
The outer window cannot pass without the isolation proof. Normal FINISH may
close FDs; the final live proof precedes that drain.

Standalone A and B screens have separate lane locks and no measurement barrier.
Stopping one sends no signal to the other. All v3 cooperative drains share a
gate: the next drain starts at least **60 seconds after the previous complete
drain**. Incomplete drains block further windows and retain their owner. The
gate does not coordinate old unmasked v1/v2 processes; an old process holding
the selected pair still prevents admission. Fault latches from v1/v2 remain
visible and are never cleared by v3.

All v2 safety conditions remain: exactly two reviewed fault lines bound to this
boot and the captured journal; fresh fault supervision; PF_EXITING-aware
memory sensing; blocks 54 and 56 offline; 8 GiB host reserve; 97 GiB available
before a standalone load, 105 GiB before a paired ordering; 8 GiB anonymous
envelope per screen; storage admission above the 8 GB free floor. A standalone
window reserves 1.1 GB; a full crossover admits 4.4 GB retained writes. Near
12 GB free, the full crossover can refuse storage even when a standalone fits.
No settings or floors are changed to make it pass.

## CPU validation and plans

From the repository root:

```bash
S=experiments/own-xpu-runtime/stage2
V="$S/screen/v3"
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest discover \
  -s "$V" -p 'test_*.py' -v
nice -n 19 taskset -c 8-15,24-31 python3 -B "$V/cpu_seal.py" --verify

nice -n 19 taskset -c 8-15,24-31 python3 -B "$V/screen.py" \
  --lane A --lineage "$S/packet56w-spin" \
  --seal "$S/packet56w-spin/screen-seal.json" \
  --binary "$S/packet56w-spin/build/device/own-rt-iq3" \
  --dispatch "$S/packet56w-spin/dispatch-speed6.json" \
  --output "$V/evidence/packet56w-A-01" --plan

nice -n 19 taskset -c 8-15,24-31 python3 -B "$V/screen.py" \
  --lane B --lineage "$S/packet59c-draft-select/selected/screen1-attention" \
  --seal "$S/packet59c-draft-select/selected/screen1-attention/build-receipt.json" \
  --binary "$S/packet59c-draft-select/selected/screen1-attention/build/device/own-rt-iq3" \
  --dispatch "$S/packet59c-draft-select/selected/screen1-attention/dispatch-speed6.json" \
  --output "$V/evidence/packet59c-B-01" --plan

nice -n 19 taskset -c 8-15,24-31 python3 -B "$V/screen.py" \
  --lane B --lineage "$S/packet60-hc-fusion" \
  --seal "$S/packet60-hc-fusion/screen-seal.json" \
  --binary "$S/packet60-hc-fusion/build/device/own-rt-iq3" \
  --dispatch "$S/packet60-hc-fusion/dispatch-speed6.json" \
  --output "$V/evidence/packet60-B-01" --plan

nice -n 19 taskset -c 8-15,24-31 python3 -B "$V/ab.py" \
  --x "$S/packet60-hc-fusion" --x-seal "$S/packet60-hc-fusion/screen-seal.json" \
  --y "$S/packet56-draft-prefix" \
  --output "$V/evidence/packet60-vs56-01" --plan
```

Plans read seals and oracle metadata, print commands and create no run output.
They launch no child, query no journal and perform no device discovery. All
three requested candidates are also tested on **both** lanes, with every
explicit override supplied. Retained plans are in [evidence](evidence/).

## Coordinator device commands — not executed during preparation

First create a fresh fault review on the CPU cores. This reads only the kernel
journal, captures the whole boot and requires exactly two fault records after
excluding deleted-coredump notices. A third line or changed boot refuses.
It derives the review boundary from the captured journal, never the clock.

```bash
S=experiments/own-xpu-runtime/stage2
V="$S/screen/v3"
nice -n 19 taskset -c 8-15,24-31 python3 -B "$V/fault_review.py" \
  --output "$V/evidence/review-window-01.json"
```

Run the following only **inside an authorized coordinator-owned `screen-*`
systemd user unit**, started at nice 0, with `Restart=no`, `SendSIGKILL=no`,
`KillMode=process`, `ExitType=cgroup`, `TimeoutStopSec=infinity`. A nice19
preparation process cannot raise itself to nice0. V3 checks the unit properties
and never creates, restarts or changes services.

Keep the coordinator's approved `LD_LIBRARY_PATH`. For independent lanes,
each command belongs in its own admitted unit; the second can start while the
first runs if its pair and host admission pass:

```bash
taskset -c 0-3,16-19 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$V/screen.py" --lane A \
  --lineage "$S/packet56w-spin" --seal "$S/packet56w-spin/screen-seal.json" \
  --output "$V/evidence/packet56w-A-01" \
  --fault-review "$V/evidence/review-window-01.json" --authorized-device-window

taskset -c 4-7,20-23 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$V/screen.py" --lane B \
  --lineage "$S/packet60-hc-fusion" --seal "$S/packet60-hc-fusion/screen-seal.json" \
  --output "$V/evidence/packet60-B-01" \
  --fault-review "$V/evidence/review-window-01.json" --authorized-device-window
```

For a crossover, use the following **instead of** standalone commands on those
pairs. X is the candidate and Y the control. This runs X/A with Y/B, then swaps
to Y/A with X/B. Both lane admissions must finish before release. Both suites
must finish before either normal teardown starts. Any failure stops the helper
from starting the next ordering; no automatic retry or service restoration.

```bash
taskset -c 8-15,24-31 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$V/ab.py" \
  --x "$S/packet60-hc-fusion" --x-seal "$S/packet60-hc-fusion/screen-seal.json" \
  --y "$S/packet56-draft-prefix" \
  --fault-review "$V/evidence/review-window-01.json" \
  --output "$V/evidence/packet60-vs56-01" --authorized-device-window
```

The helper also accepts `--x-binary`, `--x-dispatch`, `--y-binary`,
`--y-dispatch`, `--y-seal`, and separate timing modes. Use fresh output names
for separately authorized attempts. A new output name is not retry authority.

## Exactness and interpretation

Each screen loads one rank pair once, checks a separate 64-token incident
request against packet49, resets state and checks **all 12 × 128 tokens**
against the same oracle. The target, arithmetic, full BF16 KV, split 23/25,
draft rank 1 and verifier are unchanged. A mismatch cannot become a passed
screen. There is no prompt/KV/response reuse or learned draft.

The metric remains the conventional 99 intervals between token events 1–100,
then class medians and the median across classes. The crossover retains both
orderings, per-prompt and per-class differences, and their combined difference.
It does not turn a small difference into a statistically supported speed claim.
Every result is diagnostic and ineligible for promotion or submission. Native
masking, model exactness and crossover performance are **pending device work**.

See the [task note](../../../../../notes/2026-10-17-own-runtime-screen-v3.md)
and [CPU closeout](CPU-PREPARATION-CLOSEOUT.md).
