# Laguna fused direct-M8 expert transaction: exact, but not a record

Date: 2026-07-22

## Result first

The guarded persistent direct-M<=8 transaction is bitwise exact, including the
full two-start DFlash contract, but it is **not promoted**. The lower of the two
fresh-start medians is **33.00802744924381 tok/s**, below the approved
**33.08582521189141 tok/s** record by 0.077798 tok/s (-0.2351%). The other
fresh start reached 33.90821876754645 tok/s, but the 2.7272% cross-start spread
is not a reproducible record. No LocalMaxxing payload was staged or submitted.

The four-card component gate passed 64/64 changing-input cases, including the
BF16 W1, activation, W2, and final output boundaries. The full realistic gate
matched the canonical deterministic q=1 teacher 13/13 on each of two fresh
starts, matched cross-start 13/13, kept cached_tokens=0 for all 26 requests,
and passed the 512-token cross-request pair plus the 863-input-token rollover
row on both starts.

The cycle profile explains the speed result. The routed transaction drops from
six device launches per MoE layer to two, or **282 -> 94 launches** across the
47 MoE layers, but routed-MoE device time rises from **9.077583 to 10.388394
ms/cycle** (+1.310811 ms, +14.4401%). Whole noncollective XPU time rises from
**16.496175 to 18.371188 ms/cycle** (+1.875013 ms, +11.3664%). The fused W2
kernel's fixed slot-0..9 loop preserves arithmetic but serializes expert-slot
work that the incumbent route-parallel W2 kernel runs concurrently.

## Implementation and guard

The default-off selector is:

```text
VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION=1
```

It requires `VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1`, refuses the rejected remote
zero mode, and fails closed unless the activation is the plain Laguna SiLU
path without a clamp. The incumbent implementation remains intact and the
launcher defaults the new selector to zero.

Each `XpuFusedMoE` instance owns persistent maximum-M8 BF16 scratch for W1,
activation, and W2 route outputs. Under the required one-active-generation,
in-order-stream contract the scratch can be sliced for M=1..8 without an
allocation or zero fill on each layer invocation. The native call submits:

1. a paired W1 gate/up INT4 kernel that retains group-32 dequantization, FP32
   DPAS accumulation, BF16 W1 stores, BF16 reread, BF16 SiLU rounding, and BF16
   multiply rounding; and
2. a W2 plus local-reduce kernel that retains the BF16 W2 route store and
   reread, then accumulates FP32 router-weight products in fixed slot order
   0..9 before the single BF16 output cast.

Remote routes are skipped because only local routes are consumed, eliminating
the two route-output fills. The modular finalizer aliases the already-complete
output under the flag, eliminating its redundant output copy. No atomics,
changed dequantization, reordered reduction, or relaxed rounding were used.

Source commits:

- vLLM: `9164595cd2141c897358d6c58717061bfbe13e28`
  (`xpu: identify Laguna fused M8 transaction`)
- XPU kernels: `d0b5b1539dacc4a1c1edf3b0f4ee1578e34d9d16`
  (`xpu: fuse Laguna deterministic M8 expert transaction`)

The changed libraries were built incrementally with:

```bash
source /opt/intel/oneapi/setvars.sh
ninja -C build/temp libgrouped_gemm_xe_2.so _xpu_C.abi3.so
```

Build log:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/build-laguna-fused-m8-20260722.log
```

Candidate rebuild SHA-256 identities:

```text
cc9ef95c3fd2704e944cfc53cb3319fe722e0da39f90ddfbff03653e9d2795c8  libgrouped_gemm_xe_2.so
2dc852b8fb832391b0761f4b573dcf1a9b3a4450f2de350089d7d4705480d609  _xpu_C.abi3.so
```

After the negative promotion decision, those exact binaries were archived at:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/binaries/fused-m8-9164595-d0b5b15-20260722/
```

The installed package was restored to its pre-experiment libraries. Their
SHA-256 identities are `880ca85cd59cb1f7803765710c879ccc34197dafe813d61a7e853a0d23338ee5`
for `libgrouped_gemm_xe_2.so` and
`87e24739de971f98a81c1dfe108a2c08033e4f4edaa8e79c5f208adb41ec702c`
for `_xpu_C.abi3.so`.

## Four-card component exactness and timing

The tracked harness is
`experiments/laguna-s-2.1-xpu-b70/tools/gate_laguna_fused_m8.py`. It creates
full Laguna-shaped random INT4 weights and group-32 BF16 scales, changes hidden
states and local/remote routes every epoch, and checks M=1 and M=8. Each rank
ran eight epochs per shape independently on one physical B70.

| Rank | Exact outputs | Incumbent ms/layer | Candidate ms/layer | Delta |
|---:|---:|---:|---:|---:|
| 0 | 16/16 | 0.546273 | 0.566400 | +0.020127 |
| 1 | 16/16 | 0.543333 | 0.569249 | +0.025916 |
| 2 | 16/16 | 0.535820 | 0.569327 | +0.033507 |
| 3 | 16/16 | 0.542173 | 0.569039 | +0.026866 |
| Mean | 64/64 | 0.541900 | 0.568504 | +0.026604 |

Every local W1, activation, and W2 intermediate was also bitwise equal. The
mean isolated result projects from 25.469293 to 26.719678 ms across 47 layers,
a +1.250385 ms/cycle regression. This synthetic component test has a higher
local-route density than the endpoint and is therefore supporting evidence,
not a replacement for the endpoint cycle trace.

Evidence:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/fused-m8-component-20260722/rank-{0,1,2,3}.json
```

## Full two-start exactness and throughput

Both starts used eager exact DFlash, `--no-async-scheduling`, BF16 KV, seed 1,
`enable_thinking=false`, one active sequence, no prefix cache, no history or
response reuse, and `max_tokens=512` on the fixed 13-prompt realistic suite.

| Gate | Fresh start A | Fresh start B |
|---|---:|---:|
| Teacher token arrays | 13/13 | 13/13 |
| `cached_tokens=0` | 13/13 | 13/13 |
| 512-token long-then-next | 2/2 | 2/2 |
| 863-token rollover | 1/1 | 1/1 |
| Cross-start token arrays | 13/13 | 13/13 |
| Median tok/s, tokens 1-100 after TTFT | **33.00802744924381** | **33.90821876754645** |
| p10 / mean tok/s | 26.427645 / 39.049322 | 26.850389 / 39.343214 |
| Median TTFT, ms | 5324.536 | 5345.547 |
| Median full response tok/s after TTFT | 44.330361 | 44.070494 |
| Median wall full-response tok/s | 28.492601 | 28.194742 |

Both runs accepted 4,643 of 12,033 drafted tokens, or **38.585556%**. The
matching acceptance and token arrays rule out acceptance luck or a changed
answer as the cause of the speed spread.

Evidence:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/bulletproof-q1-canonical-cb616c6-6fc06b0-20260722T142908Z/bench.json
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/fused-m8-dflash-A-9164595-d0b5b15-20260722T2000Z/bench.json
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/fused-m8-dflash-B-9164595-d0b5b15-20260722T2010Z/bench.json
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/fused-m8-two-start-exactness-9164595-d0b5b15-20260722.json
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/fused-m8-cross-start-repro-9164595-d0b5b15-20260722.json
```

## Cycle profile and disposition

The candidate trace retained five steady q=8 verifier contexts per rank after
dropping the first context. As in the incumbent profile, corrupted oneCCL
device timestamps are excluded. Cross-rank mean XPU timings are:

| Scope | Incumbent ms/cycle | Candidate ms/cycle | Delta |
|---|---:|---:|---:|
| W1/W2 + activation + fills + local gather/reduce | 9.077583 | 10.388394 | +1.310811 (+14.4401%) |
| Whole noncollective XPU | 16.496175 | 18.371188 | +1.875013 (+11.3664%) |

The candidate transaction itself splits into 6.410085 ms/cycle for fused
W1+SiLU and 3.978309 ms/cycle for W2+fixed local reduction. It launches each
kernel once per MoE layer: 47 + 47 = 94 launches. The incumbent component
launches two fills, W1, activation, W2, and gather per layer: 6 x 47 = 282.
Its separate modular finalizer copy is also removed by the candidate, but is
not counted in the component launch comparison.

Profiles:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/batched-exact-dflash-cycle-profile-4a25d9a-6fc06b0-20260722/{summary.json,profile-derived.json}
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/fused-m8-dflash-cycle-profile-9164595-d0b5b15-20260722/summary.json
```

The candidate is preserved in focused commits but operationally reverted: the
flag is default-off, the incumbent code path is intact, no service is running,
and all four render nodes are free. The approved 33.085825 tok/s record remains
authoritative.

The next exact-safe lever should preserve route-parallel W2 occupancy. The
most direct follow-up is an INT4 M=8 expert GEMM occupancy/tiling pass,
especially W2 N=3072, or a split candidate that retains only persistent scratch
plus fused W1+SiLU while leaving W2 and fixed-order gather separate. If that
does not pay, move to exact attention QK/LSE/PV or improve DFlash acceptance.
Do not retry graph capture, route-buffer zeroing, or collective coalescing.
