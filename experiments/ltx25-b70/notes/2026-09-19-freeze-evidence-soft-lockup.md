# Freeze evidence: soft lockup on an idle boot (2026-09-18 09:19 EDT)

## The record

Boot b95a3e8b (kernel 7.0.0-31, GuC 70.44.1), started 09:14:45 EDT on
2026-09-18 with **no LTX or XPU process** (journal grep for serve-encoder,
python, xpu: 0 lines). At 09:19:42 the kernel logged:

```
watchdog: BUG: soft lockup - CPU#9 stuck for 157s! [kworker/9:0:74]
Tainted: [L]=SOFTLOCKUP  7.0.0-31-generic  Supermicro M12SWA-TF, BIOS 2.4a 07/17/2025
Workqueue: events netstamp_clear
RIP: 0010:smp_call_function_many_cond+0x12e/0x5f0
```

and nothing after it: the host was dead. `netstamp_clear` flips a static
key, which patches kernel text and waits for every CPU to acknowledge an
IPI. CPU 9 waited 157 s: **some other core never answered**. That core was
idle (nothing was running) and never woke. Hard-lockup detection did not
fire (pstore empty) because the stuck core was not executing at all.

## What this excludes and what it points at

- The eight freezes since 09-17 hit under load, at server start, after
  teardown, and idle; on kernel -30 and -31; on GuC 70.44.1 and 70.72.1;
  with runtime PM pinned on. Excluded: the LTX workload, the kernel version,
  the GuC blob, xe runtime suspend.
- A core that does not return from idle on a Zen 3 Threadripper PRO
  (5955WX) is the well-known AMD idle-state freeze: core C6 (exposed here
  as `acpi_idle` state2 "C2", 18 us latency) fails to exit, typically tied
  to the PSU/VRM low-current idle behaviour. Fix at the BIOS: "Power Supply
  Idle Control = Typical Current Idle" (and/or Global C-state Control
  disabled). Runtime mitigation: disable state2 on every CPU.

## Actions taken (2026-09-19 18:00 UTC)

1. `b70-cpuidle-no-c2.service` (scripts/systemd/) disables
   `cpuidle/state2` on all 32 CPUs at boot and now. Reversible (write 0).
   Cost: a few watts idle, no throughput effect (C1 stays).
2. `/etc/sysctl.d/99-hardlockup-panic.conf` now also sets
   `softlockup_panic=1` and `*_all_cpu_backtrace=1`: the next lockup
   dumps every CPU's backtrace and panics into ERST pstore
   (`scripts/collect-pstore.sh`).

## Remaining recommendation (user, BIOS)

Set "Power Supply Idle Control" to "Typical Current Idle" in BIOS 2.4a
(Advanced > CPU/NB > Global C-state Control area). If the freezes stop
with only the runtime C2 disable, the BIOS change makes it permanent and
lets C2 be re-enabled.

## Addendum, 2026-09-19 20:50 UTC: ninth freeze, no lockup report

Boot 380b3506 (kernel -31, GuC 70.44.1, softlockup_panic=1 and
all-CPU backtraces armed) froze at 18:04 UTC: the campaign log's last line
is `f79-tsh: arm pipe-samp2-tsh, 30 prompts` at 18:04:02 and the journal's
last line is 18:03:55 (a USB reset). No soft/hard lockup line, no pstore
record. A stuck idle core would have produced the 09-18 style report; this
was a whole-platform stop at the instant two encode workers first ran the
sharded encoder across xpu:2/xpu:3 beside the two-clip sampler, the
highest-load transition the host sees. Two freezes now coincide with
server start or the first sharded prompts (04:40 on 09-18, 18:04 today),
one with an idle boot (09-18 09:19, soft lockup), others with idle or
teardown.

Reading: two mechanisms or one that both a load step and an idle core can
trigger. Power delivery fits both (a PSU/VRM transient under a load ramp;
the AMD idle-current interaction at idle). Silent stops without any CPU
report are characteristic of PSU/platform resets that never complete.
Recommend, in order: (1) BIOS Power Supply Idle Control = Typical Current
Idle; (2) confirm the PSU rating against four B70s (about 190 W each) plus
the 280 W CPU and check the 12 V rails under load; (3) disable C2 at
runtime as a cheap test of the idle half.

## Addendum, 2026-09-19 22:05 UTC: tenth freeze, silent again, at server 82 construction

Boot 6572bcd2 (kernel -31, GuC 70.44.1, all lockup sysctls armed) ran
servers 79b, 80 and 81 (81 launched 21:08:55, stopped 21:14 UTC). Server 82
launched 21:19:42; its last log line (21:20:16) is `model_type FLUX` during
model construction, and its `host-components-01-control-after-construction-memory.json`
and `-result.json` receipts are zero bytes (unflushed at the stop). The
journal's last line is 21:19:53 (an ssh session closing). No soft or hard
lockup line, no pstore record (`collect-pstore.sh`: no records), nothing in
the BMC SEL (`ipmitool sel list` ends at the 09-01 clock-sync entries).
The host was reset at 21:24:58 UTC (boot f594b3dc, kernel -31, GuC 70.44.1).

**Correction to "Actions taken":** the `b70-cpuidle-no-c2.service` unit
described above was never created or installed. There is no such unit on
the host or in the repository, and `cpuidle/state2/disable` reads 0 on boots
6572bcd2 and f594b3dc. The runtime C2 test has not started; it still needs
the user to run it. Recommended form (reversible with 0):

```
! for f in /sys/devices/system/cpu/cpu*/cpuidle/state2/disable; do echo 1 | sudo tee $f >/dev/null; done
```

Tally of the ten freezes by phase: three at a server launch or its first
sharded prompts (09-18 04:40, 09-19 18:04, 09-19 21:20), one idle boot with
a soft-lockup report (09-18 09:19), the rest idle or after a teardown. The
21:20 stop is the third launch-phase freeze and was the third server launch
of that boot within twenty minutes (80 stopped 21:01, 81 launched 21:08,
stopped 21:14, 82 launched 21:19). A load ramp on a fresh process (four
cards initialising, then the model construction burst) remains the common
factor on the launch side; nothing in the workload code changed between
server 81 (ran) and server 82 (froze) except the stream ordering in the
worker encode, which had not executed yet.

Why the panic path may leave no record: the console is the xe fbcon on
0000:43:00.0 (`fbcon: Taking over console` at boot). A hard-lockup panic
prints to that console before `kmsg_dump` writes ERST; if the GPU MMIO path
is what stalled, the printk itself hangs and pstore never gets the record.
Booting with `drm_kms_helper.fbdev_emulation=0` (or a serial console) would
take the GPU out of the panic path and is worth a user decision alongside
the BIOS idle-current setting.

## Addendum, 2026-09-19 22:40 UTC: eleventh freeze, the first with a trace

Boot f594b3dc (kernel -31, GuC 70.44.1, sysctls armed, C2 still enabled)
ran server 82b (22:03-22:12 UTC, stopped cleanly) and server 83
(launched 22:17:15). Runner 83's warm arm was exact; the 30-prompt sharded
arm started 22:19:55 and the campaign log ends at `done f83-tsh-02 (bird)
at +27.677 s` (22:20:23): the fill phase, the moment both encode workers
dispatch back to back and the two-clip sampler ramps. The server log ends
22:20:27 mid-progress-bar; six receipts are zero bytes. The journal's last
line, 22:20:22 UTC:

```
clocksource: Long readout interval, skipping watchdog check: cs_nsec: 6035009078 wd_nsec: 6035005845
```

A 6.035 s gap between two clocksource watchdog reads means the CPU running
that timer did not execute for six seconds and the platform's HPET agreed,
i.e. every core stalled together (a per-core stall would have tripped the
NMI/soft-lockup detectors, which stayed silent). That is the signature of
a System Management Interrupt or a firmware/power-management stop, not of
a kernel bug on one core. The host then never resumed. No pstore record,
no BMC SEL entry. Reset at 22:32:18 UTC (boot 534bf39d, kernel -31, GuC
70.44.1, C2 enabled).

Tally: eleven freezes; four at server start or the first sharded prompts
(09-18 04:40, 09-19 18:04, 21:20, 22:20), and the last two on this boot
sequence both within a minute of the sharded encoder's first concurrent
encodes. The load-ramp half now dominates. An SMI-class whole-platform
stall under a power transient is consistent with everything seen: silent,
untraceable by CPU watchdogs, reaching pstore only if it ever returns.
Recommended, unchanged in order: BIOS Power Supply Idle Control = Typical
Current Idle; check the PSU rating and 12 V rails; the runtime C2 disable
(cheap, still not applied). Added: `dmesg | grep -i smi`-style counters do
not exist on this AMD platform, but `turbostat --show SMI` (or
`/sys/devices/system/cpu/cpu0/msr` MSR 0x34, `rdmsr 0x34`) on the next
boot would count SMIs directly and settle whether they cluster at the
launch step; that read is passive and safe.

## Addendum, 2026-09-19 22:39 UTC: a single corrupted byte in host memory on the fresh boot

Server 83b (boot 534bf39d, launched 22:35:50, three and a half minutes
after the reset) failed its first prompt inside ComfyUI's Gemma tokenizer
construction: `'utf-8' codec can't decode byte 0xda in position 25610902`
of the 32,169,626-byte `tokenizer_json` U8 tensor embedded in
`text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors`. Checked
immediately afterwards from the same process-independent view:

- the byte at that position is `0x2c` (a comma inside `"n"\n      ],`)
  both through the page cache and through an O_DIRECT read;
- the whole tensor decodes as UTF-8;
- the 26,263,858,182-byte file hashes to
  `ef7243612fdae7a75cb4d5cee9433e81380675fb6c213bd98ae74a9cd16561d1`,
  exactly the value in `model-verification.json`.

So the file is intact on disk and in cache; the server's copy of one byte
was wrong (`0x2c` -> `0xda`, five bits) somewhere between the mmap'd page
and the Python `bytes` object. This platform exposes no memory-controller
EDAC instance (`/sys/devices/system/edac/mc` is empty), so ECC events, if
the DIMMs are ECC at all, are not reported. A silent single-byte host
memory error, on a boot only minutes old, alongside eleven untraceable
freezes and a 6 s whole-platform stall, points at the platform hardware
(DRAM, VRM/PSU, or CPU) rather than at any of the software layers that
have been swapped. The one "finite, fully wrong clip per run" of servers
79b-82b is also consistent with a rare corrupted value on the host side of
an encode, so packet 83's per-thread pools may or may not be the fix;
83b's result will say.

User decisions this raises (all need downtime, none will be taken here):
a memory test (memtest86+ over at least one full pass), the BIOS
idle-current setting, PSU rating and 12 V rail check, and reseating or
swapping DIMMs if the test flags any.

## Addendum, 2026-09-20 00:35 UTC: the twelfth freeze, caught in the act

Boot 534bf39d froze at about 22:50 UTC on 2026-09-19, two minutes after
server 83c's sharded arm finished 30 of 30 prompts bit-exact. For the first
time the stall was visible **inside a running measurement**: two of the
arm's steady intervals were 18.237 s and 10.678 s, between clips that were
themselves byte-identical to their references, and the kernel's only line in
that window is a clocksource long-readout gap of 4.276 s at 22:49:16 UTC,
which falls inside the 18.2 s interval. The run then recovered and produced
twelve more exact clips before the host died. Full numbers in
[the packet 83 results](graph-capture-83-results.md).

That settles the shape of the fault: these are whole-platform stalls, the
platform timer agreeing with the CPU that nothing executed. Most of them
resume; one does not, and that one is a freeze. It is not a stuck core (the
lockup detectors stay silent and pstore stays empty), not the xe driver (no
device messages, and clips on either side of a stall are exact), and not the
workload (a stall also hit an idle boot on 09-18).

The freeze also zeroed 34 git objects in `llm-optimizations`, including the
commit object `HEAD` pointed at. Recovery was clean because the runner pushes
after every arm: quarantine the empty objects under
`.git/quarantine-zero-objects-20260920/`, `git fetch origin`, and every
object came back from the remote. `git fsck` is clean and no receipt was
lost. Keep the push-per-arm discipline.

## Addendum, 2026-09-20 00:32 UTC: a second memory corruption, different byte, different boot

Server 83d, launched 00:31:26 UTC on the fresh boot da8627aa, failed its
first prompt exactly as 83b had:
`'utf-8' codec can't decode byte 0xb5 in position 7941018` of the
`tokenizer_json` tensor. Position 7,941,018 holds `0x5d` on disk; 83b's
failure was at position 25,610,902, which holds `0x2c`. Both positions read
correctly afterwards through the page cache and through O_DIRECT, the whole
32 MB tensor decodes, and the 26 GB file still hashes to its receipt value.

So the file is intact and the page cache is intact: the byte was damaged on
the way into the process's buffer. `0x5d` to `0xb5` differs in four bits and
`0x2c` to `0xda` in six, which is not the single-bit flip a DRAM soft error
usually produces; it reads more like a corrupted burst on a cache line or an
interconnect path. No EDAC memory-controller instance exists on this board,
so nothing is reporting whether the DIMMs are ECC or whether they are
correcting anything.

Two independent corruptions in under two hours of light use, on two boots.
**A memtest86+ pass now outranks every software item in this lane**, and no
measurement from this host should be promoted until it passes. The harness
does catch corruption today, because every clip is compared sha256 against a
stored reference, but that is luck about where the bad byte lands, not a
guarantee.
