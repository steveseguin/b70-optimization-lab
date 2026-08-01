# Laguna persistent chunk-4 MoE scheduler preregistration

Date: 2026-07-31 America/Toronto

Status: **closed exact component negative; do not model-run.**

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

## Result

Candidate kernel source is
`7ad886aaf00fe431810f5ad8ea1b71b585771b06`. The sealed DSO is
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/builds/persistent-chunk4-7ad886a/libgrouped_gemm_xe_2.so`
with SHA-256
`e46a2abe17d3bc691641abd87cce44003433ad0f682e791d8769cec9a7610e6a`.
The incremental production build completed in 16:39.85 with 106,783,464 KiB
maximum RSS and zero swaps.

Static BMG inspection found the separately named 128-GRF candidate and the
byte-path control in one compile. The control retained its established 679
instructions; chunk-4 grew to 705. Both retained 2 DPAS, 32 BF16 multiplies,
and the persistent atomic/barrier markers. The candidate assembly contained
the four-ID reservation path. As in the preceding dispatcher probe, all
device builds and assembly emission succeeded before the unused host stub
failed to link unresolved PyTorch symbols; that host-link failure is plumbing,
not performance evidence.

The frozen one-B70 component used one DSO for both arms, changed inputs, 200
warmups, 15 timing samples, and 40 launches per sample:

| shape | persistent control | chunk-4 | speedup |
| --- | ---: | ---: | ---: |
| W13 | 0.321221275 ms | 0.366445675 ms | 0.876586x |
| W2 | 0.183582125 ms | 0.197057175 ms | 0.931619x |
| sum | 0.504803400 ms | 0.563502850 ms | **0.895831x** |

All six raw-BF16 output comparisons were bitwise exact. Both shapes regressed
well beyond the allowed boundary, so no topology smoke, model load, endpoint
run, or LocalMaxxing action occurred.

The measured result closes coarse chunked task acquisition on these sparse
M12 grouped GEMMs. Reserving four consecutive flat tasks reduced the number
of dynamic atomic reservations but serialized ownership within a workgroup
and added 26 final instructions; the net component cost rose by 10.4%. This
does not isolate whether load-balance loss, reduced workgroup-level
parallelism, added control flow, or a combination dominates. It does show
that the incumbent per-task atomic is cheaper than this chunking trade. Do
not retry chunk sizes above one without new evidence that preserves tile-level
parallelism.

Raw result:
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/persistent-chunk4-component-7ad886a-20260801T090500Z/summary.json`.
