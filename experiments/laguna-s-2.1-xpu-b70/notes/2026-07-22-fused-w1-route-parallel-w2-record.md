# Laguna fused W1 plus route-parallel W2: exact two-start record

Date: 2026-07-22

## Result first

Candidate A is an exact, two-fresh-start record candidate. Its fixed-suite
medians are **33.30342426046781** and **33.26756407958298 tok/s** for generated
tokens 1-100 after TTFT. The lower start exceeds the approved
**33.08582521189141 tok/s** Laguna record by **0.18173886769157122 tok/s
(+0.549295%)**. The cross-start spread is only 0.1078%. A LocalMaxxing payload
is staged but was **not submitted**; Claude owns submission.

Both fresh starts matched the canonical deterministic q=1 target teacher
**13/13**, matched each other **13/13**, and reported `cached_tokens=0` on all
26 requests. The deliberate 512-token row followed immediately by the next
request passed **2/2** on both starts. The 863-input-token rollover row generated
512 tokens and passed **1/1** on both starts.

Candidate B was audited but not implemented because Candidate A cleared the
required lower-start record floor. Its bounded fallback remains a default-off,
W2-only route-interleaved workgroup enumeration with unchanged N64 arithmetic.

## Candidate and exactness contract

The default-off selector is:

```text
VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=1
```

It requires `VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1`, is mutually exclusive with
the preserved full fused transaction, rejects the failed remote-zero mode, and
fails closed unless the activation is Laguna's plain unclamped SiLU.

The path retains the previously proven fused W1+SiLU kernel and persistent M8
BF16 scratch, then restores the incumbent W2 arithmetic and concurrency:

1. fused INT4 W1 gate/up with the incumbent FP32 DPAS accumulation and BF16
   gate/up stores;
2. BF16 reread, BF16 SiLU rounding, and BF16 multiply rounding in the same
   workgroup;
3. zero the persistent W2 route-output slice so remote routes remain exact;
4. launch the incumbent route-parallel group-32 INT4 W2 kernel unchanged; and
5. run the incumbent fixed slot-order FP32-weighted `moe_gather` unchanged.

The zero fill is required. W2 skips remote routes while the fixed route map
still presents all ten slots to the gather, so stale persistent remote rows
would be incorrect.

## Source, build, and binary identity

- vLLM branch: `experiment/laguna-s-2.1-xpu-bringup-20260721`
- vLLM commit: `6a570e70b2c1ccce3a42f3396e1bd22b0a4a8191`
  (`xpu: identify Laguna fused-W1 route-W2 path`)
- XPU-kernel branch: `experiment/laguna-s-2.1-fwht-20260721`
- XPU-kernel commit: `20cfa3aef35d1daa2c57f3dccaf7ce7d552f6751`
  (`xpu: split Laguna fused W1 from route-parallel W2`)

Only the changed libraries were requested:

```bash
source /opt/intel/oneapi/setvars.sh
ninja -C build/temp libgrouped_gemm_xe_2.so _xpu_C.abi3.so
```

Build log:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/build-laguna-fused-w1-route-w2-20260722.log
```

Candidate binary SHA-256 identities:

```text
445e2fd26b94b9d6192551239f65e4a54074ee7ae329ee6067b60ebee6232a3d  libgrouped_gemm_xe_2.so
f776587b0e2ea9f5b1f12f85d441c6373d1e29e9d23fdd979fa3a060291f63c1  _xpu_C.abi3.so
```

The exact pair and preinstall baseline pair are archived under:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/binaries/fused-w1-route-w2-6a570e70b-20cfa3a-20260722/
```

## Four-card component gate

The updated tracked harness runs changing random inputs and changing local and
remote routes at M=1 and M=8 for eight epochs/shape/rank. All final outputs and
all local W1, activation, and W2 boundaries were bitwise identical.

| Rank | Exact | Record path ms/layer | Candidate ms/layer | Delta |
|---:|---:|---:|---:|---:|
| 0 | 16/16 | 0.538958 | 0.553042 | +0.014084 |
| 1 | 16/16 | 0.546988 | 0.549986 | +0.002998 |
| 2 | 16/16 | 0.551744 | 0.550917 | -0.000827 |
| 3 | 16/16 | 0.543720 | 0.550307 | +0.006588 |
| Mean | **64/64** | **0.545352** | **0.551063** | **+0.005711** |

The isolated projection across 47 MoE layers is **25.631558 -> 25.899973
ms/cycle**, a **+0.268415 ms** regression. This synthetic gate deliberately has
a high local-route density and is supporting evidence, not the endpoint result.

Routed launches fall from **6 to 4/layer**, or **282 -> 188/cycle**. At M=8,
the prior fully fused/serialized W2 exposed only `8 * 48 = 384` workgroups/card
and looped through ten expert slots. Candidate A restores
`8 * 10 * 48 = 3,840` independent W2 workgroups/card: **10x route-parallel work
availability** with the same 8x64x32 tile, four SG16 subgroups, GRF256, K order,
dequantization, DPAS accumulation, and BF16 store.

Component evidence:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/fused-w1-route-w2-component-6a570e70b-20cfa3a-20260722/rank-{0,1,2,3}.json
```

## Endpoint cycle profile

The separate post-gate trace retained nine steady q=8 contexts/rank after
dropping the first context. Corrupted oneCCL device timestamps remain excluded.

- whole noncollective XPU: **18.232229 ms/cycle**;
- fused W1+SiLU: **6.584561 ms/cycle**;
- separate route-parallel W2: **3.358476 ms/cycle**;
- fixed-order gather: **0.443224 ms/cycle**;
- named routed-MoE kernels: **10.386260 ms/cycle** before the W2 zero fill.

The generic BF16 zero-fill kernel shares its name with unrelated copy kernels,
so it cannot be isolated safely from this trace. Thus 10.386260 ms/cycle is an
explicit lower bound for Candidate A's routed component. The incumbent routed
component was 9.077583 ms/cycle including both fills, activation, W1, W2, and
gather. The trace therefore does **not** show a device-time MoE win; the endpoint
record is the required two-start empirical result, and the small margin must
not be extrapolated beyond this exact recipe.

Profile:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/fused-w1-route-w2-dflash-cycle-profile-6a570e70b-20cfa3a-20260722/summary.json
```

## Full two-start gate

Both starts used eager exact DFlash, BF16 KV, `--no-async-scheduling`, seed 1,
`enable_thinking=false`, no prefix/cache/history/response reuse, one active
sequence, and `max_tokens=512` on the fixed realistic suite.

| Gate | Start A | Start B |
|---|---:|---:|
| Teacher token arrays | 13/13 | 13/13 |
| `cached_tokens=0` | 13/13 | 13/13 |
| 512-token long-then-next | 2/2 | 2/2 |
| 863-token rollover | 1/1 | 1/1 |
| Cross-start token arrays | 13/13 | 13/13 |
| Median tok/s, tokens 1-100 | **33.303424** | **33.267564** |
| p10 / mean tok/s | 26.508395 / 38.644057 | 26.433749 / 38.778972 |
| Median TTFT, ms | 5451.565 | 5522.227 |
| Median full after-TTFT tok/s | 42.599711 | 43.704754 |
| Median wall full tok/s | 27.757301 | 27.657754 |
| Acceptance | 4644/12026 (38.6163%) | 4640/12054 (38.4934%) |

Evidence:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/fused-w1-route-w2-dflash-A-6a570e70b-20cfa3a-20260722T205343Z/
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/fused-w1-route-w2-dflash-B-6a570e70b-20cfa3a-20260722T210400Z/
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/fused-w1-route-w2-two-start-exactness-6a570e70b-20cfa3a-20260722.json
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/fused-w1-route-w2-cross-start-repro-6a570e70b-20cfa3a-20260722.json
```

The full identity is in Start A's `identity.txt`. The compact tracked result is
`data/laguna-s-2.1-fused-w1-route-w2-record-20260722.json`.

## Staged payload and disposition

The queue is staged at:

```text
data/localmaxxing-laguna-s-2.1-int4-b70-dflash-fused-w1-route-w2-33.268tok-20260722.queue.json
```

`engineFlags.attentionBackend` is 45 characters, below the API's 64-character
cap. The queue passed the local dry-run preflight. No LocalMaxxing POST was
made.

Candidate A remains default-off in source but its exact binaries remain
installed and archived for reproduction. Candidate B was not needed. If this
row fails independent external acceptance despite the mandated two starts, the
next bounded exact lever is the audited W2-only N64 route-interleaved workgroup
enumeration; if neutral, screen N128+interleave before N32. Do not use GRF128.

All model, cache, build-log, trace, and run writes remained on CorsairExternal.
No DeepSeek held-out pack or `/mnt/fast-ai` write was used. Postflight stopped
the endpoint and left all four cards free.
