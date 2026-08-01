# Laguna exact M12 Q/K RMSNorm plus RoPE preregistration

Date: 2026-07-31 America/Toronto

Status: **component gate passed; one frozen cold TP4 endpoint leg authorized**.

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

The component stage authorizes no KV/model/draft precision change, arithmetic
relaxation, teacher or metric change, reset, reboot, or LocalMaxxing
submission. Endpoint authorization is conditional on the results below.

## Component result and endpoint authorization

The focused `_C.abi3.so` build passed the changing-input rows-12 component
gate on one B70:

- artifact:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-qknorm-rope-m12-component-20260801T030706Z`;
- raw BF16 equality: `64/64` total (`32/32` full attention and `32/32`
  sliding attention);
- full shape: `0.033718685 ms` incumbent to `0.012145815 ms` candidate;
- sliding shape: `0.034321015 ms` incumbent to `0.012058350 ms` candidate;
- 48-layer weighted projection: `1.640180760 ms` to `0.579850380 ms`;
- structural submissions: `144` incumbent kernels to `48` candidate kernels.

The source and runtime identity for the endpoint candidate are:

- XPU-kernel source `69e8ad9119a9cc70c3906b82be6254dd0160f00e`;
- candidate `_C.abi3.so` SHA256
  `ba7a3f6d21a15eec2a78a458b92a11ef4b8f4c8655752d9c47386dba628b0e9b`;
- vLLM selector source `58608c6361f1a958a7e933bed0be8c88c35aa26e`;
- unchanged record grouped-GEMM DSO SHA256
  `c4845ed7704a9afcf59e12f9d51e288f293f2e39966e283e2a7e322fed68b839`;
- runtime lock
  `tools/runtime-lock-qknorm-rope-m12.json`, SHA256
  `1b7a6d01969d09c3f9bde114a75748dace0ecbaecd7f01ebc3051d22ad74d606`.

This passes the preregistered component stop boundary. Exactly one cold,
first-valid-score endpoint leg is now authorized with only the QKNorm/RoPE
selector enabled on top of the confirmed transposed-scale record. Require
13/13 canonical-q1 token and text equality, `cached_tokens=0` on every row,
146/145 target and 14/13 draft topology on all four ranks, one invocation per
prompt, and clean teardown. Report the conventional 99-interval median first.
Do not combine native BF16 MM or shared-elementwise work in this first leg.
