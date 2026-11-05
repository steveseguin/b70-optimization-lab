# Persistent SC117 hosting and Pi experience

Owner requested removal of the shutdown timer, then asked for ongoing testing
and improvement of Pi coding-agent responsiveness, thinking, errors and context
management. The remote Pi version/configuration was unavailable; proceed with
the repository's pinned Pi 1.2.0 and preserve that limitation.

## Implemented changes

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
  Session parking and ctxkeeper remain off; plain-path continuation passed both exact gates.

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

## Validation

The service became ready at20:47:14 EST. All13 batched-prefill cases passed.
Both continuation cases matched fresh execution in tokens, draft guesses and
complete meaningful state. The long suffix used two256-row chunks and crossed
its512-row ring: prefill1330.83ms reused versus2191.02ms fresh. The short suffix
used46.19ms versus1350.91ms. These are functional reuse measurements, not fair
fresh-prompt throughput records.

11 Python lifetime tests, native socketpair deadline/cancellation tests,19 Pi
protocol/retention tests and9 isolated-harness tests pass. LAN GETs expose the
correct model/profile; disabled keeper IDs and an oversized131084-token prompt
return400 before inference. No new kernel faults or service-monitor errors.

Pinned Pi1.2.0 is installed on RAID from the repository lockfile. Functional
fixtures run in an isolated Node22 container without workspace credentials or
GPU devices, through a bounded recording proxy. All tests reuse the one live
server. Raw evidence root:
`/mnt/raid-models/ownrt-serving/2026-11-04-persistent/`.

- `pi-basic`:7 requests, all6 follow-ups reused prompt state; actual read/edit/bash
  tools, visible reasoning, one passing named test. About29.6s from first upstream
  request to last response. The original grader accidentally ran bare node --test,
  which did not discover test_sum.mjs; Pi explicitly ran the named test. Corrected
  CPU-only regrade and original results are both retained.
- `pi-notesdelta`:6 requests, all5 follow-ups reused prompt state. A planted bug in
  the1143-line ctxkeeper module was repaired exactly to its original hash;11 tests
  ran with1 expected skip. About54.5s total. Reading the large file cost26.36s to
  first delta; other follow-ups took0.35–1.99s. Tests and sync helper stayed intact.
- `pi-compaction`: FAILED original8K fixture,14 requests, no upstream errors.
  Pi's fixed4096-token provider margin conflicted with the fixture's2048 reserve:
  output was clipped to1 token before the6144-token compaction threshold. CPU
  replay of the installed functions exactly reproduced all clipped budgets.
  This is preserved as a fixture-budget failure, not a server or GPU failure.
- `pi-compaction-16k`: PASS,9 requests. Threshold compaction reduced9299 tokens to
  an estimated1812; the same persisted Pi session resumed, recalled checksum
  48151623 from an earlier log, fixed the code and passed the named test.
  Uses16K context,8192 reserve,2048 output. Two phases provide a grading boundary.
- `pi-compaction-continuous-16k`: PASS,11 requests in one uninterrupted task.
  Threshold compaction reduced8676 tokens to an estimated3082. Successful edit
  and bash followed compaction; all five ordered log reads, checksum recall and
  the named test passed. No upstream errors or server restarts.

Audit correction: Pi1.2.0 DOES check compaction before tool continuations. An
initial source audit missed the prepareNextTurnWithContext hook; both the
installed source and CLI bundle contain it. Cache usage is not double-counted.
See `pi-smoke-fixture-budget.json` for exact source locations and replay values.

The production131072 profile reserves16384 tokens, covering8192 output plus
Pi's4096 provider margin with4096 remaining at the threshold under matching
estimates. The estimators differ, so this is not a guarantee for arbitrary large
tool returns. These small fixtures do not establish131K long-context quality
or multi-day stability. The remote computer's actual Pi version/settings remain
unverified; merge the served profiles there and select the plain model/medium
thinking, including in resumed sessions.

## Focus checkpoints

20:31 EST: prioritize persistent serving, Pi streaming/reuse and compaction.
20:46 EST: all13 prefill cases passed; continuation state comparison finishing.
21:16 EST: real coding tasks and two-phase compaction passed; one uninterrupted
compaction test underway. Close client-budget investigation after that test,
then examine native keeper integration as the next useful context-management
lever. One continuously running server; no power/memory changes or restart loop.

Structured results: `experiments/own-xpu-runtime/serving/four-card-lan/pi-validation-20261104.json`.
