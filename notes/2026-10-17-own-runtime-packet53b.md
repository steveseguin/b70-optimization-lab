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

## Final CPU qualification

GNU and Intel host builds and the device compile-only build pass. Each host
compiler passes **2,935,673 checks** over2,750 sampled rows, with identical
output hash `4e4601f6ea577bb191930a887c09fd0a52082cee56eb2bd997d14ac604715dcb`. The full-shape pass matches all15 production/candidate
comparisons across the four classes in3.47 seconds. The small proofs take
less than one second each; ASan/UBSan passes the same check count and hash
in 4.62 seconds.
All17 mocked coordinator/parser tests pass, including the exact500 MB cap,
PF_EXITING, future review refusal, missing M2 cases, incomplete HC event
counts, production identity, two-owner selection and the35 µs boundary.

The final offline BMG-G31 report includes15 kernels and binds the final device
build. All use128 configured GRFs. Gate/up split-stream V8/V16, down V4/V8/V16,
HC gate V2/V4/V8 and small FFN V2/V4 have no spill metadata. Paired gate/up V4
retains896 bytes; HC low V2/V4/V8 each retains64 bytes, exactly like its accepted
control. These are offline compiler findings; installed-driver JIT and speed
remain unmeasured. [Full report](../experiments/own-xpu-runtime/stage2/packet53b-virtual/REGISTER-REPORT.md).

Cleanup leaves **62,036,613 bytes** (about62 MB), below500 MB.
The [closeout](../experiments/own-xpu-runtime/stage2/packet53b-virtual/CPU-PREPARATION-CLOSEOUT.md)
links retained evidence and rejected attempts. No GPU, oracle, protected unit
or engine was touched. The coordinator can now run the sealed windows; the
result is pending and no speed improvement is claimed.

## Device results — October 17, 09:45–09:50 UTC

The coordinator ran E1/E2 and T1/T2 on card 0. Both byte windows passed
and have the same complete output identity. The common timing selection is:

| Class | Banked candidate | T1 saved µs | T2 saved µs |
| --- | --- | ---: | ---: |
| Expert gate/up | virtual8-split-stream | 7.3960 | 7.3960 |
| Expert down | virtual16-global | 9.0625 | 9.0625 |
| Small FFN Q6 tuple | virtual4-global | 6.9800 | 6.9790 |
| HC low/gate | control | 0 | 0 |
| Total | | **23.4385** | **23.4375** |

The total misses the registered 35 µs bar: `virtualization_proceeds=false`.
Gate/up V16 loses about 52 µs, and every HC virtualization loses time
(V8 loses 7.395 µs). Those arms are closed. The controls now use the exact
packet49c 820/360-byte pitches; this supersedes packet53's roughly 22 µs
comparison for integration planning, without changing that historical result.

Coordinator decision: keep the three exact winners banked. Combine them with
later qualified candidates in packet49d once the banked total reaches at least
40 µs per ordinary M=1 layer in both owners. Packet54 separately needs 25 µs
of its own; the combined trigger is reported independently. These sums are
operator planning evidence, not an integrated model speed claim.

[Compact receipts](../experiments/own-xpu-runtime/stage2/packet53b-virtual/evidence-copy/p53b-a-summary.json)
retain the exact summary, window receipts, byte comparisons and manifest.
The [retention inventory](../experiments/own-xpu-runtime/stage2/packet53b-virtual/evidence-copy/retention.json)
hashes the unchanged original timing streams, which remain in the ignored
evidence tree. No device was used to record this closeout.
