# GPU fault while a server loaded its weights, 2026-10-04 06:25 EDT

## In plain words

**Update, 11:10 EDT: the cause is found and a fix is validated; see "Review" and "Measured on the cards" below.**
The fault is the card's copy engine reading a temporary mapping the runtime makes for any upload of 512 MiB or more
(here the 1.27 GB embedding and output-layer weights). Sending those uploads in 128 MiB pieces makes no mapping. With
that overlay the server is exact and as fast as before. No reboot was needed.

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

**What that buffer is (from the driver sources, read the same day).** The runtime in our image is
compute-runtime 26.27.39122.11 and the kernel driver is `xe` from Linux 7.0; both sources were read at those versions.

- The kernel answers `-EINVAL` to a GPU page fault in exactly two cases: the address space is not in fault mode, or
  **no mapping exists at the faulting address** (`xe_pagefault_service`). The runtime creates its address space in
  fault mode on this card, so it is the second case: the copy engine read an address where nothing was mapped.
- `0x800400200000` is the first slot for large objects in the runtime's "standard" address pool (pool base
  `0x800400000000` plus 2 MiB; objects over 4 MiB are placed from the bottom). Three kinds of object go in that
  pool. The one that is over 4 MiB, short-lived and read by the copy engine is the **temporary mapping of host
  memory made for a host-to-card copy** (`allocateGraphicsMemoryForNonSvmHostPtr`). Each one is released after its
  copy and the next one gets the same address, which is why every incident shows the same address.
- A host-to-card copy of 4 MiB or less is already done on the CPU, straight into the card's memory, with no mapping
  and no copy-engine job (`preferCopyThroughLockedPtr`, threshold 4 MiB). Only larger copies take the faulting
  path. Loading a model is thousands of large copies in a row, which is why the fault only ever shows up there.

So the event is: during a weight upload, the copy engine reads the temporary mapping of the host buffer and the
mapping is not there. Which side drops it early (the runtime releasing it before the copy has finished, or the
kernel) is not proven by reading; the runtime's release logic for these mappings is shared between its command
queues and is the likelier place. Memory pressure slows the copy engine's reads of host pages, which widens the
window; that is how container swap made it frequent.

**The fix to test.** The runtime has a switch for the 4 MiB limit: `ExperimentalH2DCpuCopyThreshold` (read when
`NEOReadDebugKeys=1`; both strings are in our image's library). Set to its largest value (2 GiB minus one byte) it
makes every weight upload a CPU copy. No temporary mapping is created and no copy-engine job reads host memory, so
the operation that faults does not happen at all. It copies the same bytes, so answers cannot change. The largest
single upload in this model is 1.27 GB per card, under the limit. Both cards expose their full 32 GB memory window,
which this path needs.

**Test, written before it runs (`MU_MODE=loadcopy`, step 0 of the after-reboot script).** Three starts of the
shipped two-card server: (1) the runtime's allocation log without the switch, (2) the same log with it, (3) the
switch alone with the strict gate.

**Rule.** The switch is adopted for research starts if the log shows host-memory mappings at `0x8004002...` without
it and none with it, the strict gate is 12 of 12 exact at the usual speed (within 1 % of 90 tok/s), and the weight
load is not more than twice as slow. If the log lines cannot be read that way, the claim is limited to "exact and
no slower"; the mechanism is then not shown. Putting it in the two package launchers is a separate step: their
bytes are pinned by the acceptance packets, so it needs a new acceptance.

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

## Measured on the cards, 09:40 to 10:10 EDT (owner chose a health check over a reboot; it passed)

Receipts: `/mnt/fast-ai/bench-results/fp8-loadcopy-20261004*/` and `fp8-loadcopy-probe-20261004/`.

| Question | Result |
|---|---|
| What is at the fault address? | The runtime's own log says it: `EXTERNAL_HOST_PTR`, 1,271,398,400 bytes, GPU address `0xffff800400200040`. That is the embedding and output-layer weight (124,160 x 5,120 values of 16 bits). Eight such mappings per two-card start: at the very end of the main weight load and during the draft-model load, exactly where the faults have struck. |
| Does the runtime switch (`ExperimentalH2DCpuCopyThreshold`) avoid it? | **No.** Same eight mappings with it, on the server and on a one-card probe. The card-side memory torch uses is not the kind the runtime's CPU-copy path accepts. Forcing that path (`ExperimentalForceCopyThroughLock=1`) crashes the process. Dropped. |
| Which uploads make the mapping? | One-card probe by size: 2, 8, 64 and 256 MiB make none (they go through the runtime's staging buffers). 512, 1,024 and 1,212 MiB each make one, at the fault address. |
| Does uploading in 128 MiB pieces avoid it? | **Yes on the probe:** a 1.27 GB tensor sent in pieces made no mapping, arrived bit-identical, and took 0.08 s against 0.14 s. |
| Does the first overlay do that in the real server? | No. The server was exact (12 of 12, 90.4 tok/s) but the overlay caught none of the eight uploads: the server's copy also converts the number format, which the first version left alone. |
| Does the second overlay? | **Yes (11:00 to 11:07 EDT).** It sent all eight uploads in pieces (4 per card, 4.74 GiB per card). The runtime's log shows **no host mapping and nothing at the fault address** during the whole start (without the overlay: 8 mappings, 24 log lines there, in each of three logged starts). The strict gate is 12 of 12 exact at 90.33 tok/s. The weight load takes 8.4 s, as before. |

**Verdict by the rule written above: adopted for research starts.** The operation that faulted no longer happens
during a two-card model load. What this does not show is a fault count: at one fault in 59 starts, counting would
take hundreds of starts. The claim is the mechanism: every saved start-up fault was a read of that mapping, and the
mapping is no longer made.

Data: [`data/2026-10-04-load-fault-fix/`](../data/2026-10-04-load-fault-fix/). Overlay:
`overlays/b70-chunked-upload/` (`B70_CHUNKED_UPLOAD=1`), CPU test `tests/test_b70_chunked_upload.py`.

## What is now in place (09:30 EDT, built and dry-run on the CPU; not yet exercised on the cards)

- **Automatic one-time recovery.** `scripts/load_fault_recovery.py` recognises this exact fault (copy-engine reads at
  `0x800400200000`, before the server is ready). The multi-user campaign's `start_server` then does what AGENTS.md
  already says for a first fault: stop the server, wait a minute, run the health probe, and make one fresh start.
  Anything else still halts: a fault while serving, a different address, a failed probe, or any earlier fault on the
  same boot.
- **The fix test.** `MU_MODE=loadcopy`, described above. It replaced the plain "name the buffer" start, since the
  sources already name it.

## Next

1. The multi-user campaign now uses the overlay by default (`MU_LOADCOPY_FIX=0` turns it off).
2. One card: its output-layer weight is 2.5 GB, the same path. Validate the overlay there (allocation log and the
   one-card strict gate) before making it the research launcher's default.
3. The two package launchers do not have it. Their bytes are pinned by the acceptance packets, so adding it means a
   new acceptance for each. Owner's call, since it changes the published packages.
4. The MiniMax video lane loads its models with its own scripts; the same piece-wise upload applies there.
5. Post the finding upstream (`intel/compute-runtime#948`): the address, what lives there, the 256/512 MiB dividing
   line and the workaround. Needs the owner's go-ahead since it is a public post.
