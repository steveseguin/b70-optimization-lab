# Laguna persistent compact-worklist MoE scheduler preregistration

Date: 2026-07-31 America/Toronto

Status: **closed exact component negative; do not integrate or endpoint-run.**

## Why this is distinct

Three scheduler treatments have now measured below the exact persistent
control:

- flattened maximum grid: `0.916350x`;
- expert-indexed fixed grid with a per-workgroup prefix scan: `0.974647x`;
- expert-indexed fixed grid supplied exclusive offsets: `0.929750x`.

The last result is decisive about fixed grids, not about the 64-expert scan in
the incumbent. It reduced generated ISA from 679 to 562 instructions but lost
the incumbent's small persistent set of dynamic work distributors. The next
candidate therefore retains the incumbent launch geometry, atomic tile
assignment, local barrier, N tiling, and exact GEMM body. It changes only the
mapping from an assigned global M tile to its expert and packed-row view.

The supplied metadata is a compact tile worklist. Each entry contains
`(expert_id, expert_row_offset, expert_rows, m_tile_within_expert)`. A
persistent workgroup uses its existing atomic-assigned global M-tile index to
load one entry in O(1), rather than scanning as many as 64 row counts. Entries
exist only for real M tiles; no empty-expert workgroups are launched.

For the component screen, the host derives the worklist from the same frozen
64-count corpus. Production integration is forbidden unless the component
passes. If authorized, the existing remap launch must emit the worklist into a
separate preallocated fixed-address buffer after it has computed the same
expert prefix in SLM. No extra device launch, host synchronization, row
reordering, or fixed expert grid is allowed.

## Gates

1. Add a default-off selector and a separately named 128-GRF kernel. Selector
   off must remain the exact protected transposed-scale record path.
2. Static BMG inspection must retain 128 GRFs, the exact 2-DPAS/32-BF16-mul
   arithmetic body, and the incumbent persistent atomic/barrier scheduler.
3. Use one DSO for both arms on the frozen changed-input physical-transposed-
   scale W13/W2 corpus. Require 6/6 raw-BF16 equality under 200 warmups and
   15x40 timing, no per-shape regression, and at least `1.05x` summed speedup.
4. Stop and preserve the result if the component misses `1.05x`. Do not modify
   remap, load the model, or run an endpoint.
5. A component pass authorizes fused-remap worklist emission and a topology
   smoke only. Smoke must retain 146/145 target, 14/13 draft, cache-zero,
   normal acceptance, four-rank selector evidence, and clean teardown.
6. Only a passed smoke authorizes one cold frozen 13-prompt endpoint leg. The
   first valid result stands.

No model, INT4 weights, BF16 KV, speculative width/depth, verification,
sampling, prompts, teacher, cache, metric, retry, warmup generation, graph
capture window, or scoring window may change. No reboot, reset, FLR, driver
reload, or privileged recovery is authorized.

## Result

The candidate source is kernel commit
`efe33d2d3434dee15e240e86b0f89a72349b5572`. The sealed DSO is
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/builds/persistent-worklist-efe33d2/libgrouped_gemm_xe_2.so`
with SHA-256
`a18843906358204bbc891238389aba846f1a2db92dee57c810cb8b43f517526f`.
The incremental production build completed in 16:51.92 with 106,995,696 KiB
maximum RSS and zero swaps.

Static BMG inspection found the intended separately named 128-GRF worklist
kernel. It retained the incumbent persistent atomic/barrier markers and the
exact arithmetic body of 2 DPAS and 32 BF16 multiplies. Final ISA was nearly
identical: 677 instructions for the candidate and 679 for the transposed-scale
control, with the same assembly spill/scratch marker counts. The probe's
device compilation and all BMG builds succeeded, but its unused host
executable then failed to link unresolved PyTorch symbols. The emitted device
assembly remains valid static evidence; the linker failure is classified as
probe plumbing, not a performance result.

The frozen changed-input component gate used physical B70 rank 0, the same DSO
for both arms, 200 warmups, 15 timing samples, and 40 launches per sample:

| shape | persistent control | compact worklist | speedup |
| --- | ---: | ---: | ---: |
| W13 | 0.320965125 ms | 0.324983675 ms | 0.987635x |
| W2 | 0.183557450 ms | 0.185832475 ms | 0.987758x |
| sum | 0.504522575 ms | 0.510816150 ms | **0.987679x** |

All six changed-input raw-BF16 comparisons were bitwise exact. Both shapes
regressed, and the summed result missed the preregistered `1.05x` gate.
Production remap worklist emission, model loading, and endpoint measurement
therefore did not occur.

The durable result is narrower than the fixed-grid negatives: preserving the
persistent distributor is necessary, but its 64-count scan is not a useful
latency target at these exact M12 shapes. Replacing that scan with four compact
metadata loads removed only two final BMG instructions and made both real
grouped-GEMM shapes about 1.2% slower. Do not retry fixed grids or this
four-int persistent worklist. A future scheduler treatment needs a genuinely
lower-cost task-acquisition representation demonstrated in final ISA before a
production build.

Raw result:
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/persistent-worklist-component-efe33d2-20260801T080500Z/summary.json`.
