# Two identical `xe` GuC hard lockups on CPU21; not caused by graph capture

September15, 2026, boot `64bbd5d2` (the user's reboot). The kernel watchdog
recorded **two hard lockups this boot**, both with the same signature:

```
watchdog: CPU21: Watchdog detected hard LOCKUP on cpu 21
CPU: 21 UID: 0 PID: 0 Comm: swapper/21
RIP: 0010:memcpy_fromio+0x7d/0xd0
  g2h_read+0x42a/0x4b0 [xe]
  xe_guc_ct_fast_path+0x78/0x1b0 [xe]
  xe_guc_irq_handler+0x9e/0xb0 [xe]
  gt_irq_handler / dg1_irq_handler / __common_interrupt
```

The CPU is in the **idle task** (`swapper/21`), taking a GPU interrupt, and
hangs reading GuC-to-host mailbox memory over MMIO. Both times the host
recovered on its own.

| When (UTC) | What was running |
| --- | --- |
| 02:09:20 | packet13 control clips: **ordinary eager generation, no graph capture** |
| 03:35:49 | packet20 graph arm, between clips r04 and r05 |

**The first lockup predates the graph-capture work entirely** -- packet14, the
first packet containing any capture code, was not built until 02:30. The
signature is byte-for-byte the same in both. This is a host/driver instability
in `xe`'s GuC message path, not a property of the workload, and it is
consistent with this host's recorded history of silent freezes.

## Why only the second one latched a fault

The launcher's fault watcher matches `Fault response|CAT error|engine reset|
GPU HANG|GuC.*reset|coredump`, a `BUG: soft lockup` form, and RCU stall forms.
It does **not** match `watchdog: ... hard LOCKUP`. The 02:09 event produced only
the lockup line and went undetected; the 03:35 event also produced
`rcu: INFO: rcu_preempt detected stalls on CPUs/tasks`, which the RCU pattern
caught. So the detector saw one of two identical events. Any successor launcher
should add `watchdog:.*hard LOCKUP` to the pattern.

## State after the incident

`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/FAULT.json` is latched, so
the frozen client refuses further requests, which is the intended behaviour. The
server process stayed alive and healthy, all four render devices are present,
load average is normal, and **the clip generated immediately before the fault
(gc20-r04-graph) completed and matched its reference bytewise on all four raw
outputs**. No agent reboot, driver reset, GPU reset or power/memory setting
change was made, and none is proposed here.

## Effect on the campaign

Packet20's only change from the qualified packet19 is a performance refactor:
one shared static buffer set per device instead of per block, a per-forward
argument signature instead of per block, and full registration validation once
per forward instead of per block call. Its single completed graph clip
(`gc20-r04-graph`) read **1.924 s** of sampler against packet19's 2.001 s
median, but **one clip is not a result** and the arm is incomplete. Packet19's
1.83x remains the qualified figure.

Evidence: [`data/xe-lockup-incident-01/`](../data/xe-lockup-incident-01/) holds
both kernel traces, the combined extract and the fault latch.
