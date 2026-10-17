# Packet 68c: two rows from the production kernels

Sealed CPU preparation. GNU and Intel each pass **1,428 byte checks** and
produce identical expected/output bytes. The device binary compiles. **No GPU
or model ran here. H(2)/H(1), including the ≤1.3 target, is unmeasured.**

The copied parent is packet68b, retained unchanged. The M1 reference is
packet64 production with `iq3-p49-split32-v1`, full BF16 state/KV, production
draft, ordinary rollback and 24/24 target placement. Packet49 remains the
output oracle. No arithmetic, target weights or emitted tokens are changed.

| Class | M2 implementation |
| --- | --- |
| Routed gate/up and down | Packet65 `wide64` raw vector loads, V8/V16 logical chains, SG32, WG64 and separate gate/up streams; two accumulator sets consume each decoded tile. Stable route union preserves each row's original slots, including partial, repeated and invalid fixture routes. |
| GDN qkv/z, QSA qgate, logits, shared expert down | Packet33 segment body with compile-time type/K/split, original WG32/SG32 geometry and global split scratch; two ordered accumulators. |
| Attention output | Packet49c vector loads, WG256/SG32 split4, original global partials, then the fused BF16 store/stream update with cached injection factors. |
| Router/shared gate/up tuple, HC norm/low/gate/mix, other operations | Two serial production M1 submissions. Every measured class states `batched` or `serial-M1`. |

The production source correspondence is in [production_rows.hpp](production_rows.hpp)
and [production_expert_chains.hpp](production_expert_chains.hpp). The latter is
mechanically derived by [derive_sources.py](derive_sources.py), with the exact
packet65 source and both successful lane screens bound in
[production-sources.json](production-sources.json). M1 expert timings still use
packet64, so the ratio includes the already screened wide64 scheduling change.
The old generic helpers remain copied for fixture history; the probe selects
only the production-derived implementations above.

## Probe and coordinator handoff

The existing lane-B flow still runs incident64 plus all twelve 128-token
packet49 requests. Positions 8, 16 and 32 retain duplicate-input probes.
Positions 9, 17 and 33 additionally pair the saved preceding real engine input
with the current input. These are independent state snapshots, **not a causal
depth-two verifier**; rank0 can include speculative engine inputs.

Three private images suffice: after the paired pass, compare row0 with its M1
reference, recycle that reference image for current-row M1, then compare row1.
Bank swaps remap saved state by logical buffer name. Every plan buffer and spare
state bank is compared; unused scratch is excluded as in 68b. Original bindings
and state are preserved. The 512 MiB per-rank allowance is unchanged.

The log reports separate duplicate/consecutive timings, both individual M1
rows, their mean denominator for consecutive inputs, route overlap, class
execution modes and byte identity. The analyzer refuses incomplete samples,
missing differing-route coverage, nonconsecutive positions, failed row checks,
or any missing one of the thirteen exact output receipts. Copies, preparation,
route readback and checking stay outside the reported replay time.

From the repository root, inside the coordinator's admitted `screen-*` unit
with its approved library environment and fresh fault review:

```bash
bash experiments/own-xpu-runtime/stage2/packet68c-m2-from-production/coordinator_probe.sh "$FAULT_REVIEW"
```

`P49_LDP` is required. The output is
`experiments/own-xpu-runtime/stage2/screen/v3-packet64-lanes/evidence/packet68c-production-B-01`.
The existing 3,600-second watchdog exceeds 4× the approximately four-minute
device window estimate, with extra work for the consecutive fixtures. No retry,
service start or teardown-policy change is added. The private bridge preserves
the frozen wrapper's lane, fault, memory, drain and oracle admission.

After the coordinator completes the window:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B \
 experiments/own-xpu-runtime/stage2/packet68c-m2-from-production/analyze_probe.py \
 experiments/own-xpu-runtime/stage2/screen/v3-packet64-lanes/evidence/packet68c-production-B-01 \
 --output experiments/own-xpu-runtime/stage2/packet68c-m2-from-production/evidence/device-analysis.json </dev/null
```

The default restore source is packet68's measured `evidence/device-cost.json`,
median **0.980923 ms**, pinned by this seal. The original 68b projection formulas
and their older 51.033041 tok/s comparison remain explicit; they are not the
newer packet64 record or a measured depth-two speed. Duplicate sensitivity is
reported separately from consecutive-input projection. No result is fabricated
before device measurement.

## Rebuild and evidence

`build_engine.py`, `cpu_gate.py`, `seal_and_plan.py` follow the parent's lean
CPU flow. Use nice19, cores 8–15,24–31, OMP2, Python `-B`, stdin `/dev/null`,
one compile at a time. The build enforces an 8 GiB address-space ceiling,
12 GiB disk floor and a build under 1 GB. A sealed packet cannot be overwritten.
The retained build is 110,554,976 bytes. Build objects and caches are ignored.

The inherited 4 MiB RoPE constant and four approximately 1.2 MB fixture byte
files are necessary replay/byte-identity evidence. Restore RoPE from the pinned
parent and regenerate fixtures with these sources and recorded compilers.
This is an originating-host build with hash-pinned inherited objects, not a
public portable binary claim.

[Fixture receipt](fixture/receipt.json), [build receipt](build-device-receipt.json),
[plan](evidence/probe-plan.json), [seal](screen-seal.json),
[analysis tests](evidence/analysis-tests.log), [closeout](CPU-PREPARATION-CLOSEOUT.md),
[task note](../../../../notes/2026-10-17-own-runtime-packet68c.md).
