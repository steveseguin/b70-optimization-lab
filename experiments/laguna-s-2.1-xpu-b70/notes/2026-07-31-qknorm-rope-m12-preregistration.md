# Laguna exact M12 Q/K RMSNorm plus RoPE preregistration

Date: 2026-07-31 America/Toronto

Status: **source, focused build, and one-card component gate authorized; no
model endpoint or throughput claim authorized**.

## Premise

The current 122.829 record's target replay profile leaves roughly 65--70% in
captured graph segments. Native M12 BF16 QKV/O MM improved eager streamed
components by 32% but changed the exact endpoint by only +0.24%, establishing
that primitive-dispatch savings can disappear under graph replay.

Q/K RMSNorm plus RoPE is different: the incumbent captured graph contains
three actual device kernels per attention layer. The existing Laguna exact
fusion reduces them to one while preserving the incumbent RMSNorm reduction
tree and BF16 norm-to-RoPE boundary. At M8 it was exact, and its combination
with shared elementwise work produced a valid endpoint record, but its native
entry remains hard-pinned to eight rows.

## M12 geometry

Keep the M8 geometry byte/source unchanged: 16 heads per workgroup, 16 lanes
per head, 256 threads. Add an M12 geometry with 8 heads per workgroup and 128
threads. The two TP4 physical Q+K totals are then exact multiples:

- full attention: 12 rows x (12 Q + 2 K) = 168 heads = 21 workgroups;
- sliding attention: 12 rows x (18 Q + 2 K) = 240 heads = 30 workgroups.

Each head still owns the same 16 adjacent lanes, each lane accumulates the
same eight BF16 elements serially, and the same 16-lane shift tree produces
RRMS. Preserve the explicit BF16 round after `x*rrms`, the BF16 weight
multiply, the existing BF16 cos/sin cache, and the NeoX multiply/add order.
Do not use a partial workgroup or add a tail path.

## Gates

1. The native op accepts only rows 8 or 12, the established TP4 full/sliding
   Q/K shapes, BF16 tensors, head-dim-128 norm weights, rotary 64/128, matching
   outputs, and one position per row.
2. Build only `_C.abi3.so` with the pinned oneAPI 2025.3 toolchain. The grouped
   GEMM DSO remains the confirmed transposed-scale record binary.
3. Extend the existing changing-input component gate with an explicit rows
   argument defaulting to eight. At rows 12 require raw BF16 Q and K equality
   over at least 16 independently seeded epochs for both physical shapes.
4. Require a material timing reduction and the structural 144-to-48 kernel
   count reduction before separately authorizing vLLM selection or a model
   endpoint.

No KV/model/draft precision change, arithmetic relaxation, teacher or metric
change, reset, reboot, service launch, endpoint, or LocalMaxxing submission is
authorized by this stage.
