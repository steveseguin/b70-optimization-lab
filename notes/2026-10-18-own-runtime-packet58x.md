# Packet58x: larger one-card cache, October 18

CPU admission passes: 21.553 GB cache, 3.553 GB above the 18 GB control.
All original device transient allowances remain, plus 512 MiB for driver
overhead and the unchanged 1.5 GB reserve. Host admission is 98.990 GB with
the measured floor, full backing for the added cache, 4 GiB margin and 8 GiB
reserve. Independent route replay projects +2.26% from reduced fill copies
alone; this is a conditional estimate, not a measured speed.

Evidence and reproduction: [admission](../experiments/own-xpu-runtime/stage2/packet58x-cache-capacity/ADMISSION.md).
The private packet58v copy now has one maximum-size allocation and a quiescent
18 GB / maximum switch. CPU gates and both temporary lane-A plans pass. The
next step is the coordinator's 12 × 64 smoke, then the one-load five-view
12 × 128 bracket only after an exact, cleanly drained smoke. Neither is queued.
Serial maintenance is the default: packet58v's completed bracket is exact and
overlap is faster, but its controls drifted 14.73%, above its registered 3%
limit. Overlap remains selectable. No GPU or service ran in this preparation.

Started at 17:51 UTC with 33.2 GB root free. `git pull --rebase` refused unrelated
dirty orchestration files; fetch confirmed HEAD equals origin/main. Those edits
and all frozen packet trees remain protected. The task's stop floor is 25 GB,
build cap 300 MB, CPU memory cap 4 GB, nice 19 and cores 8–15/24–31.

The admission milestone was committed and pushed as `7cc07d7be`. It projected
+2.2023% using the mean fill cost. The final analysis uses each prompt's own
99 charged intervals and recomputes the six-class statistic: **26.821731 tok/s,
+2.2614%**, still only a conditional projection. The newly finished packet58v
bracket raised the host accounted peak by 57,344 bytes; final admission is
**98,989,727,744 bytes**. No reserve or live shadow stop was reduced.

The implementation's literal sweep found the old native 26.409 GB allocator
limit and updated it together with planning and Python admission. Read-only
review caught direct-launch cap handling and missing continuous device
occupancy checks; both are fixed. Actual startup reaches native execution with
the proposal's lanequeue-derived service name and recorded oneAPI library path.
The original oracle binding, drain fix, memory fence and getrlimit refusal stay.

Both builds, K1 mixed-source bytes, repeated capacity/race checks, full-shape
allocation and switching, miniature exact repeats, two parser paths with eight
negative cases, six entry probes, 96 Python tests, seal verification and two
temporary queue plans pass. The build is about 80.6 MB; peak compiler RSS is
below 0.73 GB, and the full-shape mock uses about 30 MB RSS. Compilation waited
for the existing whole-host hold through the shared compiler-turn gate.

[CPU closeout and retained evidence](../experiments/own-xpu-runtime/stage2/packet58x-cache-capacity/CPU-PREPARATION-CLOSEOUT.md).
The final readiness marker is written only after the implementation commit and
proposal hashes are fixed, then committed separately. It is the task's last
content write. Device fit, quality and speed remain pending.

## Packet58xb — overlap and first-view amendment, October 18

At the owner's request, before any packet58x device window, the smoke and all
five v5 views now select `cache_maintenance=overlap`. The cache-cap dimension
stays 18GB/max/18GB/max/18GB; allocation, reserves, BF16 KV, tile16 and target
arithmetic `iq3-p49-split32-v1` are unchanged. This lets the larger-cache screen
measure an incremental gain on the overlap line used by packet58w.

The earlier serial choice above used packet58v's original drift verdict,
which included A0's cold-cache 22.730951 tok/s. The owner's
[p58wb amendment](2026-10-18-own-runtime-packet58w.md#packet58wb--cold-first-view-amendment-october-18)
was made before packet58w's chain. Replaying the frozen smoke and every native
token from all five views under that amendment passes: warm serial controls
26.053436 / 26.078853 tok/s, overlap 28.115842 / 28.152570 tok/s, warm-control
drift 0.097558%, minimum overlap gain 7.810884%. The original packet58v verdict
and every frozen packet are unchanged. These are readiness comparisons from
packet58v, not packet58x measurements or a new record.

Packet58x's own comparison reader now matches that rule: A0 is reported and
must be exact, but is excluded from drift and comparison. Both max views B0/B1
must be at least 1.005 times each remaining 18GB control A1/A2; their max/min
must be at most 1.03. Decimal comparisons preserve the inclusive thresholds.
Every view still requires the exact uncached twelve-prompt suite; the real
reader checks all 128 output tokens and matching prompt/output identities.

Minimal CPU reseal passes: **101 Python tests**, six real queue/window/native
argument paths intercepted before device execution, two old-unit-gate refusals,
drain/teardown and memory checks, the **1,250-source seal**, and both temporary
lane-A queue plans. Entry probes additionally assert overlap in every smoke/v5
table row and the unchanged cache-cap sequence. New regressions cover the cold
first view, an inexact first view, either candidate below a warm control, 3.5%
warm drift, and exact gain/drift boundaries. Native binaries and their existing
byte, protocol, reset and full-shape startup receipts are retained unchanged;
the build remains **80,586,089 bytes**.

The first entry probe refused on the real host-memory gate while the existing
chain held memory. Later probes passed the unchanged live admission check;
no fallback or reduced threshold remains. No service was stopped or started.
Commands used `nice -n 19 taskset -c 8-15,24-31 python3 -B`, closed stdin and
the 4-GiB CPU limit. No model payload was loaded by these probes.

Reproduction from the packet directory: `maintenance_decision.py`,
`plan_queue.py --emit-only`, `argument_gate.py`, `run_cpu_gates.py`, `seal.py`,
`seal.py --verify`, `plan_queue.py`. The last command plans each rewritten
proposal on a temporary queue and never touches a live `queue-*.txt`.

Git pull refused the unrelated dirty orchestration files; fetch confirmed
HEAD == origin/main. The implementation is committed with explicit paths and
pushed, then `READY-FOR-DEVICE.json` is rewritten as the last content write to
bind that commit, the new seal and both planned proposal hashes. The marker
is committed and pushed separately. No GPU, service, sudo, setting, live queue,
other packet tree or screen tree was changed by this preparation. The smoke
and v5 remain unqueued and unlaunched; device fit, quality and speed are pending.

## Packet58xc — own the source closure, October 18

The first smoke passed K1a and K1b, then refused before WSCREEN because the
seal still pinned packet58w's mutable `verify_ready.py`. Packet58wc had
legitimately changed that file. The failed smoke remains untouched under
`evidence/card0-capacity-a/smoke/`; no packet58x model timing window ran.
The reported fault count remains two; this CPU preparation ran no GPU probe.

Packet58x now owns its comparison reader, metrics, supervision helpers,
fault expressions and the command-building functions used by its unit gate.
The original parent smoke and five-view outputs replay from a local verified
snapshot, including every native token against `iq3-p49-split32-v1`. A0 is
still exact and reported, but excluded from drift and gain. Each max view must
reach 1.005 times each remaining 18GB control; control drift must stay at or
below 3%. The native executables, allocation, reserves, tile16 and BF16 KV
are unchanged. Source include paths are mechanically redirected into the
owned historical snapshot; this amendment does not rebuild the executables.

The pin gate refuses any external path absent from the explicit immutable
allowlist. Only the original oracle binding and exact frozen parent binary
hashes are allowed, including the retained compiled object binaries. Nested
admission and fixture provenance also has local copies. Original receipts
and source maps remain under `lineage/` as history, rather than live checks
against sibling files. The 10.235 MB source/evidence archive preserves 1,159
verified original members; [retention and restoration](../experiments/own-xpu-runtime/stage2/packet58x-cache-capacity/RETENTION.md)
explains why it is retained. No parent or other packet tree was changed.

Validation: **106 Python tests**, all six real queue/window entry probes and
both old-unit refusals pass. The probes compare the command and closed
environment with the current coordinator, pass the real live memory check,
and intercept native execution. Peak probe child RSS stayed below **35 MiB**.
The minimal seal and build gate pass with **314 source pins**; retained
build size is **80,586,089 bytes**. No full-shape or GGUF-reading gate was run.
The complete parent replay again gives 0.097558% warm-control drift and a
minimum 7.810884% overlap gain; these remain parent readiness comparisons,
not packet58x speed measurements.

Both proposals now use fresh jobs `packet58x-smoke-c-A` and
`packet58x-v5-c-A`, writing `evidence/card0-capacity-c/{smoke,max}`. The bracket
requires that fresh smoke. Both passed planning on temporary queue copies,
including the coordinator's newly added recursive pin guard. Planning reads
a temporary copy of the prospective readiness marker; it does not overwrite
the live marker early or disable any pin checks. Packet-local copies of the
two proposals are sealed, with the two allowed coordinator proposal paths
recorded separately. Nothing was queued or launched.

Commands used `nice -n 19 taskset -c 8-15,24-31 python3 -B` with stdin closed.
CPU utilities were capped at 2 GiB; entry probes preserve unlimited virtual
addresses to test the real runtime refusal policy and enforce a 2 GiB RSS
ceiling. No service, sudo, settings, model payload read or live queue write
was performed. `git pull --rebase` refused unrelated dirty files; fetch later
confirmed HEAD equals origin/main. Implementation changes are committed with
explicit paths and pushed immediately. `READY-FOR-DEVICE.json` is then the
last content write and is committed and pushed separately.

Recheck from the packet directory: `maintenance_decision.py`,
`plan_queue.py --emit-only`, `argument_gate.py`, `run_cpu_gates.py`, `seal.py`,
`seal.py --verify`, and `plan_queue.py`. The first full model smoke, quality
and capacity timing results are still pending coordinator execution.

## Packet58xd — DRM occupancy units repaired, October 18

Smoke c passed K1a/K1b, then stopped cooperatively during load because the
new sensor accepted only KiB. Its timing and prefill files are empty. The
failed evidence is untouched; the reported fault count remains two, with no
new kernel lines in that failure. This repair ran no device or health probe.

The exact Ubuntu 7.0.0-39 formatter was checked using the matching binary and
System.map. Its image matches the installed dpkg digest. It prints bytes, KiB
or MiB, choosing the largest exact unit up to MiB; zero is `0`, and GiB never
appears. [Kernel evidence and input identities](../experiments/own-xpu-runtime/stage2/packet58x-cache-capacity/DRM-SIZE-FORMAT.md).
The live Python sensor, native post-load guard and admission receipt reader
now handle all three formats. Unknown units, signs, decimals, extra tokens,
Unicode digits and uint64 overflow still refuse. Tests cover both actual
parsers, unit boundaries, zero, malformed values, client deduplication and
the unchanged 30.5 GB occupancy stop. The packet audit found no other active
fdinfo/sysfs size assumption.

Only the device entry was rebuilt. Host executables and reused kernel objects
are unchanged. Peak compiler RSS was **544,669,696 bytes**, under a 2 GiB
address-space cap; retained build size is **80,595,561 bytes**. The original
receipt remains in `lineage/58xc-build.json`. The shared compiler lock was
held by another builder waiting on the stopped smoke's stale hold. Neither
was changed. Read-only checks found no active compiler or whole-host device
child before this urgent entry-only compile ran under the brief's CPU caps.

All **110 Python tests**, six real environment/unit-name entry probes through
intercepted native exec, both old-unit refusals, drain/teardown and memory
checks pass. Probe RSS stayed below 35 MiB. The seal verifies **395 sources**.
No model payload or full-shape execution ran. Parent comparison replay stays
unchanged and supplies no new packet58x speed claim.

Restored historical metadata initially tripped the coordinator's recursive
pin check. Both temporary-plan refusals are retained in
`evidence/queue-plan-smoke-58xd-*-refusal.log`. Only archive-verified generated
JSON copies outside the current build source closure were removed; originals
remain in the owned archive and `restore()` recreates them. The active drain
scanner excludes that historical build cache. No pin guard or external
allowlist was relaxed.

Both final proposals pass planning on temporary queue copies with a temporary
prospective readiness marker. Jobs `packet58x-smoke-d-A` and
`packet58x-v5-d-A` use `evidence/card0-capacity-d/{smoke,max}`; v5 requires the
fresh smoke. Neither is queued. Commands used `nice -n 19 taskset -c
8-15,24-31 python3 -B` and closed stdin. No GPU, services, sudo, settings,
model reads, live queue writes or other packet changes were performed.

Git pull refused unrelated dirty work; fetch initially confirmed HEAD equals
origin/main. Implementation changes use explicit-path `git commit --only`
and are pushed immediately. `READY-FOR-DEVICE.json` is the last content write,
binding the implementation commit, rebuilt artifact seal and both planned
proposals; it is then committed and pushed separately. Fresh smoke, full model
quality and timing remain pending coordinator execution.
