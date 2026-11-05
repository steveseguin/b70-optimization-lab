# Persistent SC117 hosting and Pi experience

Owner requested removal of the shutdown timer, then asked for ongoing testing
and improvement of Pi coding-agent responsiveness, thinking, errors and context
management. The remote Pi version/configuration was unavailable; proceed with
the repository's pinned Pi 1.2.0 and preserve that limitation.

## Changes under qualification

- Hosted lifetime is zero (unlimited) in service, adapter and native engine.
  Finite experiment lifetimes remain available. Startup, partial IPC transfers,
  GPU operations, cancellation, peer failure and fault monitoring remain bounded.
  Native command reception can idle indefinitely before its first byte.
- Persistent hosting discards the process-long p92 timing stream and disables
  per-request detailed timing archives in RAM. Bounded request summaries remain.
- Plain answer text streams while tools are advertised. Partial tool markup is
  withheld until the canonical tool parser has the complete call.
- Unknown model IDs are rejected before inference. Previously the disabled
  keeper ID silently selected the plain model.
- Dedicated four-card Pi profile: true 131072 context, 8192 output budget,
  visible medium thinking with explicit effort mapping, client compaction on.
  Profiles are available from `/client-config/pi/models.json` and
  `/client-config/pi/settings.json` on the LAN endpoint.
- Live continuation is requested, but enabled only after the exact startup
  gate passes. The gate now crosses the 512-row ring and actually uses two
  batched prefill chunks; its old 72-token suffix did neither at chunk size256.
  Session parking and ctxkeeper remain off while qualifying this plain path.

## Why the previous experience could be poor

The hosted arm explicitly disabled keeper, sessions and continuation. The older
two-card Pi profile instead selected keeper, advertised a virtual 10M context,
disabled client compaction and disabled thinking. Which settings were actually
installed on the remote computer is unknown. The four-card server accepted the
wrong model ID silently and reread the entire conversation each turn. It also
buffered all ordinary answer text whenever tools were present.

The native checkpoint path explicitly rejects TP ranks. Live continuation has
no such ban and already has exact-output/state tests; it is the first practical
latency lever. Keeper policy can work without checkpoints but currently buffers
whole responses and adds internal summary work. It needs separate quality and
latency testing. The 131K TP layout has little VRAM headroom; doubling context
does not fit by changing one flag. The older 262K layout is a different, slower
profile with a 512-output-token limit.

## Restoration and identity

- Boot `f3360802694f4c1aa92779c40200c82c`; all five excluded memory blocks remain offline.
- Mounted existing RAID UUID1498256698254816 read/write with `norecover` and
  Corsair UUID4E0E66ED0E66CD91 read-only with `norecover`; no repair or force.
  Both target shard sizes/device/inodes match the existing authority.
- Fresh RAID build admission passed with 4GiB planned writes and 50GiB free floor.
- Final build SHA256 `69d73cd6efa2e491dc259710ba760e5f50045eb88ff254a15320d8b041601721`.
  Receipt: `experiments/own-xpu-runtime/engine/receipts/persistent-20261104.json`.
  Binary: `/mnt/raid-models/ownrt-serving/2026-11-04-persistent/engine-build-r3/sc117-engine`.
  Runtime RoPE and canonical sources stay on persistent internal storage.
- Relative to hosted37ee90a428cd, only main.cpp and rank.hpp compiled dependencies
  changed: lifecycle/IPC and diagnostics; model kernels/weights/arithmetic unchanged.
  Earlier CPU builds r1/r2 were superseded before any model launch.
- Same model, four-card topology, F32, target-verified MTP, context131072 and
  `tptsxqckhcbgls` kernel flags. No new benchmark/record claim.
- One bounded four-card health probe passed all cards and found no new fault.
  `/mnt/raid-models/ownrt-serving/2026-11-04-persistent/health-preflight.json`.
- One service start at2026-11-04 20:26:30 EST, same address/port18160. Native
  `--seconds=0`, `--wait-seconds=300` on each rank. Adapter operation wait remains
  28800s for this context. Service `Restart=no`; no restart loop.
  Control: `/dev/shm/sc117-4card-lan-20261104-202629/control/run-20261105T012630Z`.

## Validation so far

11 Python lifetime tests, native socketpair deadline/cancellation tests,19 Pi
protocol/retention tests and4 isolated-harness tests pass. LAN GETs expose the
correct model/profile; a disabled keeper-model POST returns400 before inference.
Installed pinned Pi1.2.0 on RAID with lockfile integrity, scripts/optional modules
disabled. Functional fixtures are isolated from workspace credentials and the
GPU devices. No real Pi generation requests yet; startup gates still running.

The compaction fixture uses an8K advertised client window to exercise Pi's
compaction promptly. This tests client behavior, not native keeper or a131K
long-context quality claim. Exact tokenizer budget is recorded alongside it.

## Focus checkpoint

20:31 EST: serving correctness and interactive latency are the main path.
Priorities: finish the one startup gate, run real Pi tool/streaming/reuse tests,
then client compaction and interpret failures. No kernel tuning or additional
model launches while this server is loading. Next focus review in15minutes.
