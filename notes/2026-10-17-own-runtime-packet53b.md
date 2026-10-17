# Packet53b: more logical lanes for experts, HC and the small FFN

This prepares the next coordinator-owned device screen. No GPU program,
model oracle, server, service or host setting is used or changed. Work stays
at nice19 on cores4–15,20–31, one compile at a time. The packet49 oracle and
packet49c record chain remain protected. Build storage is capped at500 MB.

Packet53's V4 choices saved22.083/22.291 µs, below its30 µs bar. Its
[pushed device closeout](2026-10-17-own-runtime-packet53.md#device-results--october-17-09150919-utc)
keeps the original identity and closes the persistent arms. Packet53b needs
35 µs across experts, HC low/gate and the small FFN, using one common
per-class selection chosen by the minimum saving across both timing owners.
Savings are against the production kernels, not V4.

The [packet](../experiments/own-xpu-runtime/stage2/packet53b-virtual/README.md)
keeps the original chains and adjacent trees. Experts test paired V4 and
larger V; HC tests V2/V4/V8 across both low/gate sides; small FFN tests
V2/V4. M2 remains two serial rows. There is no new oracle arithmetic.

## Register screening and production control identity

The requested paired gate/up V16 carries32 FP32 sums per physical lane.
At128 GRFs, offline BMG-G31 compilation reported4352 bytes of scratch spill;
paired V8 reported2432. Bounded two-chain scheduling and scalar unpacking
still spilled. The experimental256-GRF kernel property was refused by the
installed offline SPIR-V reader; it is excluded from the device packet.

The registered gate/up replacements split gate and up into separate
subgroups. V8 and V16 then hold8 and16 sums per lane, respectively. Both
reported zero spill metadata in screening. Their extra input loads remain
inside timing. Paired V4 is retained as the requested remeasured reference;
its original spill metadata is reported, not hidden. Down still tests
V4/V8/V16 with the per-chain K640 tail check. Final register inspection follows
the final device build; actual runtime behavior remains for the coordinator.

Review found that packet53's fixture used aligned16 expert row pitches832/368,
while packet49c uses compact820/360-byte pitches. Packet53b explicitly matches
packet49c for both control and candidates. This does not change or invalidate
packet53's recorded comparisons under its own identity. The dense control
bodies match packet49c after namespace and literal launch-range normalization.
The small-FFN control is the actual `p30.small.rows4` tuple, selected by the
SPEED6 map; that map is byte-identical to packet51's baseline map.

The first offline inspection hit two header-mirror inclusion refusals. Their
logs are retained. Subsequent inspection uses the same checked source tree
as the device build. CPU gates remain bounded: one GNU/Intel proof pair,
small control fixtures, one complete-shape M1 pass per class, one sanitizer
proof and mocked coordinator tests. M2 small-proof and full device cases are
retained. Final results will be appended here after qualification.

[INTEGRATION.md](../experiments/own-xpu-runtime/stage2/packet53b-virtual/INTEGRATION.md)
maps each possible winner to packet49c's expert epilogue, HC low/gate and
small-group calls, shared by M1 and both M2 rows. A passing device result goes
to packet49d in the next brief. This preparation does not modify that engine.
[WINDOW.md](../experiments/own-xpu-runtime/stage2/packet53b-virtual/WINDOW.md)
contains E1/E2, T1/T2 and summary commands, with the original PF_EXITING sensor,
past-UTC review boundary, fresh-owner seals and cooperative stop behavior.
