# PCIe/NVMe corrected-error quarantine reassessment

Date: 2026-08-03 America/Toronto

Status: **read-only reassessment. Nothing was written to `/sys` or `/proc`, no
elevation was used, no device was touched, and no model, service, endpoint, or
XPU probe was run. This note does NOT lift the quarantine — that remains a human
decision and one material piece of evidence is still missing.**

## Why this was reopened

The quarantine has been the top blocker on the board since 2026-08-02, forbidding
every model load, benchmark, XPU probe, reset, and recovery action. Production
planning made its basis worth establishing precisely rather than inheriting.

## Finding: the corrected errors are exclusively on the boot NVMe link

A full sweep of every PCI device exposing AER statistics found exactly two
nonzero devices. This was captured independently twice — once by the
investigating agent, and once by the coordinator from a snapshot taken *before*
that agent began, specifically so the result could be corroborated rather than
trusted.

| device | identity | `TOTAL_ERR_COR` |
| :--- | :--- | ---: |
| `0000:01:00.0` | Samsung NVMe, vendor `0x144d`, class `0x010802`, driver `nvme` | 13 |
| `0000:00:03.1` | that NVMe's PCIe root port | 2 |
| `0000:23:00.0`, `0000:27:00.0`, `0000:43:00.0`, `0000:47:00.0` | the four B70 GPUs, vendor `0x8086` device `0xe223`, driver `xe` | **0** |
| every other device, including the full GPU switch fabric | — | 0 |

`TOTAL_ERR_NONFATAL` and `TOTAL_ERR_FATAL` are zero everywhere in the machine.

The kernel journal agrees independently. Filtering the current boot's AER records
by PCI address yields 26 mentions of `0000:01:00.0` and 4 of `0000:00:03.1`, and
**no GPU address appears at all** — not `0000:23:00.0`, `0000:27:00.0`,
`0000:43:00.0`, or `0000:47:00.0`. Two independent mechanisms, the cumulative
sysfs counters and the per-event journal, attribute every error to the same
device.

**The GPU half of the quarantine has no supporting device evidence.** Every
corrected event in the retained record is on the root-filesystem NVMe link or its
own root port. Not one is on a GPU, a GPU switch port, or anything else.

## Finding: the rate is not climbing

`kernel.dmesg_restrict=1`, but the user is in the `adm` group and the journal is
persistent, giving 14 boots and 205.8 hours of retained history: **490 corrected
events, 2.38/hour average**, ~99% attributed to `nvme 0000:01:00.0`.

Peaks sit in the middle of the window, not at the end. The maximum (5.19/hour)
coincides exactly with the 5.4-hour long-context sweep that ran a temporary
16 GiB swap file on this same NVMe. The current boot sits in the bottom quartile
at 0.66/hour, 15 minutes of idle sampling produced no new events, and the
coordinator independently observed the cumulative total unchanged at 15 across a
further 40 minutes. The variance is load-driven, not calendar-driven.

The error signature supports the same reading. The endpoint logs `RxErr`
(physical-layer receiver errors) with `BadTLP`, `BadDLLP`, and `Rollover` all
zero, and only 2 replay-timer timeouts across 490 events. A degrading link
escalates receiver errors into CRC failures and replay storms; this one does not.
No link is downtrained: the NVMe runs Gen4 x4 at spec, and all four GPU host
links run Gen4 x16, the platform maximum.

Most directly: `/sys/fs/ext4/nvme0n1p2/errors_count`, `first_error_time`, and
`last_error_time` are all **0**. Those live in the ext4 superblock and persist
for the life of the filesystem. Despite ~490 corrected PCIe events, the
filesystem holding the model weights has never recorded an error.

## Finding: the gate that declared the quarantine cannot pass on this host

`2026-08-02-exact-small-swap24-preregistration.md` fails a run on **any** matching
PCIe/AER *corrected* event over its window. Against a measured background of
0.15--5.2 corrected events per hour present continuously across the entire
retained journal, no run of meaningful duration can satisfy that gate regardless
of hardware health.

The quarantine is therefore self-perpetuating by construction. Unless the gate
becomes a rate threshold — failing on any *uncorrectable* event, or on corrected
events above roughly 6/hour, which exceeds every value in the 8-day record — it
will re-declare itself after the next run and block the next window too.

The original observation was accurate as far as it went. The three events it
recorded are real and are included in the 13 now on the counter. What it could
not see, because it only ever read bounded journal windows and never the
cumulative counter, was the scale (490, not 3) or the trend.

## Independent risk found while investigating: the root filesystem

`/mnt/fast-ai` — where the notes place the model weights, all run artifacts, and
bench results — **is not a mountpoint**. Those 585 GiB sit directly on the root
ext4 filesystem, alongside `/swap.img`, on a 930 GiB device that is **92% full
with 71 GiB free**. Meanwhile a 3.6 TiB drive (`sda2`, NTFS) is not mounted and
appears nowhere in `/etc/fstab`.

This is the same NVMe generating the corrected errors and the same one whose swap
exhaustion already killed a run. For a service that writes artifacts
continuously, this will cause an outage before the AER counters will, and it is
fixable without any authorization.

## Assessment and the one missing piece

The evidence supports a marginal-but-functional PCIe receiver on the NVMe link,
load-modulated, stable across eight days, causing no data-path harm. It does not
support a failing device, and it categorically does not implicate the GPUs.

What it cannot exclude is degradation slower than the journal's eight-day
retention. What is genuinely unknown is **NVMe controller-internal health** —
media errors, wear, unsafe shutdowns, thermals. `nvme-cli` and `smartctl` are not
installed, so no SMART data exists. That is the only material gap.

Two commands close it, and they need a human:

```
sudo apt-get install -y nvme-cli
sudo nvme smart-log /dev/nvme0
```

Decision rule: `critical_warning` nonzero, `media_errors` nonzero, or
`percentage_used` near end-of-life means replace the drive and ship nothing. All
clean means the corrected errors are link-side only.

**Never write to an AER counter file.** Any write zeroes it, destroying the
accumulated count and the only cheap trend baseline that exists. The same applies
to `setpci` on the AER status register, and no NVMe or PCIe reset should be
issued against a device hosting the mounted root filesystem.

A zero-cost permanent improvement, needing no elevation: record
`/sys/bus/pci/devices/0000:01:00.0/aer_dev_correctable` with a timestamp once a
day. Against the 490-event baseline that turns the ship decision into a monitored
quantity.

## What this note does and does not authorize

It authorizes nothing. It records evidence and an assessment. Lifting any part of
the quarantine, running the SMART commands, and any subsequent device window all
require explicit human authorization, consistent with the campaign rule that no
escalation follows from a diagnostic whose result has not been proven.

The protected `125.4619731637751 tok/s` conventional short-decode record is
untouched.
