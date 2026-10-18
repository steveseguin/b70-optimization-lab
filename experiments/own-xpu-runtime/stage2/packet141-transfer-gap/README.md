# Packet141 — cold sequence versus warm kernels

CPU-prepared diagnostic; no device evidence or speed claim. The only proposal
is [lane B](../../ops/lane-queue/proposed-p141-probe-B.txt), **not queued**.
[Preregistration and work note](../../../../notes/2026-10-18-own-runtime-packet141.md).

One TP2 load runs the first 47 packet49 incident-retrospective tokens, checking
every token, then measures rank0's next 24-layer target half at position 133.
Its input token is 10015. The actual routes must match packet138's saved fixture
48 on all 24 layers; no expert IDs or hidden values are injected. A reset and
an eight-token oracle check follow. The rank1 process stays loaded but does not
run during the half diagnostic. This is a single workload/owner diagnostic,
not a varied-prompt throughput qualification or a fresh-owner speed verdict.

The packet136 bundle8 selection, target arithmetic and original compiled kernel
objects are retained. All 196 top-level native source files are copied; all 182
parent symlinks are preserved verbatim. `preserve_links.py` restores ignored
build links. The oracle remains a link, validated through `oracle-binding.json`
and `shared_oracle.py`, never flattened into a source map. The original
compiled-source closure is hash-bound; only a private engine entry is rebuilt.
Its host entry is O1 to bound preparation cost; the production kernel objects
and arithmetic flags are unchanged. No throughput inference uses host-loop time.

## Measurements

Four cyclic arm orders give each arm each position, from identical saved real
state and the exact same 530 prepared kernel calls. Timing queries happen only
after the corresponding commands finish. These are real queue submissions;
prepared command-group interception is not an XPU executable graph. No external
profiler, graph-event profiling or per-site wait is added to arms a or c.

- **a:** device-local 256 MiB cache sweep, then the full half in original order.
- **b:** each original site repeated six times, retaining the last four. Restore
  its output/in-place buffers before each repeat; first and last producer bytes
  must match. A multi-pass site stays a multi-pass site. Restore time is excluded.
- **c:** the full half in order, reading every 64-byte line of the consumer's
  actual weight allocations immediately before that site. Expert banks touch
  only the ten captured experts. Touch events are retained separately.
- **natural:** the same in-order half without the extra eviction sweep. This
  tests whether a's controlled cache condition exaggerates the ordinary sequence.

All arms must finish with identical hashes for **all** saved nonweight device
allocations. The initial snapshot is 778,473,844 bytes; its hard cap is 1,500 MiB.
No snapshot is written to disk. New device storage is 256 MiB plus 256 KiB;
full-size CPU allocation admission passes on both ranks. Native rank0 routes and
complete state equality still require the future device run.

Sum all event durations per class per half before taking medians. Warm samples
are four complete virtual halves assembled by repeat index; do not sum medians
of individual events. Retain per-site counts and raw start/end clocks. Report
queue span and host wall separately; warm wall includes diagnostic restores and
cannot stand in for engine launch time. Pre-touch traffic/time is excluded from
kernel duration, explicitly reported, and never offered as a free optimization.

Primary disjoint classes: attention (including GDN), HC, MoE gate/up, MoE down,
shared plus fused router, route, norms and small kernels. Fused gate/up and
shared/router events cannot be honestly split further; retain their original
site labels and never charge them twice. Detail rows preserve every site class.

Preregistered decision: all class ratios a/b <=1.15 closes the body lever under
this diagnostic and retains the working 59–60 band; any class >=1.30 with
>=0.5 ms/half goes to a class-specific layout/allocation/order brief; otherwise
report and close. Incomplete coverage or failed equality is inconclusive.
Additionally, if natural/a differs by more than 10% in a >=0.5 ms class, do not
apply the kill gate: forced eviction is not representative enough. This validity
check can only withhold a verdict. Hardware L2/L3 occupancy is not directly
measured; the probe does not equate useful bytes with measured DRAM traffic.

## Coordinator handoff

Expected device duration: 10–20 minutes; watchdog: 4,800 seconds (4× upper
estimate). One load, one attempt, no retry. The proposal uses
`screen-packet141-probe-B.service` and embeds the oneAPI library path. Existing
lane reservation, fault review, memory floor, masks and cooperative drain apply.
The native boundary refuses finite address-space limits or changed getrlimit
values. CPU resource caps exist only in CPU command entrypoints.

CPU preparation commands, each prefixed by `nice -n 19 taskset -c 8-15,24-31
python3 -B`, stdin `/dev/null`: `preserve_links.py`, `build_engine.py`,
`full_shape.py`, `test_probe.py`, `argument_gate.py`, `seal.py`, `queue_plan.py`.
Compilation uses `ops/compile_turn.py`; root must retain 25 GB, physical build
files stay below 300 MB, probe output below 200 MB. No live queue, device,
service, power, memory, swap or page-cache setting is touched by preparation.

Read `READY-FOR-DEVICE.json` for the exact preparatory commit and proposal hash.
Device execution remains the coordinator's action. After clean release, the
CPU analysis consumes the retained raw events, complete-state checks and oracle
receipts. It refuses partial or altered evidence.

Timing review: all measured sites use original `enqueue()` / `finish()` bookkeeping.
One additional cold half per block uses original enqueue without event recording;
its wall time must agree within 10% with arm a. Large between-kernel gaps
(>=0.5 ms and >10% of span) withhold the kernel-bound inference. The extra
control is diagnostic and must reproduce the same whole-half state exactly.
Warm restore includes declared fused outputs and in-place KV/recurrent state;
whole-half state hashes fail closed on undeclared stateful alias effects.

The natural control follows the same host-to-device state restoration as other
arms. It is a no-extra-eviction sensitivity check, not a direct cache-occupancy
measurement. Report this limitation with any diagnostic conclusion.
