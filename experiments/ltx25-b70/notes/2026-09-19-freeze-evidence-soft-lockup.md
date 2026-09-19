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
