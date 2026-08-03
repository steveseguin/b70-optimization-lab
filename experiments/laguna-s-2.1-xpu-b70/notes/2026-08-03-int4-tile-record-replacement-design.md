# Laguna INT4 tile-record replacement design and accounting correction

Date: 2026-08-03 America/Toronto

Status: **47-routed-layer accounting corrected; post-load ownership seam and
consumer blockers audited; direct host packers pass CPU tests; no integrated
or runtime-capable replacement yet**.

No device, model, XPU runtime/probe/import, service, reset, recovery, privilege,
or submission action occurred. The corrected PCIe/NVMe quarantine and protected
125.461973 conventional tok/s record remain unchanged.

## Correction: 47 routed-MoE layers, not 48

The prior tile-record memory ledger incorrectly multiplied routed-expert
payload by all 48 transformer layers. The target has 48 transformer layers but
only 47 routed-MoE layers, IDs 1 through 47. Layer 0 is dense.

The source-of-truth evidence agrees:

- target `config.json` has `num_hidden_layers=48`, `mlp_only_layers=[0]`,
  `decoder_sparse_step=1`, and `num_experts=256`;
- `LagunaDecoderLayer` selects `LagunaMLP` for layer 0 and `LagunaMoE` for
  layers 1..47;
- the safetensors index has routed-expert keys for exactly layers 1..47 and no
  routed-expert key for layer 0; and
- the weightless fixture independently records `layers=48`, `moe_layers=47`.

Dense layer 0, dense shared experts, and the six-layer dense DFlash model have
no E64 routed W13/W2 group32 payload and cannot supply a missing 48th record.

The exact conditional logical payload under EP4/E64, the frozen W13/W2 shapes,
group32 BF16 scales, and 1152-byte records is therefore:

| payload | bytes | MiB | GiB |
| --- | ---: | ---: | ---: |
| W13 records, 47 layers | 10,645,143,552 | 10,152 | 9.91406250 |
| W2 records, 47 layers | 5,322,571,776 | 5,076 | 4.95703125 |
| all records | **15,967,715,328** | **15,228** | **14.87109375** |
| conventional packed weights | 14,193,524,736 | 13,536 | 13.21875000 |
| one BF16 scale layout or clone | 1,774,190,592 | 1,692 | 1.65234375 |
| incumbent weights + original scales + clone | 17,741,905,920 | 16,920 | 16.52343750 |

Consequences:

- retain conventional weights/scales, add records, and remove only the clone:
  29.74218750 GiB steady logical payload, a **+13.21875 GiB/rank** growth;
- replace weights, original scales, and clone completely with records:
  14.87109375 GiB, a **1.65234375 GiB/rank** saving; and
- records plus surviving original scales: 16.52343750 GiB, exactly the
  incumbent affected payload and therefore no saving.

The old 48-layer record, scale-clone, and duplicate-growth claims of 15.1875,
1.6875, and 13.5 GiB respectively are superseded. They were high by 324, 36,
and 288 MiB. This correction applies to the July 31 transposed-scale note and
the August 3 INT4 affine state, tile-record, scale-payload-clone, one-cursor,
weight-cursor, hybrid-prefetch, and canonical-cursor preregistration/result
notes. Those chronological artifacts are deliberately preserved. Their
duplicate-integration hard stop remains correct; only their byte totals are
superseded.

These are exact tensor-payload calculations, not allocator or startup-peak
measurements. Peak remains unknown. A whole-record allocation after the
incumbent clone existed would expose at least 31.39453125 GiB of simultaneous
logical payload before packing temporaries, allocator rounding, reservation,
or fragmentation. Projection-by-projection replacement should be materially
lower but is not yet measured.

## Ownership and lifetime audit

The deployed path selects `CompressedTensorsWNA16MarlinMoEMethod`. It registers
checkpoint-layout packed-weight and BF16-scale Parameters, loads the checkpoint
through their `weight_loader` attributes, then calls
`convert_to_wna16_moe_kernel_format` from
`process_weights_after_loading`.

The narrowest replacement seam is
`vllm/model_executor/layers/fused_moe/oracle/int_wna16.py::_process_weights_xpu`.
Its outputs immediately flow into `replace_parameter` in
`compressed_tensors_moe_wna16_marlin.py`, module by module, before
`load_model` returns. Model-weight profiling, available-KV calculation, KV
allocation, warmup, and graph capture all happen later.

The current ordinary path instead produces full conventional
`[E,N,K/2]` weights and `[E,N,K/32]` scales there. On the first profile forward,
`XpuFusedMoe` lazily allocates signed-nibble weight copies and persistent
transposed-scale clones. That lazy wrapper is too late for the replacement: it
is already inside the memory-profile forward and complicates reload/graph
ownership.

The intended single-owner contract is:

1. `w13_weight_packed` and `w2_weight_packed` are the only persistent
   registered Parameters and storage owners;
2. `w13_weight_scale`, `w2_weight_scale`, `w13_weight`, and `w2_weight` are
   detached, non-persistent buffer views;
3. each projection's owner, modular-weight view, and BF16 ABI scale view share
   exactly one storage pointer;
4. state dict and `named_parameters(remove_duplicate=False)` expose each owner
   once; and
5. no conventional weight, original scale, transposed-scale clone, or lazy
   `implement_zp` allocation survives.

Layerwise reload also needs an explicit rebinding test. Existing reload code
can copy processed bytes back to stable owner/buffer addresses, but the rebuilt
quant config and kernel may otherwise retain references to temporary packed
views. Until stable-pointer reload and graph-facing rebinding are proven, live
reload is outside the record contract.

## Host packing result

Two focused source commits now preserve the packing work:

- canonical-kernel descendant
  `/home/steve/src/laguna-xpu-kernels-int4-tile-record-replacement-20260803`,
  branch `experiment/laguna-int4-tile-record-replacement-20260803`, commit
  `faf3809`: conventional-layout reference packer, **9 CPU tests passed**;
- deployed-vLLM descendant
  `/home/steve/src/laguna-vllm-int4-tile-record-replacement-20260803`, branch
  `experiment/laguna-int4-tile-record-replacement-20260803`, commit
  `75c6b9804`: direct GPTQ-layout-to-record packer, **6 CPU tests passed**.

The direct packer consumes checkpoint/load-time `[E,K/8,N]` int32 weights and
`[E,K/32,N]` BF16 scales. It writes one expert at a time into one exact-size
record allocation and never materializes a full conventional projection.
Tests cover exact record order, owner/alias shape and pointer identity, exact
allocation bytes, input immutability, contract rejection, exhaustive 256-byte
signed conversion, and BF16 raw-bit preservation for signed zero, infinities,
NaNs, and subnormals.

The audit corrected a misleading conceptual description of the existing
`implement_zp` transform. Its actual byte result is exactly `packed ^ 0x88`, a
high-bit flip in each nibble. It is not the mathematical sign-magnitude mapping
previously encoded by the first uncommitted helper draft. Both committed
packers now match the live implementation exhaustively. The transform is
applied before scale interleaving; applying it to a complete record would
corrupt every BF16 sidecar.

An initial uncommitted attempt to pack lazily inside `XpuFusedMoe.__init__` was
removed after the ownership audit. It was at the wrong lifetime seam and is not
part of either commit above.

## Blocking consumer matrix

The generic XE2 grouped GEMM understands the TileMajor record ABI and verifies
that the int8 owner and BF16 scale marker alias one base allocation. The
protected Laguna path is not yet fully record-capable:

- exact M<=8 W13/W2 dispatch uses
  `cutlass_grouped_gemm_m8_topk_int4_xe2_impl`, which hard-requires ordinary
  weight and scale shapes/strides;
- the fused W1/SILU/route/W2 path has the same ordinary-only contract in both
  mainloops;
- the reference fallback expects ordinary tensors;
- the width-12 transposed-scale selector expects a standalone clone; and
- generic TileMajor currently forces the M8 policy for every row count, so
  prefill/large-M performance risk is unresolved.

Therefore packing is not wired into `process_weights_after_loading` yet. Doing
so now would either break exact decode consumers or require retaining the
13.21875-GiB conventional representation. Both outcomes fail the gate.

The score-preserving successor must make every specialized W1/W2 record
consumer TileMajor-aware, suppress standalone scale clones and lazy recoding,
fail closed for reference/EPLB/reload/offload combinations that are not proven,
and carry an explicit immutable layout marker such as
`laguna_int4_tile_record_v1` through vLLM's quant config into the XPU wrapper.
Only after host ownership, reload, consumer-matrix, and compile/static gates pass
could a separately authorized device action be considered.

## Current decision

The canonical 370/318 emitter remains the preferred offline record kernel.
The replacement lane has advanced from an abstract memory blocker to two
byte-exact, bounded host packers and a concrete ownership seam. It remains an
offline implementation lane, not correctness, memory, latency, throughput, or
record evidence.
