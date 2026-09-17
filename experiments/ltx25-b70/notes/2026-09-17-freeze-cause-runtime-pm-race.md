# The silent freezes: two B70s were runtime-suspending because the keep-awake policy races the xe probe

*2026-09-17 05:41–05:55 UTC, after the sixth silent lockup in two days (05:17
UTC, one minute after packet 67's campaign finished with the server idle).*

## Timeline of the lockups

| When (UTC) | Host state at the freeze |
| --- | --- |
| 09-14 19:36 | ~25 s after a sealed-server teardown |
| 09-16 13:55 | ~90 s after a clip batch finished, server idle |
| 09-16 17:20 | during a server start (packet 56) |
| 09-17 00:10 | 43 min after a GPU fault, halted process idle |
| 09-17 03:14 | mid-campaign (packet 62), between arms' prompts |
| 09-17 03:40 | idle boot, 13 min after boot, nothing running |
| 09-17 03:48 | idle boot, 5 min after boot, nothing running |
| 09-17 05:17 | 1 min after a campaign completed, server idle |

Every one is at or shortly after a transition to idle GPUs, and two happened
with no GPU process at all. No kernel line precedes any of them.

## What the host looks like on a fresh boot

`/sys/class/drm/card*/device/power` on this boot, before any GPU work:

| PCI | render node | `power/control` | `runtime_status` | suspended |
| --- | --- | --- | --- | ---: |
| 0000:43:00.0 | renderD128 | on | active | 0 s |
| 0000:47:00.0 | renderD129 | on | active | 0 s |
| **0000:23:00.0** | renderD130 | **auto** | **suspended** | 545 s of 553 |
| **0000:27:00.0** | renderD131 | **auto** | **suspended** | 544 s of 553 |

Two of the four B70s runtime-suspend into D3 whenever they are idle for one
second (`autosuspend_delay_ms=1000`). The card that page-faulted on 09-16
(`0000:27:00.0`) is one of them. The September 1 note
(`experiments/qwen38-flash-next-fp8-b70/notes/2026-09-01-b70-idle-d3cold-recovery.md`)
already recorded this platform failing to wake B70s from idle D3cold, and
the repository's answer was the boot-time unit
`b70-runtime-performance-policy.service`, which sets every B70 endpoint and
bridge path to `power/control=on`.

## Why the policy only covered two cards

The unit's own log this boot, against the kernel's probe timestamps:

| | time |
| --- | --- |
| policy writes `on` to 0000:23:00.0 | 01:33:54.44 EDT |
| xe finishes probing 0000:23:00.0 | 01:33:54.98 EDT |
| policy writes `on` to 0000:27:00.0 | 01:33:54.46 EDT |
| xe finishes probing 0000:27:00.0 | 01:33:55.39 EDT |

The xe probe installs runtime autosuspend on the device it is bringing up,
so the two cards that probed *after* the unit ran had their `on` overwritten
with `auto`. The two that probed before it kept `on`. The unit is ordered
after `systemd-udev-trigger.service`, which only guarantees the events were
queued, not that the driver finished. The policy the user approved has been
silently half-applied on every boot since it was installed.

## Fix

1. Immediately: write `on` to the two endpoints (reversible; identical to
   what the unit intends).
2. Durably: `/etc/udev/rules.d/60-b70-runtime-pm-on.rules` applies
   `power/control=on` on the PCI `bind` event for vendor 8086 device e223,
   which fires after the driver's probe, so it cannot be raced. A copy is
   kept at `systemd/60-b70-runtime-pm-on.rules`.
3. The sealed launcher's preflight will refuse to start while any B70
   endpoint reports `power/control` other than `on`, so a future regression
   is caught before work instead of after a lockup.

Applied 2026-09-17 05:57 UTC: all four endpoints report `control=on status=active`, the udev rule is installed and udev reloaded. GPU work resumed with packet 69.

Nothing here changes model arithmetic. It raises idle platform power. It is
a hypothesis with strong circumstantial support, not a proof; the test is
whether the host stays up through idle periods and transitions from here.
