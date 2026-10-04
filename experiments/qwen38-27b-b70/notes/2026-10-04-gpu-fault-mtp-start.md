# GPU fault while a server loaded its weights, 2026-10-04 06:25 EDT

## In plain words

The test of speculation with several users never ran. Its server faulted one of the two cards while it was loading
the model, before any request was sent. This was the second fault since the last reboot, so by the owner's rule all
GPU work stopped and the machine needs a reboot before the test is tried again. Nothing was reset and nothing was
retried. Nothing is running on the cards.

It also corrects something we had written: the September fix (no swap for the container) made this start-up fault
rare, it did not end it. This start had the fix in place and faulted anyway, after 58 clean starts.

## What happened

| | |
|---|---|
| When | 2026-10-04 06:25:28 EDT, 66 seconds after the server start, 10 h 20 min into the boot |
| Card | `0000:e3:00.0` (the other card logged nothing) |
| Kernel lines | 27 x `Fault response: Unsuccessful -EINVAL`, `Engine memory CAT error [18]: class=bcs`, `Timedout job ... in python3 [274877]`, `Xe device coredump has been created` |
| Server | two-card research launcher, image R310, depth-5 speculation, 4 sequences, the three exactness overlays |
| Moment | the same second the log says `Loading weights took 8.47 seconds`; the draft model loads next |
| Kernel | 7.0.0-38, boot `66541315-49f1-41f7-af1d-4756d6b89c9c` |
| Health check before the start | passed (06:24:22) |

The copy engine (`bcs`) is the one that moves the weights from host memory to the card. Same engine, same moment
in the start and same kernel lines as the September start-up faults. Those were on the other card, `0000:03:00.0`.

## What it was not

- **Not container swap.** The container ran with `--memory 12g --memory-swap 12g`, was not OOM-killed, and the
  host swapped out 319 MiB during the start, which is what every clean start tonight did (80 to 316 MiB).
- **Not low host memory.** Available memory never went under 5.2 GiB. The memory guard did not fire.
- **Not a kill.** No process was killed; the launcher saw the kernel lines, stopped the server and latched.
- **Not the overlays or the speculation setting as such.** The fault came before the model finished loading.
  Seven earlier depth-5 starts tonight were clean.

## What we do not know

- Whether the first fault on this boot made this one more likely. That one (October 3, 22:39) was on the same card:
  the memory guard killed a busy server and the compute engine was reset. The health check passed afterwards and
  32 research starts were clean before this one.
- Whether the number of starts on one boot matters. This boot had 10 soak starts and 33 research starts.

## The count since the no-swap fix

| Period | Starts | Faults at load |
|---|---:|---:|
| 2026-09-19 to 2026-10-03, kernel 7.0.0-31 | 16 | 0 |
| 2026-10-03, kernel 7.0.0-38, soak | 10 | 0 |
| 2026-10-03/04, kernel 7.0.0-38, research servers | 33 | 1 (the last) |

One in 59. Before the fix it was five in about four days. So the fix helps a great deal and is not a cure.

## What was done

- Evidence saved to `/mnt/fast-ai/bench-results/gpu-fault-20261004T1025/`: the device dump (505 KB, copied before
  the kernel discards it), the whole kernel log of the boot, the fault lines, the server state, the memory trace.
  The small files are also in [the run's data folder](../data/2026-10-04-fp8-multiuser/three-mtp5-s4-fault/).
- No reset, no reboot, no retry, no health probe. No GPU work after 06:26.
- The test is now a script that refuses to run on this boot or on any boot that already has a fault line:
  `experiments/qwen38-27b-b70/scripts/run-20261004-fp8-mtp-under-load.sh`.

## Next

1. The owner reboots the machine.
2. Run the script above in its own unit. It answers the open question: is the shipped speculation still lossless
   with 4 and 8 users when the three fixes are on.
3. If a start faults again at load on a fresh boot, that is a rate worth acting on: the next step would be a
   bounded retry rule for start-up faults (stop, health check, one fresh start), not more diagnosis.
