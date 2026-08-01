# Laguna persistent chunk-4 MoE scheduler preregistration

Date: 2026-07-31 America/Toronto

Status: preregistered before source change, build, or device execution.

## Distinct premise

The exact M12 grouped-GEMM scheduler evidence now separates two facts:

- replacing the persistent distributor with fixed flattened or expert grids
  loses (`0.916350x`, `0.974647x`, and `0.929750x` variants);
- retaining the persistent distributor but replacing the 64-count scan with a
  four-int worklist also loses (`0.987679x`).

The remaining dynamic scheduler cost is task acquisition. The exact
`w4a16_policy_m_8` route uses 64-thread workgroups. A B70 exposes 32
subslices, so the launch creates `32 * 512 / 64 = 256` initial persistent
workgroups. In the frozen component corpus, every active expert has at most
six rows and therefore one M tile. W13 has 51 active experts and 32 N tiles,
or 1,632 flat tasks; W2 has 57 active experts and 48 N tiles, or 2,736 flat
tasks. The incumbent consequently needs multiple global-atomic acquisition
waves after the initial 256 tasks.

The candidate retains the incumbent launch geometry, count scan, expert
grouping, row order, weights, transposed scales, GRF128 kernel, local barrier,
N tiling, GEMM arithmetic, accumulation, and stores. It changes the persistent
atomic reservation from one flat task ID to four consecutive IDs. A workgroup
processes those four IDs serially before acquiring another chunk. Consecutive
IDs normally remain within one M tile's N sweep, so the treatment may also
retain expert/weight locality without giving up dynamic distribution.

This is not a fixed grid, direct expert scheduler, compact metadata worklist,
or arithmetic change. Every flat task still has exactly one owner, and its
tile coordinate and math are unchanged.

## Gates

1. Start from protected kernel source `99886d783372e621941228250091dc8ebdc1595d`.
   Add one default-off literal selector and a separately named chunk-4 GRF128
   kernel. Selector off must leave the promoted path unchanged.
2. Focused source/static checks must show the candidate still uses the
   persistent atomic and local barrier, reserves exactly four IDs, and retains
   the exact 2-DPAS/32-BF16-multiply body. No production remap change is
   allowed.
3. Use one DSO for both arms on the frozen changed-input physical-transposed-
   scale W13/W2 corpus. Require 6/6 raw-BF16 equality under 200 warmups and
   15x40 timing, no per-shape regression, and at least `1.05x` summed speedup.
4. Stop and preserve the result if the component misses `1.05x`. Do not load
   the model or run an endpoint.
5. A component pass authorizes a four-rank topology smoke only. It must retain
   146/145 target, 14/13 draft, cache-zero, normal acceptance, selector
   evidence on every rank, and clean teardown.
6. Only a passed smoke authorizes one cold frozen 13-prompt endpoint leg. The
   first valid result stands.

No model, INT4 weights, BF16 KV, speculative width/depth, verification,
sampling, prompts, teacher, cache, metric, retry, warmup generation, graph
capture window, or scoring window may change. No reboot, reset, FLR, driver
reload, or privileged recovery is authorized.
