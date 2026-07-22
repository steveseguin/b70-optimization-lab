# Laguna S 2.1 remote-route zeroing and deterministic graph attempt — 2026-07-22

## Numbers first

The approved exact reference remains **33.08582521189141 tok/s**
(`cmrw7cn1k006jnz01gq2z981v`). Neither candidate beat it, so no
LocalMaxxing payload was staged or submitted.

| Lever | Exact result | Median tok/s 1-100 | Delta vs 33.085825 | Disposition |
|---|---:|---:|---:|---|
| A: direct-M8 remote-route zero in the GEMM | **13/13** vs canonical q=1, cache-zero, long-then-next and rollover passed | **32.59089977332271** | **-0.49492543856870 (-1.496%)** | exact negative result; default-off flag retained |
| B: fixed-rank low-width PIECEWISE capture | **1/13** vs canonical q=1; rollover failed at token 17 | **17.52411096933551** | **-15.56171424255590 (-47.04%)** | rejected and reverted |

Lever A acceptance was `4,641/12,047 = 38.5241%`, essentially unchanged
from the approved base's `4,642/12,040 = 38.5548%`.

## A: MoE launch reduction

### Change

`VLLM_XPU_LAGUNA_M8_REMOTE_ZERO=1` is default-off. For the direct M<=8
expert path it allocates the two per-layer route buffers with `empty` instead
of `zeros`. Each remote expert workgroup writes BF16 zero into its own output
tile; local experts run the unchanged DPAS calculation. This preserves the
existing deterministic 47-layer all-gather plus fixed-rank BF16 sum contract.

The component gate passed for M=1 and M=8: W1 route buffers, activation, W2
route buffers, gathered output, and remote-zero tiles all matched the old
path. Evidence:

`/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/remotezero-component-gate-20260722.json`

The full max-512 gate then matched the canonical q=1 teacher 13/13, including
the deliberate 512-token long-then-next pair and the 863-input-token rollover
row. All requests reported `cached_tokens=0`:

- run: `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/remotezero-dflash-A-c92ceca-1b2bbcb-20260722T1700Z`;
- exact comparison: `exactness.json` in that run;
- full result: `bench.json` in that run;
- primary median: **32.59089977332271 tok/s**;
- full-response median: `42.97908768644102 tok/s`;
- p10: `26.021955457683372 tok/s`;
- TTFT median: `5,628.615 ms`.

Only one fresh full-suite start was run because the candidate was already
1.496% slower than the approved record; the two-start promotion gate was not
invoked for a non-record candidate.

### Cycle profile

The structural goal succeeded but did not improve throughput:

| Quantity | Before | Remote-zero | Delta |
|---|---:|---:|---:|
| all-gather + all-reduce calls/cycle | **97 + 1 = 98** | **97 + 1 = 98** | 0 |
| named fill kernels/cycle | **96** | **1** | **-95** |
| all XPU kernel launches/cycle | **1,945** | **1,844** | **-101** |
| collective CPU API ms/cycle | 13.654 | 13.853 | +0.199 |
| noncollective XPU ms/cycle | 16.496 | 18.378 | +1.882 |
| normalized host/launch residual ms/cycle | **81.504** | **81.053** | **-0.451 (-0.553%)** |
| normal cycle ms | 111.655 | 113.284 | +1.630 |

The before host residual above is normalized to the approved full-512 run:
`6,354/1,720` emitted tokens/cycle and `33.085825` tok/s, using the published
13.654 ms collective and 16.496 ms noncollective components. The remote-zero
side uses `6,354/1,721` and `32.590900` tok/s. This is the appropriate
acceptance-matched comparison. The older published **53.833 ms** residual was
derived from the obsolete 37.59 tok/s partial-suite row with a different
acceptance distribution, so it is not directly comparable to the approved
full-512 base.

The candidate Kineto trace retained only two steady q=8 cycles after dropping
two because profiling slowed generation to about 0.1 tok/s. It is sufficient
for the exact launch counts but weak for small timing differences. oneCCL
device timestamps remain corrupt and were excluded. Evidence:

`/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/remotezero-cycle-profile-40a0528-1b2bbcb-20260722T1820Z/{summary.json,profile-derived.json}`

Conclusion: writing remote zeros inside the expert kernel really removes the
95 fill launches, but those launches were not the host bottleneck. The small
timing changes are noise-to-negative and the full-suite throughput regressed.

## B: deterministic PIECEWISE graph

### Root cause found

The original graph nondeterminism was not one bug:

1. The first AOT trace was taken at the 8,192-token profile shape. Python
   exact-path predicates were false there, so the generic reduction branch
   became frozen into the artifact.
2. Exact-path environment flags did not all participate in the compile cache
   identity.
3. The DFlash `eagle_head` graph still contains ordinary
   `torch.ops.vllm.all_reduce` calls. Draft arithmetic may vary without
   violating correctness only if the target verifier remains exact.
4. Cold compile and AOT reload select different capture coverage/artifacts.
   On the second fresh start, the loader selected AOT hash
   `6deac7fc...`, which contains ordinary all-reduces, while the just-captured
   exact-target hash `dabe62f7...` contains all-gathers plus
   `rank_order_bf16_sum` and no ordinary all-reduce.
5. Even the target artifact with fixed-rank reductions was not numerically
   identical to eager. It matched only 1/13 prompts. Therefore Inductor fusion,
   compiled operator arithmetic, or captured mutable state still changes the
   target computation beyond the reduction replacement.

The attempted default-off graph mode skipped compiled prefills above width 8,
traced width 1 and 8 with exact verifier context, made target embedding
reconstruction rank-ordered, registered flags in the compile identity, and
captured sizes 1 and 8. The first attempt failed startup because graph warmup
traced the non-exact path and `ColumnParallelLinear.forward` specialized a
dynamic input dimension through `for row in range(input_.shape[0])`. Extending
the exact context through warmup fixed that shape-guard failure.

The corrected cold start required 642 seconds of engine initialization,
including 583 seconds of compilation and 402 seconds of graph capture. Intel
IGC repeatedly failed the fused DFlash softplus/BMM Triton kernels with an
internal floating-point exception; fallback variants eventually let the
server start.

Full evidence:

- startup failure:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/deterministic-graph-A-c92ceca-1b2bbcb-20260722T1730Z/server.log`;
- runnable cold graph:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/deterministic-graph-B-40a0528-1b2bbcb-20260722T1745Z`;
- exact comparison: `exactness.json` in that run;
- second fresh-start cache-selection evidence:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/deterministic-graph-C-40a0528-1b2bbcb-20260722T1810Z/server.log`.

The two-fresh-start exact gate is **NO**. Start 1 already failed the teacher
12/13, so it could not qualify; start 2 then demonstrated non-unique AOT
artifact selection before serving. No graph number is submit-valid.

The failed graph changes were reverted on the branch. Their implementation,
compiler failures, output evidence, and revert commits remain in history.

## Builds and commits

- XPU kernels implementation: `1b2bbcb0fd4c86baa9d27b58814c920122a6ac6c`
  (`xpu: remove Laguna remote route fills`).
- Build log:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/build-laguna-remotezero-20260722.log`.
- `_xpu_C.abi3.so`: SHA256
  `87e24739de971f98a81c1dfe108a2c08033e4f4edaa8e79c5f208adb41ec702c`.
- `libgrouped_gemm_xe_2.so`: SHA256
  `880ca85cd59cb1f7803765710c879ccc34197dafe813d61a7e853a0d23338ee5`.
- Graph attempts: vLLM `c92ceca4a` and `40a0528c6`.
- Graph reverts: vLLM `194490ffe` and `f7d13121a`.
- Final vLLM schema compatibility commit: `3b13cebbe`.
- Final branch heads: vLLM `3b13cebbe`; XPU kernels `1b2bbcb`.

## Next lever

Do not spend another cycle on route-buffer initialization. The next useful A
step is a persistent/fused direct-M8 layer transaction that combines
remap/gather, W1, activation, W2 and local reduction, while retaining the
existing fixed-rank EP reconstruction. The 47 EP transactions are causally
separated by the next layer and cannot simply be coalesced across layers
without expert replication or a model-level pipeline redesign.

For graph work, first make compile-cache identity select one exact artifact
and add per-layer eager-vs-compiled tensor parity probes. Only after the first
divergent tensor is found should graph capture be retried; fixed-rank
collectives alone are insufficient.

No DeepSeek held-out pack was used, no payload was staged or submitted, no
`/mnt/fast-ai` writes were made, and DeepSeek branches plus `preserve/*` tags
were untouched.
