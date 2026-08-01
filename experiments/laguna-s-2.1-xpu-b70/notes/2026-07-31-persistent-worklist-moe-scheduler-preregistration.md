# Laguna persistent compact-worklist MoE scheduler preregistration

Date: 2026-07-31 America/Toronto

Status: preregistered before source change, build, or device execution.

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

