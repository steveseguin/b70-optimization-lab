# Screen v2: two simultaneous lanes, then swap

CPU preparation is complete. **No v2 device run or speed claim has been made.**
This folder is independent of v1 and leaves its results and all sealed packets
unchanged. It supports the two-card packet56 controller family, packet57 timing,
and compatible candidates with a lean screen seal. One-card screens remain v1.

| Lane | Engine cards | PCI pair | CPU cores | Priority |
| --- | --- | --- | --- | --- |
| A | 0, 1 | 0000:23:00.0, 0000:27:00.0 | 0–3,16–19 | nice 0 |
| B | 2, 3 | 0000:43:00.0, 0000:47:00.0 | 4–7,20–23 | nice 0 |

The worker passes `--card 0` or `--card 2` to the lineage's controller, which
passes `--card base+rank --cards 1` to each native rank. This is the same
selection mechanism as packet45's cards-2+3 replicate; see
[the SPEED6 commands](../../packet45-merged3/SPEED6-CLOSEOUT.md).
Lane A's PCI pair is also retained in v1 packet56-a's
`run/ranks/rank*/drm-memory-after_load.txt`.

Each lane has its own lock, output, rank caches and nice0 CPU condition check.
The worker imports the **selected lineage's** sealed pipeline and suite.
Packet56 supports `token`; packet57 supports `token` and `attribution`.
Unsupported modes are refused before launch. No device selector remapping is
used. The environment stays closed with `OMP_NUM_THREADS=2`.

Each screen loads one pair once, checks incident64, resets state and runs all
12 fixed prompts at 128 tokens against the unchanged packet49 oracle. Every
one of the 1,536 suite tokens must match. BF16 KV, target split 23/25, rank-1
draft, 4096 context and the unchanged allocation envelope are required.
The 64-token check is excluded from suite metrics. These remain diagnostic
screens, with the strict realistic final gate false; a record needs its full
sealed chain and fresh-owner qualification.

## CPU preparation and planning

All commands below are from the repository root. CPU helpers use nice19 and
cores **8–15,24–31**. They never discover devices or run a model.

```bash
V=experiments/own-xpu-runtime/stage2/screen/v2
nice -n 19 taskset -c 8-15,24-31 python3 -B "$V/cpu_seal.py" --verify
nice -n 19 taskset -c 8-15,24-31 python3 -B -m unittest discover \
  -s "$V" -p 'test_*.py' -v
nice -n 19 taskset -c 8-15,24-31 python3 -B "$V/ab.py" \
  --x experiments/own-xpu-runtime/stage2/packet57-attribution --x-timing attribution \
  --y experiments/own-xpu-runtime/stage2/packet56-draft-prefix --y-timing token \
  --output "$V/evidence/p57-vs56-a" --plan
```

The initial build used `cpu_seal.py` without `--verify`: compile each Python
source in memory, run the focused tests and one orchestration byte fixture,
then seal the sources and evidence. There is no native code change or build.
The fixture runs the complete v1/v2 worker flow through a small fake transport;
all 12 request receipts are byte-identical while the card/priority arguments
change. This is an orchestration check, **not device exactness evidence**.
The saved plan is [plan.json](plan.json), the checks are
[cpu-tests.log](cpu-tests.log), and the source/artifact closure is
[wrapper-seal.json](wrapper-seal.json). Device entry points verify that seal.

## Fault review: count first, boundary second

Run this passive check shortly before the coordinator window:

```bash
V=experiments/own-xpu-runtime/stage2/screen/v2
nice -n 19 taskset -c 8-15,24-31 python3 -B "$V/fault_review.py" \
  --output "$V/evidence/review-p57-vs56-a.json"
```

It reads **this boot's entire kernel journal**, uses `window_driver.py`'s
`FAULT` and `DELETED` expressions, and refuses unless there are **exactly 2**
fault records after excluding deleted-coredump notices. Only then does it
derive the boundary from the last captured kernel timestamp. It retains the
compressed full capture, the two fault records, boot, cursor, timestamp and
hashes. It never substitutes the current clock for reviewed history.

The CPU preparation capture found exactly two lines; see
[evidence/cpu-review.json](evidence/cpu-review.json). A real launch rechecks the
capture binding, boot, exact two records and fresh journal tail. A third fault,
a replacement fault, a new boot, missing journal or edited capture refuses the
window. Live supervision uses the same expressions, including `GPU HANG`,
lockups and hardware errors. No fault latch or coredump is cleared.

## Coordinator A/B command

**Only the coordinator executes device commands.** Start inside a coordinator
owned `screen-*` systemd user unit configured with `Restart=no`,
`SendSIGKILL=no`, `KillMode=process`, `ExitType=cgroup` and
`TimeoutStopSec=infinity`. The wrapper verifies these properties. No service
was created or used during preparation. The unit must start at nice0: a
nice19 process cannot raise itself to nice0 without privilege.

Inside that unit, use the approved library path and a closed environment:

```bash
V=experiments/own-xpu-runtime/stage2/screen/v2
taskset -c 8-15,24-31 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$V/ab.py" \
  --x experiments/own-xpu-runtime/stage2/packet57-attribution --x-timing attribution \
  --y experiments/own-xpu-runtime/stage2/packet56-draft-prefix --y-timing token \
  --fault-review "$V/evidence/review-p57-vs56-a.json" \
  --output "$V/evidence/p57-vs56-a" --authorized-device-window
```

This example measures attribution overhead. Use `--x-timing token` for a
comparison with ordinary token timing, or supply another compatible sealed
candidate with `--x`, `--x-seal`, `--x-binary`, `--x-dispatch` (and equivalent
`--y-*` options). Existing packet56/57 seals are verified, never regenerated.
New candidates can use [the lean seal contract](../LEAN-CPU.md), with their
pipeline, suite and storage helpers included in the source closure. A lean
seal defaults to token timing; other timing support must be explicitly bound
in its `timing_modes` field. Do not claim attribution timing is ordinary speed.

The helper runs **X on A and Y on B together**, waits for both measurements and
drains, then runs **Y on A and X on B together**. Both lane wrappers must pass
admission before the common start barrier opens. It never retries a failed
window or proceeds to the second ordering after failure.

Both suites finish before the first normal teardown starts. A shared gate
covers every v2 worker, including standalone screens and cooperative error
cleanup. It serializes drains and waits **at least 60 seconds after the prior
pair has completely drained** before the next teardown starts. Teardown
receipts record start/end monotonic times; the A/B helper checks the gap.
An incomplete drain blocks new launches and leaves the owner in its unit.
An uncommanded native crash cannot be scheduled by Python; that invalidates
the pair, stops further launches and retains failure evidence.

Both lanes preserve the inherited 97 GiB prelaunch check. Concurrent admission
requires 105 GiB available: the original floor plus another full 8 GiB
anonymous-process envelope for the second pair, sharing the same immutable
mapped model inputs. Both passive supervisors enforce the 8 GiB host reserve
and their respective anonymous-memory ceilings throughout. The inherited bad
RAM fence is unchanged. Storage admission reserves 4.4 GB for the four screens
while keeping the existing 8 GB free floor. A new allocation envelope requires
a separate reviewed profile; neither builds nor weights are copied here.

## Output, interpretation and expected duration

`comparison.json` retains both orderings, every prompt difference, each class's
candidate/control median and difference, and each ordering's overall
class-balanced difference. The combined result reports the arithmetic mean of
the two signed tok/s differences and the geometric mean of the two ratios,
expressed as percent. The latter cancels a fixed multiplicative lane bias.
It does not remove changing host contention or give a confidence interval.
The helper prints the combined per-class and overall results and their path.

The primary metric is still **99 inter-token intervals between generated
stamps 1 and 100**, class medians then median across classes. A 1–2% change
needs repeated fresh crossovers; the packet56 spread of 46.07–47.04 tok/s
already overlaps that range. A single crossover is not an automatic ranking
or promotion. Both orderings and all exactness checks are mandatory.

Plan **8–10 minutes for one complete A/B crossover (both orderings, four
screens)**. The measured v1 packet56-a window was 213.04 seconds; two concurrent
rounds plus two 60-second teardown gaps give about 546 seconds (9.1 minutes),
with loading/drain variation. This is an estimate, not a v2 measurement.
Attribution or a slower candidate may take longer. The 3600-second per-screen
watchdog is a stop limit, not a duration estimate.

A standalone lane remains available inside the same kind of admitted nice0
unit, with its exact lane affinity:

```bash
V=experiments/own-xpu-runtime/stage2/screen/v2
taskset -c 4-7,20-23 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B "$V/screen.py" --lane B --timing token \
  --lineage experiments/own-xpu-runtime/stage2/packet56-draft-prefix \
  --fault-review "$V/evidence/review-p57-vs56-a.json" \
  --output "$V/evidence/B-p56-a" --authorized-device-window
```

Append `--plan` and use the CPU preparation affinity/priority for a CPU-only
standalone plan. Use fresh output names for separately authorized attempts;
a new name never authorizes an automatic retry.
