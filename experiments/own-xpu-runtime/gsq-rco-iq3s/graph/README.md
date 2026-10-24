# GSQ-RCO actual packet3 graph bridge

The actual own-runtime `flash::Directory`, `geometry_from_directory` and 48-layer
`Builder` accept the authenticated new tensor census under a private format
admission overlay. GNU CPU compilation and eight admission/graph tests passed.
The old and new recorded plans have **1,873 identical logical launch sites and
2,065 identical logical buffers**, including every shape, input/output/weight
name, parameter and card assignment. Only packed weight-byte accounting changes.
No arithmetic operator, backend owner, model payload or device was executed.
`native_admitted` remains false.

## What changed and what did not

[overlay.patch](overlay.patch) changes private copies of packet2 enum/layout and
packet3 grid-name admission to cover all 13 actual types. Added Q4_K, Q5_K,
IQ4_XS and Q2_0 numeric decode paths explicitly throw; planning acceptance cannot
silently invoke an absent decoder. F16 and IQ3_XXS names are also admitted. The
actual graph builder, geometry code, API and grid tables remain unchanged.
All frozen originals are rehashed against [parent-pins.json](parent-pins.json).
The private copies stay under ignored `build/private`; [overlay.json](overlay.json)
binds them and the exact patch. Decoder equations belong to the separate
[scalar-format proof](../formats/README.md), not this bridge.

The C++ recorder is reused verbatim from packet3. It first invokes the real
full model planner, then invokes the same Builder with context 4,096. The
metadata bridge checks the exact two-shard identity, complete metadata, all
1,224 names, actual type IDs, dimensions, byte extents and file offsets against
the pinned new census. The old tensor census supplies authoritative per-name
component/layer annotations, independently checked against the old model's
names/shapes/types/bytes. No component is inferred from a filename pattern.

The executable is an internal graph recorder for the bridge-generated TSVs,
not a general authenticated model loader. The expected TSV and input census
are hash-bound by the Python coordinator. Model authentication and actual
shard parsing/placement remain the next integration step. This is the original
**unfused packet3 graph**, not the selected Engine's fused lowering, cache,
expanded weights, capture-site count or executable dispatch configuration.

## Binding and dispatch accounting

Every launch weight is present, every logical buffer reference resolves with
the correct ownership mask, all GEMV/routed-GEMV shapes agree, and each buffer
read/write extent is recomputed. Every one of the 1,224 weights is consumed.
The actual plan contains 36 GDN, 12 QSA and one PLE path; the 24+24 split has one
forward handoff and one result handoff. [accounting.json](accounting.json)
retains every tensor's role, consumer-card mask and location, every buffer mask,
and every `(op,type)` requirement with the originating launch index and tensor.
Every requirement is marked `native_qualified:false`. Counts below count weight
bindings, not physical kernel dispatches.

| Operation | Type | Weight bindings |
| --- | --- | ---: |
| conv | F16 | 1 |
| conv | F32 | 36 |
| gdn | F32 | 72 |
| gdn_norm_gate | F32 | 36 |
| gemv | BF16 | 484 |
| gemv | IQ4_XS | 42 |
| gemv | Q4_K | 43 |
| gemv | Q5_K | 31 |
| gemv | Q6_K | 89 |
| gemv | Q8_0 | 96 |
| lookup | IQ4_NL | 1 |
| lookup | IQ4_XS | 1 |
| norm | F32 | 100 |
| qsa_append_pool | F32 | 12 |
| qsa_prepare | F32 | 36 |
| routed_gemv | IQ2_S | 40 |
| routed_gemv | IQ3_S | 20 |
| routed_gemv | IQ3_XXS | 34 |
| routed_gemv | IQ4_NL | 39 |
| routed_gemv | IQ4_XS | 2 |
| routed_gemv | Q2_0 | 9 |

## Raw 24+24 accounting (not fit admission)

| Plan card | Old raw weights | New raw weights | Logical buffers | New sum |
| --- | ---: | ---: | ---: | ---: |
| 0 | 26,165,134,080 | 25,739,449,600 | 95,960,180 | 25,835,409,780 |
| 1 | 26,464,055,040 | 28,975,258,880 | 96,181,196 | 29,071,440,076 |

New host-file-backed embedding/PLE weights total **29,137,853,440 bytes**. These
sums use the actual unfused plan's logical ownership; replicated logical controls
are counted on both cards. They do not preserve a future loader's mask3 HC
replica policy and must not be mistaken for native allocation placement.
That loader policy requires its own accounting. Expanded cache, transient
scratch, transfer staging, rollback, allocator/driver overhead and peak
residency are absent here. No card-capacity, speed or native fit claim follows.

## Evidence and tests

[build-receipt.json](build-receipt.json) binds the compiler, six compiler
inputs, binary, exact parent/private sources, generated directories, actual
plans and test log. [old-plan.json](old-plan.json) and
[new-plan.json](new-plan.json) are actual C++ outputs. Eight tests cover metadata,
shard/header identity, names/types/shapes/extents/offsets, actual C++ duplicate/
unknown/missing/extra records, real geometry/Builder shape rejection (with the
outer frozen check deliberately bypassed by identical malformed expected input),
context bounds, every retained launch/buffer, and deliberately broken weight/
buffer/card bindings. Numeric paths are never called. All outputs remain below
4 MiB, within the authorized 40 MiB cap.

A bounded GNU build/run uses `build_engine.py` under nice19, cores8–15/24–31,
two-thread variables and 4 GiB address space. The compiler uses the existing
compile-turn lock. Attempt directories preserve sources/logs/receipts; the
helper refuses overwriting promoted outputs. Existing evidence is permanent
research metadata, restorable from Git; only staged headers and compiled
artifacts are ignored.
