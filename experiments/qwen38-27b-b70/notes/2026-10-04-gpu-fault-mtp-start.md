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

## Review, later the same day: why it failed

**Short answer: a bug in Intel's GPU driver stack, hit by timing while a model loads. Not our settings, not a bad
card, not memory.** It is the open upstream report `intel/compute-runtime#948`; other owners of two and four B70s
see the same family and Intel has no fix yet.

**The new evidence.** Every start-up fault we have saved is the same event, down to the address:

| Fault | Card | Kernel | Container swap | Pages the copy engine could not read |
|---|---|---|---|---|
| 2026-09-16 | 03:00.0 | 7.0.0-31 | allowed | `0x800400200000` to `0x800400228000`, first `...213000` |
| 2026-09-17 03:10Z | 03:00.0 | 7.0.0-31 | allowed | the same range, first `...213000` |
| 2026-09-19 | 03:00.0 | 7.0.0-31 | allowed | the same range, first `...213000` |
| 2026-10-04 | e3:00.0 | 7.0.0-38 | off | the same range, first `...213000` |

Same 160 KiB of GPU address space, the same pages in nearly the same order, always a read by the copy engine, always
while the model loads, always `IPEHR 0x13000203` in the dump. Two cards, two kernels, swap on and off, four
different processes. Random memory pressure would hit different buffers each time. This is one specific small buffer
that the runtime asks the copy engine to read at a moment when it is not mapped: a race inside the driver stack
(the `xe` kernel driver and the Level Zero runtime, version 26.27.39122.11 in our image).

**What that changes.**

- Container swap was never the cause. It made the timing worse, which is why turning it off cut the rate from five
  in four days to one in 59 starts.
- The card is not suspect. The same fault has now been on both cards.
- The first fault on this boot (October 3, 22:39) is a different, harmless class: its address ends `...56aa4c7000`,
  the same address three other reporters see after killing a busy job. So this boot had one real fault, not two.
- The saved kernel logs were hiding the address: the fault record is one multi-line message and our line filters
  kept only its first, empty line. Read it with `journalctl -k -o json` or `-o cat`.

**What we still do not know:** which buffer lives at `0x800400200000`. The runtime in the image has the logging
switches to say (`NEOReadDebugKeys=1` with `LogAllocationType`, `PrintBOBindingResult`); one logged start on a
healthy boot names it. That would turn our upstream report from "it faults sometimes" into "this buffer, this
address, four times", and may show a way to avoid the race from our side.

**What others report that may help:** three independent B70 owners in the upstream thread see far fewer faults on
kernel 6.17 than on 7.0. Their faults are under load, ours are at load time, so it may not carry over, and at one
fault in 59 starts a fair comparison needs well over a hundred starts.

## What was done

- Evidence saved to `/mnt/fast-ai/bench-results/gpu-fault-20261004T1025/`: the device dump (505 KB, copied before
  the kernel discards it), the whole kernel log of the boot, the fault lines, the server state, the memory trace.
  The small files are also in [the run's data folder](../data/2026-10-04-fp8-multiuser/three-mtp5-s4-fault/).
- No reset, no reboot, no retry, no health probe. No GPU work after 06:26.
- The test is now a script that refuses to run on this boot or on any boot that already has a fault line:
  `experiments/qwen38-27b-b70/scripts/run-20261004-fp8-mtp-under-load.sh`.

## What is now in place (09:30 EDT, built and dry-run on the CPU; not yet exercised on the cards)

- **Automatic one-time recovery.** `scripts/load_fault_recovery.py` recognises this exact fault (copy-engine reads at
  `0x800400200000`, before the server is ready). The multi-user campaign's `start_server` then does what AGENTS.md
  already says for a first fault: stop the server, wait a minute, run the health probe, and make one fresh start.
  Anything else still halts: a fault while serving, a different address, a failed probe, or any earlier fault on the
  same boot.
- **A start that names the buffer.** `MU_MODE=namebuffer` starts the shipped two-card server once with the runtime's
  allocation logging on and saves every log line that mentions the fault address range. It is step 0 of the
  after-reboot script.

## Next

1. The owner reboots the machine (or says the health check is enough: this boot had one real fault).
2. Run `scripts/run-20261004-fp8-mtp-under-load.sh`: the naming start, the speculation test, the one-exchange
   speed-up.
3. Post the finding upstream (`intel/compute-runtime#948`), with the buffer's name if step 2 found it. Needs the
   owner's go-ahead since it is a public post.
