# Exact M=8 Pair-Tiled MHC Closure

Date: **2026-07-18**

Status: **bitwise exact; performance rejected before model load**

## Outcome

A dedicated fixed-M8 vector kernel assigned two verifier rows to each
256-thread workgroup and loaded each shared FP32 FN vector once for both rows.
It retained separate per-row K traversal, SG16 reduction, subgroup summation,
native math, Sinkhorn operations, and BF16 materialization points.

The arithmetic design worked. Both accumulator geometries passed all four B70s
bit-for-bit across **16 changed eager schedules and 70 fixed-address graph
replays**, with zero mismatches in `residual_out`, `next_post_mix`,
`next_comb_mix`, or `layer_input`.

The performance design did not work:

- six-output projection blocks: **9.143246 ms/cycle**;
- twelve-output projection blocks: **8.554636 ms/cycle**;
- same-binary incumbent control: **8.043785 ms/cycle**;
- existing exact staged pair-vector path: **8.999082 ms/cycle**.

The best pair-tiled candidate therefore regresses the complete row-tiled
87-collective/85-MHC component by **0.510851 ms/cycle**. It was rejected before
a service load, realistic suite, or LocalMaxxing submission.

## Why shared reads lost

The candidate halves nominal FN reads from eight copies to four, about 6 MiB
less per MHC boundary, but it also halves the projection grid from eight
workgroups to four. M=8 is already too narrow to occupy the 20-Xe-core B70
well. The lost workgroup-level parallelism is more expensive than the saved FN
traffic, and using twelve-output blocks only recovers part of the loss by
removing two extra projection/reduction barrier rounds.

The existing generic vector implementation independently confirms the same
boundary. It already shares FN reads across two rows in a staged projection,
but separate post/projection/stage2 commands reach 8.999082 ms/cycle, still
0.955297 ms behind the incumbent single-kernel per-row path.

## Evidence and identity

- XPU experiment commit:
  `92b194a9c152812c4e280c92a7263dbd5473898b`;
- MHC library SHA-256:
  `ddff6923fa836361d431ead23960fbe26feb45bb8d9b3c79ed526b6a60208d7a`;
- six-output candidate:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m8-pairtile-mhc-gate-20260718T2320Z`;
- same-binary control:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m8-pairtile-mhc-control-20260718T2325Z`;
- twelve-output candidate:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m8-pairtile12-mhc-gate-20260718T2330Z`;
- staged exact vector control:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m8-pair-vector-staged-gate-20260718T2335Z`.

The experimental route remains fail-closed behind
`VLLM_XPU_V4_MHC_POST_PRE_M8_PAIRTILE=1`; all launchers default it to `0` and
record it. Keep the source as exact geometry evidence, but do not enable it.

## Next decision

Do not spend another endpoint load on pair sharing or generic M=8 vector/DPAS
variants. A split-workgroup exact projection would require an extra workspace
and reducer while preserving the original 16-subgroup order; the existing
staged result shows that its sub-millisecond ceiling is unlikely to repay the
added command and synchronization cost.

Return to the larger DSpark fixed sampler/acceptance/commit boundary, where the
measured eager sampler alone is approximately 10.50 ms/cycle. Unlike another
MHC geometry variant, that boundary can remove many kernels and collectives and
has enough ceiling to matter to the 100 tok/s objective.
