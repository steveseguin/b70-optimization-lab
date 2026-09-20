# Freeze 2026-09-20 ~10:17 EDT (boot 5486d35a): second freeze under packet 87

## What happened

Boot `5486d35a` (09:53:51 EDT) ran one encoder server (packet 87, pid 6941,
launched 10:13) and the f87 campaign from 10:14:42. The kernel journal's last
signs: `clocksource: Long readout interval, skipping watchdog check` at
10:16:52 (a >14 s stall), journal flush ending 10:17:01. Validation mtimes
show the GPU pipeline kept completing clips until **10:19:20** — so the
userspace/storage side hung first while compute continued ~2 min longer.
User rebooted; current boot `dff7cf53` 11:29. pstore empty again.

## Yield before the freeze

- Warm: 3/3 exact.
- Endure: **84 of 120 clips complete, zero mismatches** — the wrong-clip bug
  did not fire.
- All packet-87 fingerprint data was **lost**: `record_fingerprint` stores
  in a 512-entry in-memory dict on the server (`ltx_pipeline.py:52-57`); the
  freeze killed the process. No latent/noise fingerprints persisted.

## Attribution update

Freezes by packet on this codebase state:

| Packet | Campaigns | Freezes |
| --- | --- | --- |
| 84 (events only) | 1 full | 0 |
| 85 | 1 launch + warm | 0 |
| 86 (events + cond/output fps) | 1 full (incl. wrong clip caught) | 0 |
| 87 (adds in-pipeline D2H fps of ~10 tensors/clip) | 2 attempts | **2** |

Both 87 freezes hit ~70–130 s into the campaign — the window where the new
blocking `tensor.cpu()` strided reads on the sampler worker streams first
run against in-flight graph replays. Correlation is now strong enough to act
on: the in-pipeline D2H fingerprinting is the prime suspect (mechanism:
forcing the xe driver to synchronize copy-engine reads against concurrent
graph replays on four cards).

C6 was disabled on this boot too. Two freezes with C6 off further weakens
C6-as-cause; the driver-stress-under-instrumentation hypothesis now leads.

## Action (pre-committed in the 00:39 note)

Packet 88: revert the sampler-node instrumentation to the packet-86 set
(events + conditioning/seed/output fingerprints — proven stable across 84/85/86
campaigns). The wrong-clip root-cause hunt continues by **offline replay**:
when the bug fires under 88, its inputs are already fully fingerprinted in the
receipts; replaying the exact clip on the quiesced server afterwards can use
arbitrarily heavy instrumentation because nothing else is in flight.
