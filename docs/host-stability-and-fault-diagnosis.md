# Host stability and fault diagnosis on a multi-GPU B70 workstation

How this lab found out why its four-card machine kept freezing, what each
fault looked like, and the commands that separated one cause from another.
Nothing here depends on which model was running. The reader-friendly summary
is the [Host stability guide](../learn/host-stability.html); host *speed*
tuning is a separate page, [Host tuning](../learn/host-tuning.html).

Last updated 2026-10-03. Numbers are from one machine and are labelled where
they are inference rather than measurement.

## The short version

- Between 2026-09-13 and 2026-10-03 the four-B70 host ended **34 of 38 boots
  uncleanly**. It looked like one problem. It was at least four, plus one
  false lead.
- **Faulty system memory was the biggest one, and it was found last.** The
  board has no ECC, so nothing ever logged a memory error. A locked userspace
  memory test over 104 GiB failed in 13 minutes; an earlier test over 64 GiB
  had passed. A targeted test then pinned the fault to eleven 32 KiB regions
  and logged about 45,000 bad words per one-minute round. The machine reset
  itself during that test with every GPU idle.
- **Fencing the bad memory in software worked.** Taking 10 GiB of memory
  blocks offline at runtime, then re-testing 99 GiB twice, gave zero errors.
- **One GPU, separately, stalls the machine.** Five hard lockups sit in the
  Intel `xe` driver's interrupt handler, always on the CPU that services one
  specific card. With panic-on-lockup off the machine survives them.
- **A CPU idle-state bug caused idle freezes.** Disabling the deepest idle
  state ended them.
- **A debugging setting made things worse.** Panic-on-lockup, with no crash
  capture behind it, turned stalls the machine had survived into silent halts.
- **"The disk dies first" was wrong.** The journal stops minutes before a
  freeze because journald only syncs every five minutes.

If you only do three things on an unstable multi-GPU box: check whether your
memory is ECC, run a memory test that covers nearly all of it, and classify
how every boot ended before theorising.

## The machine

| Part | Detail |
| --- | --- |
| Board, BIOS | Supermicro M12SWA-TF, BIOS 2.4a (2025-07-17, still the newest) |
| CPU | AMD Threadripper PRO 5955WX (16 cores) |
| Memory | 4 x Kingston 32 GB DDR4-3200 **unbuffered, non-ECC**, 1.2 V, slots A1/B1/E1/F1; one module has a different part number |
| GPUs | 4 x Intel Arc Pro B70 (32 GB), PCIe Gen4 x16 each, `xe` driver, GuC firmware 70.44.1 |
| Storage | Samsung 980 PRO 1 TB (root) |
| OS | Ubuntu 24.04, HWE kernel 7.0.0-31, then -34 |

## What we saw, and what each thing turned out to be

| Symptom | Count | Cause | How it was shown |
| --- | --- | --- | --- |
| Machine silently frozen, reset by hand | 25 boots ended by the reset button | Mixed: memory, GPU lockup, idle-state bug, and the panic setting | Boot classification below |
| Machine reset itself | 4 boots (`internal CPU shutdown`) | Memory (one occurred during a CPU-only memory test) | Reset-reason line on the next boot |
| One byte wrong in a 32 MB tensor after loading a 26 GB file; file correct on disk | 2 | Memory | Same byte-lane signature in the memory test |
| Python crash, general protection fault at the identical instruction | 2 | Memory (heap corruption during a large load), inferred | Same-address crash on two boots |
| One wrong output in about a hundred, neighbours exact, never reproduces | 5 runs | Probably memory (data staged through host RAM); not yet shown | Open |
| `watchdog: hard LOCKUP` in `xe_guc_irq_handler` | 5 (3 in September, 2 on 2026-10-03) | One GPU stops answering reads | Kernel trace, IRQ affinity |
| `soft lockup` waiting for other CPUs (`smp_call_function_many_cond`) | 2 boots, 6,603 log lines in one | CPU idle state (C6 class) | Gone after the idle state was disabled |
| `clocksource: Long readout interval` (4 to 72 s) | 7 lines in 5 boots, all unclean | A symptom of the stalls above, not a cause | Follows the lockups |
| `xe` engine faults (`Fault response: Unsuccessful -ENOENT`, CAT error, engine reset) | 5 boots | Driver or card, at process teardown | Not followed closely by freezes (22 to 100 minutes later; two of those boots ended cleanly) |
| Files zero-length or NUL-filled after a freeze | every freeze | Normal: unflushed page cache is lost | See "Why evidence disappears" |
| Journal ends minutes before the freeze | most freezes | Normal: journald's sync interval | See "Why evidence disappears" |

Zero machine-check errors, zero PCIe AER messages, zero NVMe errors and an
empty BMC event log across all of it. On this board that silence means
nothing: there is no ECC to report memory errors, and PCIe errors are handled
by the firmware and never shown to Linux.

## Step 1: classify how every boot ended

Do this before anything else. It turns "it keeps crashing" into counts.

```bash
journalctl --list-boots                                   # first and last timestamp of each boot
journalctl -b -1 -n 20 --no-pager                         # how the previous boot ended
journalctl -b 0 -k | grep 'Previous system reset reason'  # AMD: why the machine reset
```

On AMD the kernel prints the reset cause on the *next* boot:

| Reset reason text | Meaning here |
| --- | --- |
| `system reset pin BP_SYS_RST_L was tripped` | A person pressed reset: the machine had frozen |
| `internal CPU shutdown event occurred` | The CPU shut itself down (triple fault): the kernel's own memory or state was corrupted |
| (clean) journal ends with `systemd-shutdown` lines | Normal shutdown |

Our result: 38 finished boots, 4 clean, 25 reset pin, 4 internal CPU
shutdown, 4 software reset with no shutdown logged, 1 ACPI power transition.

Then search every boot for the signatures that matter, with specific patterns
(generic words such as `hang` or `mce` match unrelated lines):

```bash
for b in $(seq -37 0); do
  journalctl -b $b -k --no-pager 2>/dev/null |
    grep -cE 'hard LOCKUP|soft lockup|Long readout interval|Fault response|CAT error|Hardware Error'
done
```

## Step 2: find out whether your memory can even report errors

```bash
sudo dmidecode -t 16 | grep 'Error Correction'    # None = no ECC
sudo dmidecode -t 17 | grep -E 'Locator:|Size:|Type Detail|Part Number|Speed|Voltage'
ls /sys/devices/system/edac/mc                    # empty = no memory error reporting
```

Ours said `Error Correction Type: None`, `Synchronous Unbuffered
(Unregistered)`, and no `mc0`. System-memory ECC is a property of the memory
modules; it cannot be switched on. This is a different thing from the B70's
own **VRAM** ECC, which is a firmware setting and costs about 4 GB per card:
see [B70 ECC and usable VRAM](b70-ecc-and-vram.md).

With no ECC, "no errors logged" is not evidence of healthy memory. You have
to test.

## Step 3: test nearly all of the memory, locked

```bash
sudo apt-get install memtester
free -g                                   # leave 15 to 20 GiB for the system
for i in 1 2 3 4 5 6 7 8; do sudo memtester 13G 1 > worker-$i.log 2>&1 & done
```

Three details decided the outcome here:

1. **Coverage.** A 64 GiB test (4 x 16 GB) passed on 2026-09-20. The fault
   sits in the top quarter of physical memory and the smaller test never
   touched it. Cover everything you can.
2. **Run it as root.** Without root memtester cannot lock its pages, and you
   cannot map failures to physical addresses afterwards.
3. **Do it with the GPUs idle.** A failure, or a crash, with no GPU process
   running rules out the GPU driver and the workload in one step.

Result on 2026-10-03: two of eight workers failed within 13 minutes, 1,192
mismatches, after the earlier test phases had passed over the same pages.
Every mismatch was in **byte 6 of the 64-bit word** (bits 48 to 55), in runs
of 64 or 128 bytes, and where the pattern was identifiable the bad byte held
the *previous* pattern's value: a write that did not land.

```text
FAILURE: 0x0606060606060606 != 0x0605060606060606 at offset 0x00000001644fde70.
```

One byte position only is the signature of one data lane, which on
unbuffered x8 modules means one memory chip. Multi-bit garbage within one
byte is also why this never looked like a classic single-bit flip.

### Map the failures to physical addresses

memtester prints offsets into its own buffer. While it is still running,
[`tools/memtester-phys-addresses.py`](../tools/memtester-phys-addresses.py)
reads `/proc/<pid>/pagemap` and prints the physical page behind each failing
offset. Ours were 0x1b7ff52000 to 0x1b7ff59fff and 0x1c3fe2a000 to
0x1c3ff50000: both just under a 1 GiB boundary, near 110 and 113 GiB.

## Step 4: localise it with a physical-address-aware test

[`tools/physmap_memtest.py`](../tools/physmap_memtest.py) locks a large
buffer, learns the physical address of every page, hammers chosen regions
and logs each bad word by physical address, fsynced as it goes.

```bash
# fast: the last 8 MiB of every 1 GiB block, plus a control set from the middle of each block
sudo python3 tools/physmap_memtest.py --gib 104 --tail-mib 8 --rounds 12 --out run.jsonl
# full coverage: every locked page
sudo python3 tools/physmap_memtest.py --gib 99 --rounds 2 --all --out all.jsonl
```

| Run | Scope | Result |
| --- | --- | --- |
| 1 | 104 GiB locked, last 4 MiB of 106 blocks + control, 3 rounds (52 s each) | 128 bad words, all in one block's tail; control 0 |
| 2 | Same, last 8 MiB, 5 rounds before the machine reset itself | 226,271 bad words (about 45,000 per round, flat); control 0 |
| 3 | After fencing: 99 GiB, every page (25,952,256 pages), 2 rounds (about 580 s each) | **0** |

Run 2 put every failure in **eleven 32 KiB regions**: six in the 1 GiB block
at 109 GiB (offsets 0x3fa78000, 0x3faa8000, 0x3fb18000, 0x3fbc8000,
0x3fe30000, 0x3fee0000) and five in the block at 112 GiB (0x3fa60000,
0x3fab0000, 0x3fb00000, 0x3fbd0000, 0x3fe28000). Still byte 6 only, in every
cache line of each region, with no interleave pattern at any size from 64
bytes to 64 KiB. Fixed row-sized regions on one byte lane are weak rows in one
chip on one module, not a timing margin and not the CPU. Which slot holds it
is not established: without EDAC there is no address decode, so finding it
means pulling modules and re-running the test (a minute per round, far
quicker than memtest86+).

The error rate is intermittent (8, then 120, then 0 bad words in the three
rounds of run 1) and that is why a short or partial test can pass.

## Step 5: fence bad memory without a reboot

Linux can take whole memory blocks out of service at runtime. It migrates
whatever is in them elsewhere first, and it is reversible.

```bash
cat /sys/devices/system/memory/block_size_bytes      # ours: 80000000 = 2 GiB
# block number = physical address / block size, e.g. 0x1b7ff52000 / 0x80000000 = 54
cat /sys/devices/system/memory/memory54/{state,removable}
for n in 53 54 55 56 57; do
  echo offline | sudo tee /sys/devices/system/memory/memory$n/state
done
grep MemTotal /proc/meminfo                          # ours: 125.6 -> 115.6 GiB
```

We fenced the two affected blocks plus one neighbour on each side and the
block between them: physical 0x1a80000000 to 0x1cffffffff, 10 GiB. Then the
full-coverage test (run 3) found nothing in two rounds.

Limits:

- **It does not survive a reboot.** Every boot starts with the bad memory in
  use until the command is run again. The persistent form is a kernel boot
  parameter that reserves the range, for example `memmap=10G$0x1a80000000`
  (the `$` needs escaping in GRUB); we have not applied or tested that.
- A second write of `offline` to a block that is already offline prints
  `I/O error`. Check `state` instead of trusting the message.
- It only helps when the fault is localised. Re-test everything afterwards.
- It is a workaround. The fix is replacing the module; registered ECC memory
  would also have reported this on day one.

Until bad memory is fenced or replaced, do not install kernels or packages
(a corrupted write of a boot image is a real risk) and do not trust any
measurement from the machine.

## The GPU that stops answering

Three hard lockups (2026-09-14 22:09 and 23:35, 2026-09-20 00:39) have the
same trace:

```text
watchdog: CPU21: Watchdog detected hard LOCKUP on cpu 21
RIP: memcpy_fromio
 g2h_read [xe] <- xe_guc_ct_fast_path <- xe_guc_irq_handler <- dg1_irq_handler
```

The CPU is copying a message out of the card's memory in the interrupt
handler and the read does not complete, so the card had stopped answering.
To see which card a CPU services:

```bash
for d in 23 27 43 47; do
  i=$(ls /sys/bus/pci/devices/0000:$d:00.0/msi_irqs | head -1)
  echo "$d:00.0 irq $i cpu $(cat /proc/irq/$i/effective_affinity_list)"
done
```

CPU 21 services `0000:43:00.0`, which is also the card that logged a memory
CAT error and engine reset on 2026-09-17. The machine survived the first two
lockups after 16 s and 72 s stalls. Whether this is the card, its slot, its
power feed or the driver is open; swapping the card to another slot would
tell. It is a different fault from the memory one.

**Update, 2026-10-03 evening: it recurs on kernel 7.0.0-38, and it is
survivable.** With the bad memory fenced and panic-on-lockup switched off,
the same lockup fired twice in 15 minutes of GPU load (19:38 and 19:53 EDT)
and the machine carried on both times, after stalls of roughly 14 s and 24 s
(`clocksource: Long readout interval ... 24242715672`). The workload saw a
long gap between two clips and nothing else; every clip stayed byte-exact.
On this kernel the stuck instruction is inside `g2h_read` itself and
`xe_guc_pagefault_handler` is on the interrupt stack: the handler is
draining GPU page-fault messages from the firmware in interrupt context and
does not get out. Earlier the same evening, with panic-on-lockup still on,
the machine had frozen silently mid-run; that is what this lockup looks like
when the kernel is told to panic and nothing records the panic. The traces
are in [`data/2026-10-03-xe-guc-hard-lockup/`](../data/2026-10-03-xe-guc-hard-lockup/).

Practical consequences: keep `kernel.hardlockup_panic=0` (it is now 0 in
`/etc/sysctl.d/` on this host); expect an occasional 10 to 70 second stall
under GPU load rather than a freeze; and treat a multi-second gap in a run
as this fault until the journal says otherwise:

```bash
journalctl -k -b 0 | grep -c 'hard LOCKUP'
```

## The idle-state freezes

Two boots died in `soft lockup` storms where one CPU waited forever for
another to answer an inter-processor interrupt, one of them two and a half
minutes after boot with nothing running. That is the long-standing AMD
deep-idle (C6 class) problem. A small systemd unit now disables the deepest
idle state on every CPU after boot:

```bash
for c in /sys/devices/system/cpu/cpu*/cpuidle/state2/disable; do echo 1 | sudo tee $c; done
```

After it went in (2026-09-19) that signature never appeared again and an idle
boot ran for 5.6 days. Freezes under load continued, which is how we knew it
was not the whole story. The cleaner fix is the BIOS setting **Power Supply
Idle Control = Typical Current Idle**.

## A setting that made it worse

`kernel.hardlockup_panic=1` was set to "get a trace". With `kernel.panic=0`
and no working crash capture, a panic simply halts the machine forever. The
lockup the machine had recovered from twice on 09-14 became a permanent
silent freeze on 09-20. Only enable panic-on-lockup when something will
actually catch the panic: a working pstore, kdump, or a network console.

## Why evidence disappears, and the false lead it created

We spent days on "storage fails first": the journal stopped up to five
minutes before each freeze while the workload kept finishing work.

- journald syncs to disk every five minutes by default (`SyncIntervalSec=5m`),
  immediately only for critical messages.
- ext4 writes file data back about 30 seconds late.

So after a freeze the journal is missing its last minutes and recent files
are zero-length or NUL-filled, on a perfectly healthy disk. This also means
a freeze can zero Git objects: recover by moving zero-byte objects aside and
`git fetch`, and push after every result.

What does capture last words:

| Method | Needs | Note |
| --- | --- | --- |
| `netconsole` to another machine | A second host on the LAN | Sends kernel messages from interrupt context; the most robust |
| `journalctl -kf` piped to a file with a `sync` per line | Nothing | Cheap; loses the final moments if userspace stops first |
| pstore / kdump | Configuration and a reboot | Ours was empty: nothing was configured to write to it |
| BMC event log (`ipmitool sel elist`) | A BMC | Ours logged nothing for any freeze |

## Other checks that came back clean (and how to run them)

```bash
sudo lspci -vvv | grep -E '^[0-9a-f]{2}:|LnkSta:|DevSta:|CESta:|UESta:'   # PCIe link and sticky error bits
sudo nvme smart-log /dev/nvme0                                              # media errors, unsafe shutdowns
sudo ipmitool sensor | grep -Ei '12V|5VCC|3.3VCC|Temp'                      # rails and temperatures
```

- **PCIe.** All four cards train at 16 GT/s x16 (they are 32 GT/s cards on a
  Gen4 board; `downgraded` is expected) with no physical-layer errors. Almost
  every device shows `CorrErr+ UnsupReq+` with `AdvNonFatalErr`: that is left
  over from bus enumeration and is harmless. Real link trouble looks like
  `RxErr` or `BadTLP`, which only the NVMe showed.
- **NVMe.** 0 media errors, 4% wear; 38 of 76 power cycles were unsafe
  shutdowns, which is the freeze count showing up on the disk.
- **Power.** 12 V read 11.91 V with the GPUs idle. It has not been logged
  with four cards under load, so the power supply is not cleared.
- **BIOS.** No newer release exists for this board.

## A second machine: GPU faults that came from a container memory limit

Our other host has two B70s, an 8-core EPYC, **15 GiB of ECC memory** and 36 GiB of swap. Its memory
error counters work and read zero, so nothing above applies to it. Its problem looked like a driver
bug and was mostly our own launcher.

**Symptom.** At least five times between September 6 and 19, 2026 a card's copy engine faulted while a model
was loading its weights, never during steady serving:

```
xe 0000:03:00.0: [drm] Tile0: GT0: Fault response: Unsuccessful -EINVAL
xe 0000:03:00.0: [drm] Tile0: GT0: Engine memory CAT error [18]: class=bcs
xe 0000:03:00.0: [drm] Tile0: GT0: Timedout job ... in python3
xe 0000:03:00.0: [drm] Xe device coredump has been created
```

The same signature is reported by other dual-B70 owners in `intel/compute-runtime` issue 948, on
several kernels, driver releases and firmware versions. It is still open.

**What we measured.** A recorder beside a service start showed 4.4 GB swapped out during the
weight load, 4.2 GB of it in one 20-second burst, with 7 GB of host memory free and
`vm.swappiness` at 1. The swapping was not the host's decision. The container was started with
`--memory 12g --memory-swap 16g`; reading 29 GB of weights filled the container's page cache, the
container hit its own 12 GB ceiling about two thousand times, and each time the kernel pushed the
container's working memory out to its 4 GB swap allowance. A cgroup at its limit swaps whatever the
host's swappiness says. Pages the copy engine was reading from host memory could be swapped out
from under it.

**The fix** is one argument: give the container no swap, so reclaim drops clean file pages instead.

```
docker run --memory 12g --memory-swap 12g ...     # equal values = memory.swap.max 0
cat /sys/fs/cgroup/system.slice/docker-<id>.scope/memory.swap.peak    # should read 0
cat /sys/fs/cgroup/system.slice/docker-<id>.scope/memory.events       # oom_kill should read 0
```

The same mistake had already cost us the desktop session once: a 4 GiB `MemoryMax` "tripwire" around
a 27 GB model load made the cgroup thrash until `systemd-oomd` killed the user's session. **A memory
cap below what a job really touches is not a safety net; it is a source of memory pressure.**

**What happened after the fix** (lab-measured, 2026-09-19 to 2026-10-03).

| Starts of the two-card service | Kernel | Faults |
|---|---|---:|
| 3 validation starts, container swap-out 0 each | 7.0.0-31 | 0 |
| 10 start/stop cycles, first GPU work on the boot | 7.0.0-31 | 0 |
| 3 more on the same boot, after nine video-model runs | 7.0.0-31 | 0 |
| 10 start/stop cycles, first GPU work after the reboot | 7.0.0-38 | 0 |
| 33 research-server starts on that same boot, overnight | 7.0.0-38 | **1** (the last) |

Every start reproduced the reference outputs exactly (12 of 12 prompts) at about 90 tokens a second.
The runner is `scripts/fp8-start-cycle-soak.sh`; the numbers are in
[the kernel soak record](../experiments/qwen38-27b-b70/data/2026-10-03-kernel-soak/README.md).

**What this does and does not show.** The fix made the fault rare. It did not end it. After 58 clean starts,
the 59th faulted the same way on 2026-10-04: copy engine, the second the weights finished loading, with the
container unable to swap and 5 GiB of host memory free. That start was the 43rd on one ten-hour boot, and a
killed job had already faulted the same card earlier on that boot; we do not know whether either matters. One
in 59, against five in four days before, says container swap was the main cause and not the only one. We
also never switched the swap allowance back on to watch the fault rate return.
[Incident record](../experiments/qwen38-27b-b70/notes/2026-10-04-gpu-fault-mtp-start.md).

Two other triggers on this host are separate and still stand: a direct card-to-card copy
faulted both cards (staging the transfer through host memory avoids it), and **killing a busy GPU job
logs the same fault lines by itself**. Our one freeze on September 21 came ten minutes into a rerun
that was started 90 seconds after such a kill; after any fault line we now stop, save the evidence, and
do no more GPU work on that boot until a health check passes cleanly.

**Two guards worth copying on a small-memory host.** `earlyoom`, set to act on available memory
alone (with tens of GB of swap its default never triggers) and to prefer the model-loading process
over the desktop; and a watchdog around each job that kills that job, not the session, when
available memory falls below a floor.

## Kernel and firmware notes (as of 2026-10-03)

- Ubuntu 7.0.0-34 is security-only: no `xe`, DRM, AMD or idle changes against
  -31. A newer number is not automatically a GPU fix.
- 7.0.0-38 does **not** fix the interrupt lockup described above (two
  occurrences on its first evening).
- 7.0.0-38 (noble-updates) carries a fix for a deadlock at GPU exec-queue
  teardown, two `xe` page-table bind fixes and an AMD IOMMU locking fix.
  7.0.0-39 (proposed) stops the driver handing out video memory that the
  compression hardware owns, a bug that corrupted GPU page tables on B580 and
  B570 cards; whether the B70 is affected is unconfirmed.
- The driver recommends GuC firmware 70.54.0 for these cards; the Ubuntu
  package ships 70.44.1, two Intel bug-fix releases behind.
- `unattended-upgrades` installs and removes kernels on its own. It replaced
  our fallback kernel during the gap. Record the kernel in every run identity
  and decide deliberately whether automatic kernel upgrades stay on.
- On the two-card host, 7.0.0-31 and 7.0.0-38 scored the same on ten service start/stop cycles
  each (zero faults, same speed). A tip that "kernel 7 fixed it" did not apply: that host was already
  on 7.0 for every fault it had.
- We found no public report of a kernel version curing B70 freezes; two open
  upstream issues describe the same engine-fault signature on dual-card
  machines.

## Rules we now follow

1. Classify boot endings and count signatures before forming a theory.
2. On a board without ECC, test nearly all memory, locked, before blaming
   software. Re-test after any hardware change.
3. A crash or a corruption with the GPUs idle clears the GPU stack for that
   event.
4. One byte wrong in a large copy, a crash at the same instruction twice, or
   one bad result among exact neighbours are memory symptoms until shown
   otherwise.
5. Do not read meaning into where the journal stops.
6. Do not enable panic-on-lockup without a way to capture the panic.
7. Change one thing per boot. A kernel swap and a firmware swap on the same
   boot told us nothing about either.
8. No installs and no promoted measurements while known-bad memory is in use.

## Not established

- Which memory slot holds the faulty module.
- Whether the one-wrong-result-per-hundred symptom is the memory fault.
- Whether the `0000:43:00.0` lockups follow the card, the slot or the power.
- Whether kernel 7.0.0-38/-39 or GuC 70.54.0 change the engine faults.
- 12 V behaviour with all four cards loaded.

## Evidence

- [Raw memory-test logs and summaries](../data/2026-10-03-host-memory-fault/README.md)
- [Host forensic review, 2026-10-03](../experiments/ltx25-b70/notes/2026-10-03-host-forensics-and-catch-up.md)
- [Freeze evidence, 2026-09-19](../experiments/ltx25-b70/notes/2026-09-19-freeze-evidence-soft-lockup.md) (its "driver excluded" and "storage first" conclusions are corrected above)
- [Userspace memory test that passed, 2026-09-20](../experiments/ltx25-b70/notes/2026-09-20-memtester-result.md)
- [Firmware and kernel review, 2026-09-17](../experiments/ltx25-b70/notes/2026-09-17-firmware-and-kernel-review.md)
