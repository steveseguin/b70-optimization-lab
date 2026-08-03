# Laguna INT4 tile-record replacement design and accounting correction

Date: 2026-08-03 America/Toronto

Status: **offline replacement integrated in paired kernel/vLLM worktrees;
one-owner host behavior, fail-closed lifetime gates, and both BMG AOT targets
pass; no device correctness, allocator, latency, throughput, or record
evidence**.

No successful device/model load, generation, benchmark, service, reset,
recovery, privilege, or submission action occurred. One accidental over-broad
test command attempted XPU initialization before interruption and is explicitly
quarantined below. The corrected PCIe/NVMe quarantine and protected 125.461973
conventional tok/s record remain unchanged.

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
or fragmentation. Projection-by-projection replacement is now implemented.
Per target layer and rank, checkpoint-layout W13 weight plus scale is 216 MiB,
W2 weight plus scale is 108 MiB, and the completed record pair is the same 324
MiB logical payload. Packing W13 first exposes 324 + 216 = **540 MiB** of
simultaneous affected logical storage before replacing and releasing its
source; packing W2 then exposes 216 + 108 + 108 = 432 MiB. Allocating both
destinations before either replacement would expose 324 + 216 + 108 = **648
MiB**. Thus the sequential design bounds the exact tensor-payload excess at
+216 MiB/rank over the ordinary post-load affected storage. This is still not
an allocator or startup-peak measurement and excludes allocator rounding,
reservation, fragmentation, and implementation temporaries below the
projection boundary.

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

The integrated successors are:

- kernel consumer/capability commits `5f019f0` and `f050bec`, on the same
  kernel worktree, with the restored exact M12 mapped-tail commits `0c0d9bd`
  and `8944dcd`;
- vLLM post-load ownership/factory/reload/offload commit `8fe856e1a` and
  follow-up test commit `7d4c50696`, on the same vLLM worktree.

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

## Resolved consumer matrix and fail-closed boundaries

All weight consumers in the paired source contract now accept the immutable
TileMajor ABI:

- generic grouped GEMM covers M12, other decode widths, and prefill;
- fixed M<=8 top-k INT4 covers the non-fused exact-small route;
- fused W1/SILU and W2/reduce cover the exact fused route; and
- the restored M12 mapped gather/scale/add endpoint consumes the generic W1/W2
  results and shared output without requiring a standalone transposed-scale
  clone.

The specialized SYCL kernel names include the layout bit, use the exact
`N * (K / 32) * 18` expert stride, and preserve incumbent nibble decoding,
BF16 scale bits, arithmetic, reduction order, and barriers. Generic and
specialized entrypoints require K32/N64, exact record shapes, and weight/scale
base-pointer aliasing, and reject the ordinary-only dequant-MAD path.

The vLLM post-load method preflights both projections, then packs and replaces
W13 before allocating W2. Each projection has one Parameter owner; scale and
modular-weight ABI aliases are non-persistent buffers sharing that storage.
The state dict contains only the two kernel-format owners. A real-method host
test proves the original W13 weight and scale Parameters are collectible inside
the W2 pack callback.

The layout marker `laguna_int4_tile_record_v1` reaches both XPU wrapper
construction sites. Before packing, vLLM queries a no-tensor native capability
op on the source device. The op fails closed unless the loaded binary was built
with XE2 support, the selected architecture is accepted, XE-default is not
forced, and the same cached native record selector used by every consumer is
enabled. The Python capability additionally requires the separately built
`_moe_C` M12 mapped-tail op, so a skewed partial install fails before packing.
Record-mode public apply entrypoints repeat that device-specific capability
check, catching later force-default drift.

The selector-on factory is limited to the exact protected Laguna INT4/group32/
symmetric/BF16/E64-of-256/EP4/K10/3072x1024/SILU contract and the required
exact-small selectors. Reference MoE, transposed-scale clones, dequant-MAD,
direct M1/M2, MXFP4 prepack, SwiGLU controls, bias, router-weight-on-input,
EPLB, CPU/UVA/prefetch offload, layerwise reload, and fallback quant methods
fail closed. Fresh checkpoint-layout strict loading into a record-format state
dict remains unsupported. An allocation failure during W2 packing can leave
W13 replaced, but model initialization then terminates; retaining rollback
storage would defeat the lower logical peak.

Named offline validation:

- kernel host/static matrix: **48 passed**;
- vLLM packer/integration/real-method ownership: **21 passed**;
- strict-env/reload/offload nodes: **14 passed**;
- Ruff, Python byte compilation, and `git diff --check`: passed;
- compile-only BMG AOT: `_xpu_C` and `_moe_C` both linked successfully.

No built extension was imported or executed. The AOT result proves
compilation only, not device correctness or performance.

The successful compile-only invocation pinned the experiment worktree rather
than relying on the helper default:

```bash
KERNELS_DIR=/home/steve/src/laguna-xpu-kernels-int4-tile-record-replacement-20260803 \
BUILD_DIR=/home/steve/src/laguna-xpu-kernels-int4-tile-record-replacement-20260803/build/xpu-c-only-tile-record-20260803 \
INSTALL_PREFIX=/tmp/vllm-xpu-tile-record-20260803 \
JOBS=2 GDN_KERNELS=OFF \
  scripts/build-vllm-xpu-kernels-xpu-c-only.sh

cmake --build \
  /home/steve/src/laguna-xpu-kernels-int4-tile-record-replacement-20260803/build/xpu-c-only-tile-record-20260803 \
  -j=2 --target _moe_C
```

The helper set the existing BMG AOT device `bmg-g21-a0`. The final
device-index dispatch fix then rebuilt and relinked `_xpu_C` incrementally in
the same worktree build directory.

One over-broad reload-test command accidentally selected parameterized engine
tests and attempted XPU initialization before being interrupted. It completed
no successful model load, generation, or benchmark and is quarantined as no
evidence in
`/home/steve/identified-mistakes/2026-08-03-laguna-overbroad-reload-pytest-xpu-init.md`.
A later compile helper invocation also briefly targeted the default base
checkout instead of this worktree; it was stopped at 108/706, installed no
binary, and contributes no evidence. The successful compile commands used an
explicit worktree source and build directory.

## Current decision

The canonical 370/318 emitter remains the preferred offline record kernel.
The replacement lane has advanced from an abstract memory blocker to a paired,
compile-clean offline implementation with one-owner post-load replacement and
every known source consumer covered. It remains an offline implementation
lane, not correctness, allocator-memory, latency, throughput, or record
evidence. The protected **125.461973 conventional tok/s** runtime record is
unchanged. Any device/model validation remains separately authorization-gated
under the corrected PCIe/NVMe quarantine.
