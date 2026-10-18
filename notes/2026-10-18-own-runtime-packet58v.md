# Packet58v: overlap one-card expert-cache maintenance

CPU-only preparation on main. Pull refused the unrelated dirty files; fetch
confirmed HEAD and origin/main at `19d0d2b4eb26e1f0a9ea58ffd5706565a41d2b24`.
No GPU, service, live queue, host setting or frozen packet is changed.

## Measurement milestone

[Receipt analysis](../experiments/own-xpu-runtime/stage2/packet58v-async-cache/evidence/measurement.json)
joins cache epochs to every request's prefill and generated positions. The
metric uses generated events 2–100: 1,188 positions per view. These means
are measured spans, not reciprocals of the class-balanced token rate.

| Evidence | Cache ms/token | Fills/token | Fill MB/token |
| --- | ---: | ---: | ---: |
| 58p WS | 7.061129 | 33.005051 | 65.456571 |
| 58p WS128x | 6.993898 | 33.005051 | 65.456571 |
| 58p WS128 record | 6.991363 | 33.005051 | 65.456571 |
| 58r A0/B0/A1/B1/A2 | 6.841656–7.144937 | 33.005051–33.189394 | 65.456571–65.820854 |
| 58t A0/B0/A1 | 7.153813–7.223038 | 33.005051–33.179293 | 65.456571–65.801244 |

The 58p record's token wall mean is 37.973680 ms. Every position publishes
144 pointer tables, totaling 1,179,648 bytes. Their separate publication time
was **not recorded**; it is included in cache wall and cannot be recovered
from aggregate copy counters. Fill bytes are commanded payload, not measured
PCIe traffic. Bracket repeats are diagnostics, not independent fresh-load
speed results.

The older [58i attribution](../experiments/own-xpu-runtime/stage2/packet58i-onecard-attribution/ATTRIBUTION.md)
measured 7.834869 ms cache work inside a 40.667671 ms token on 58g. The newer
record still spends 18.41% of its mean token wall in cache maintenance, far
above the 1.5 ms stop threshold. Proceed with the implementation.

Reproduce with `nice -n 19 taskset -c 8-15,24-31 python3 -B
experiments/own-xpu-runtime/stage2/packet58v-async-cache/measure.py </dev/null`.
The analyzer is capped at 4 GiB and does not import a runtime or read weights.

## Design and evidence status

Implemented in the new copy: retain tile16 arithmetic and global LRU; publish
host pointers before reusing victim slots; copy on a separate BCS event chain;
expose completed fills only at a later position boundary. Pointer publication
uses one contiguous upload plus a scatter into the existing tables. Planning
uses retained routes while the next position computes. Because those victims
cannot safely be revoked during that position, reuse begins at the following
boundary: this conservative version adds one position of lag. Pending slots
cannot be evicted again. All actual routes still update LRU recency.

Both GNU and Intel builds and the final full-shape integration checks pass.
The protocol/ownership race gates and full-size K1 source byte comparisons
pass on CPU. The 87 Python policy checks pass. There is no device correctness
claim. The private packet58u policy, plus a 32 MiB metadata
allowance and 1,179,648-byte staging backing, needs 95,435,761,152 bytes of
available host RAM. The 8 GiB reserve and original device ceiling remain.

[Per-prompt sensitivities](../experiments/own-xpu-runtime/stage2/packet58v-async-cache/evidence/projections.json)
give 28.01964 tok/s (+6.83%) if all fill DMA at an assumed 25 GB/s is hidden,
with only 0.25 ms extra cost per token. Hiding half the cache wall with 0.5 ms
overhead gives 28.49486 (+8.64%). Both assume no loss of cache hits, no bandwidth
contention and no driver serialization. They are conditional calculations,
not speed results. The impossible all-cache-removal bound is 32.07938 tok/s.

Hot-expert cache idea credit: Niko1221 / Strata. Implementation is lab-authored.
Device equality, small async smoke and performance remain pending. No gain
is measured by this preparation.

## Final CPU handoff

Measurement milestone `2a09e170e` and implementation milestone `8aa900539`
were each pushed immediately. The final [seal](../experiments/own-xpu-runtime/stage2/packet58v-async-cache/build-receipt.json)
verifies 537 source/dependency pins and all thirteen CPU evidence gates.
The build occupies 80,484,411 bytes. The largest compiler child used about
727 MB RSS; K1 used 339 MB and the full-size sparse startup used 30 MB.

The protocol fixture performs 9,966 checks and 388 expected race refusals
per repeat, including three consecutive reuses of the same slot. Both repeats
pass. The owner fixture separately proves foreground retirement leaves DMA
pending, pending release refuses, and final shutdown drains before freeing.
The actual Engine full-shape test submits all 1,440 mock projection copies,
retains incomplete fills, and publishes only at a later boundary. K1 source
bytes, reset brackets, both real parser paths, six intercepted native launch
paths, shared oracle, drain fix, admission and all 87 Python checks pass.

The [smoke proposal](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p58v-smoke-A.txt)
and [v5 proposal](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p58v-v5-A.txt)
both pass the coordinator planner on temporary queue copies. Expected time is
10–15 and 20–30 minutes respectively; each watchdog is 7,200 seconds. The
commands embed the recorded oneAPI library path. The larger runner checks
the exact smoke's build, output tokens and clean drain before it can launch.
No live queue or device output directory was created. The plan retained
36,324,839,424 root-free bytes and budgeted 2,684,354,560 bytes for both jobs,
leaving the 25 GB floor intact.

[CPU closeout and limitations](../experiments/own-xpu-runtime/stage2/packet58v-async-cache/CPU-PREPARATION-CLOSEOUT.md).
No frozen packet, screen, live ops file, service, GPU job, host setting, sudo,
reboot, external submission or unrelated process was touched. Existing dirty
orchestration files remain outside these commits.

## Packet58vb: launch-unit repair and minimal reseal

The 16:23:22 UTC smoke was refused before device work because the copied
unit gate still named packet58r. The gate now derives packet58v service
names from lanequeue's own command builder and retains the coordinator
`packet58-` prefix. Other packet services still refuse. The literal sweep
also corrected queue receipt labels, diagnostics and scratch names. It
restored an accidental historical measurement-path rewrite; replay produces
the exact same measurement bytes. Historical provenance, shared contracts
and the unchanged CPU parser ABI remain explicit.

Both actual proposals now enter the real queue runner, then all six
window/native argument paths with the real unit/environment checks, passive
card topology and live host-memory admission. Both fail on the old gate and
pass with the fix. Native execution is intercepted. All 91 Python policy
tests pass; the reseal verifies 540 source/dependency pins. Both temporary
queue plans pass. The 95,435,761,152-byte model admission and 8 GiB reserve
are unchanged. No compiler, GPU, service, live queue or settings were used.

The [repair closeout](../experiments/own-xpu-runtime/stage2/packet58v-async-cache/packet58vb-closeout.md)
records the literal classification and synthetic test boundaries. The
[minimal-reseal receipt](../experiments/own-xpu-runtime/stage2/packet58v-async-cache/evidence/minimal-reseal.json)
confirms identical binaries, native sources, host policy, oracle and
`iq3-p49-split32-v1` arithmetic. Device correctness remains pending.
The final `READY-FOR-DEVICE.json` binds the committed repair and proposal
hashes; it is the last content write and lands in a follow-up commit.
