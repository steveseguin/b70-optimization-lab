# Packet119: selected DOWN cache warming

CPU-only preparation from frozen packet118. `down_warm=production|p119` adds
independent reads of selected experts' tile16 DOWN weights during unchanged E1
gate/up arithmetic. The values are discarded. Model state, quantization,
verifier, arithmetic order and draft prefix stay unchanged.

[Work note](../../../../notes/2026-10-18-own-runtime-packet119.md) explains the
footprint, bound and diagnostic limits. [Micro preregistration](micro-preregistration.json)
fixes the routes, ordering, byte gates and 15% pair-time kill gate.

Run the proposed micro only through the coordinator:
[proposed-p119-micro-B.txt](../../ops/lane-queue/proposed-p119-micro-B.txt).
It contains two fresh runs. No device has run in this preparation. Actual cache
behavior, device byte identity and speed are pending. The conditional
[v5 bracket](v5/README.md) must not be queued until both micros pass.

CPU build/check entry points: `build_cpu119.py`, `build_microbench.py`,
`queue_plan_micro.py`, and the v5 preparation described in its README.
Use `nice -n 19 taskset -c 8-15,24-31 python3 -B <entry> </dev/null`.
No CPU address-space cap belongs in a module import or native device ancestry.

Frozen sources remain references or packet-owned copies with provenance.
New code is the warming header, binding/parser delta, pair/cache probes,
fail-closed micro analyzer and the copied v5 wrapper. The other copied native
sources exist to keep includes and checked submission preparation local.
