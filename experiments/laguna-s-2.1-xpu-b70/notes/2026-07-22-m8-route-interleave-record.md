# Laguna M8 route-interleaved INT4 expert GEMM: exact two-start record

Date: 2026-07-22

## Result first

Candidate B is an exact, reproducible two-fresh-start record candidate. Its
fixed-suite medians are **33.438926675602126** and
**33.546438841532144 tok/s** for generated tokens 1-100 after TTFT. The lower
start exceeds the approved **33.26756407958298 tok/s** record
`cmrwlyxez00f4nz01zefturuv` by **0.1713625960191436 tok/s (+0.515104%)**.

Both starts matched the canonical deterministic q=1 target teacher **13/13**,
matched each other **13/13**, and reported `cached_tokens=0` on all 26
requests. Long-then-next passed **2/2** and the 863-input-token rollover row
passed **1/1** on each start. A LocalMaxxing payload is staged but was **not
submitted**; Claude owns submission.

## Fresh record-path re-profile

The approved fused-W1 + route-parallel-W2 record path was restarted and
profiled before changing source. The trace retained nine steady q=8 contexts
per rank after dropping the first context.

- whole noncollective XPU: **18.377500 ms/cycle**;
- aggregate unnamed/other noncollective: **13.409344 ms/cycle**;
- fused W1+SiLU: **6.488383 ms/cycle**, **0.138051 ms/layer**;
- route-parallel W2: **3.330374 ms/cycle**, **0.070858 ms/layer**;
- fixed-order gather: **0.441856 ms/cycle**, **0.009401 ms/layer**; and
- named routed MoE: **10.260613 ms/cycle** before the ambiguous zero fill.

Thus `other noncollective` is the largest aggregate bucket, but W1 is the
largest identifiable and actionable kernel bucket, almost twice W2. The first
privileged ComputeBasic pass on the unmodified record binaries measured W1 at
**41.62% EU active / 86.41% thread occupancy / 515.67 GB/s DRAM read** and W2
at **44.69% / 94.33% / 535.40 GB/s**. W1 was therefore the primary occupancy
target; W2 was included because the same safe enumeration applied to both.

Profile evidence:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/candidate-b-record-reprofile-6a570e70b-20cfa3a-20260722T1753Z/summary.json
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/candidate-b-record-counter-baseline-6a570e70b-20cfa3a-20260722/
```

## Occupancy change and arithmetic contract

The new default-off selector is:

```text
VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=1
```

It fails closed unless both the exact batched MoE and the approved fused-W1 +
route-W2 path are enabled. It changes only workgroup enumeration for W1 and
W2. The record path exhausts N tiles for one route before moving to the next;
the candidate cycles across all 80 `[8 rows * top-10]` routes at each N tile:

```text
record:    route = gid / n_tiles;  n_tile = gid % n_tiles
candidate: route = gid % 80;       n_tile = gid / 80
```

Every workgroup still owns the identical route and N tile. There is no true
M=8 arithmetic merge: each routed expert remains an independent M=1 numerical
lane. Packed signed INT4 dequantization, group-32 BF16 scales, K32 traversal,
FP32 DPAS accumulation order, BF16 gate/up stores, BF16 SiLU/multiply
rounding, W2 BF16 stores, remote-route zero semantics, and fixed slot-order
FP32-weighted gather are unchanged.

## Source, build, and binary identity

- vLLM branch: `experiment/laguna-s-2.1-xpu-bringup-20260721`
- vLLM commit: `6a570e70b2c1ccce3a42f3396e1bd22b0a4a8191`
- XPU-kernel branch: `experiment/laguna-s-2.1-fwht-20260721`
- XPU-kernel commit: `210a6eb604500c80bc5989d4b9fc59e75f1bb316`
  (`xpu: interleave Laguna M8 routed workgroups`)

Focused rebuild:

```bash
source /opt/intel/oneapi/setvars.sh
ninja -C build/temp libgrouped_gemm_xe_2.so _xpu_C.abi3.so
```

Build log and installed binary identities:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/build-laguna-m8-route-interleave-20260722.log
78a7218de45ee46b3734dc977c0d6115607ff7536706c0be2d4728b4ca2c40be  libgrouped_gemm_xe_2.so
625af4bbe792effde9f2f54c319f807a5c49b9756be313f9307d90da9ff5149e  _xpu_C.abi3.so
f222d3e2d2a8a331e3c85f12e0d02a17aa7a89147bbbcc8ac2c2a816629a405f  _moe_C.abi3.so
```

The candidate binaries are archived at:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/binaries/m8-route-interleave-210a6eb-20260722/
```

## Four-card component exactness and counters

The tracked harness changes random inputs and local/remote routes at M=1 and
M=8 for eight epochs/shape/rank. Final MoE outputs plus every local W1,
post-SiLU activation, and W2 boundary are bitwise identical.

| Rank | Exact | W1 record -> candidate ms | W2 record -> candidate ms | Full routed record -> candidate ms |
|---:|---:|---:|---:|---:|
| 0 | 16/16 | 0.355714 -> 0.344023 | 0.170459 -> 0.164758 | 0.559039 -> 0.532155 |
| 1 | 16/16 | 0.359763 -> 0.347601 | 0.172379 -> 0.167817 | 0.564795 -> 0.543147 |
| 2 | 16/16 | 0.359729 -> 0.345864 | 0.171549 -> 0.166740 | 0.560943 -> 0.537929 |
| 3 | 16/16 | 0.361694 -> 0.346691 | 0.171944 -> 0.166880 | 0.563030 -> 0.539339 |
| Mean | **64/64** | **0.359225 -> 0.346045** | **0.171583 -> 0.166549** | **0.561952 -> 0.538143** |

Mean W1 improves **3.669%**, W2 improves **2.934%**, and the complete routed
component improves **4.237%**. Matched ComputeBasic queries used a synchronization
boundary after every selected kernel so adjacent traffic was not attributed to
the query.

| Kernel | EU active | Thread occupancy | DRAM read GB/s | DRAM write GB/s | Query time |
|---|---:|---:|---:|---:|---:|
| W1 record | 43.769% | 88.090% | 534.124 | 0.941 | 0.363475 ms |
| W1 interleaved | 47.723% | 86.666% | 502.278 | 1.126 | 0.345965 ms |
| W2 record | 46.527% | 93.967% | 528.579 | 1.973 | 0.171486 ms |
| W2 interleaved | 49.126% | 93.542% | 517.429 | 2.092 | 0.163862 ms |

EU activity rises by **3.954 points** for W1 and **2.599 points** for W2. DRAM
read rate falls while completion time improves, indicating the win is not more
DRAM traffic; route interleave improves issue opportunity and/or cache locality.

Evidence:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/m8-route-interleave-component-6a570e70b-210a6eb-20260722/
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/m8-route-interleave-counters-6a570e70b-210a6eb-20260722/
```

## Full two-start exact and performance gate

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
| Median tok/s, tokens 1-100 | **33.438927** | **33.546439** |
| p10 / mean tok/s | 26.271576 / 38.363995 | 26.545802 / 38.761945 |
| Median TTFT, ms | 5625.603 | 5590.080 |
| Median full after-TTFT tok/s | 43.281862 | 43.599339 |
| Median wall full tok/s | 27.247814 | 27.676431 |
| Acceptance | 4643/12033 (38.5856%) | 4642/12040 (38.5548%) |

Evidence:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/m8-route-interleave-dflash-A-6a570e70b-210a6eb-20260722T223950Z/
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/m8-route-interleave-dflash-B-6a570e70b-210a6eb-20260722T224721Z/
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/m8-route-interleave-two-start-exactness-6a570e70b-210a6eb-20260722.json
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/m8-route-interleave-cross-start-repro-6a570e70b-210a6eb-20260722.json
```

Start A's `identity.txt` captures the full runtime, model, binary, flag, and
artifact identity. The compact tracked result is
`data/laguna-s-2.1-m8-route-interleave-record-20260722.json`.

## Staged payload and disposition

The queue is staged at:

```text
data/localmaxxing-laguna-s-2.1-int4-b70-dflash-m8-route-interleave-33.439tok-20260722.queue.json
```

`engineFlags.attentionBackend` is 40 characters, below the API's 64-character
cap. No LocalMaxxing POST was made. The selector remains default-off in source.
The next bounded exact lever after external review is attention BF16 QKVO or
sliding-window decode; deeper DFlash acceptance policy is the independent
algorithmic lane. W1 occupancy is no longer the untested follow-up because this
candidate improves both W1 and W2.

No DeepSeek held-out pack or `/mnt/fast-ai` write was used. The protected
DeepSeek option4-decoder and `preserve/*` refs were unchanged. Postflight
stopped the endpoint and workers; `xpu-smi ps` showed only its own probe on all
four cards.
