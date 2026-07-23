# Laguna M=8 BF16 attention native-MM occupancy experiment: exact negative

Date: 2026-07-22 (America/Toronto)

## Result first

The default-off native-M=8 BF16 attention projection selector is fully exact
and reproducible, but it is not a record candidate. The two fresh-start fixed
suite medians are **32.29886858244683** and **32.17100003502565 tok/s**. The
lower start is **1.26792996497435 tok/s (-3.791777922%)** below the approved
**33.43893 tok/s** record `cmrwot89400gqnz014oodtlbp`.

Both starts match the canonical deterministic q=1 teacher **13/13**, match
each other **13/13**, and report `cached_tokens=0` on all 26 requests. The
512-token long-then-next cross-request gate and 863-input/512-output rollover
gate pass on both starts. No LocalMaxxing payload was staged or submitted.

## Projection topology and record-path profile

Laguna does not dispatch separate Q, K, and V GEMMs on this path. It dispatches
one fused `QKVParallelLinear`, whose result slices are Q/K/V, followed by O.
TP4 has four physical projection shapes at verifier M=8:

- 12 full-attention layers: QKV `[8,3072] x [3072,2048]`, with output slices
  Q=1536, K=256, V=256; O `[8,1536] x [1536,3072]`;
- 36 sliding-attention layers: QKV `[8,3072] x [3072,2816]`, with output
  slices Q=2304, K=256, V=256; O `[8,2304] x [2304,3072]`.

The retained record trace totals **2.9188377 ms/target cycle** for these four
families. Trace time and trace-implied logical BF16 weight bandwidth are the
least-perturbed timing view; the EU and actual DRAM-read columns are averages
of four cold matched ComputeBasic queries on card 0.

| Physical projection | Layers | Trace ms/layer | ms/cycle | Logical weight GB/s | EU active | Actual DRAM read GB/s |
|---|---:|---:|---:|---:|---:|---:|
| Full fused QKV | 12 | 0.0268161 | 0.3195581 | 469.23 | 10.401% | 173.640 |
| Sliding fused QKV | 36 | 0.0352871 | 1.2615130 | 490.31 | 10.785% | 168.469 |
| Full O | 12 | 0.0227033 | 0.2705478 | 415.67 | 11.301% | 168.052 |
| Sliding O | 36 | 0.0298523 | 1.0672188 | 474.19 | 10.147% | 199.550 |

These projections are strongly issue/occupancy starved relative to the
interleaved INT4 expert kernels, which reached roughly 48% EU active. The
sliding QKV family has the most absolute headroom: it is the largest physical
bucket at **1.2615130 ms/cycle**, and its Q slice is nine times wider than each
GQA K/V slice. Sliding O is second at **1.0672188 ms/cycle**.

For attribution only, standalone logical projection diagnostics were also
profiled. They are not additive to the physical fused-QKV time and did not run
in the server:

| Logical diagnostic | Shape | EU active | ComputeBasic query ms | Actual DRAM read GB/s |
|---|---|---:|---:|---:|
| Full Q | 3072->1536 | 9.275% | 0.054106 | 176.549 |
| Sliding Q | 3072->2304 | 9.638% | 0.088452 | 161.611 |
| K | 3072->256 | 5.855% | 0.021762 | 77.338 |
| V | 3072->256 | 6.121% | 0.023790 | 69.957 |

## Default-off occupancy change

The new selector is:

```text
VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM=1
```

It fails closed unless exact speculative attention is active, the layer is a
target Laguna QKV/O projection, the verifier has exactly eight rows, input and
weight are BF16, and the shape is one of the four physical shapes above. It
replaces the record path's expanded stride-zero batch of eight M=1 BMMs with a
native `torch.mm([8,K], [K,N])`. This exposes the M/N tile grid directly to
oneDNN without changing source operands, output dtype, bias handling, target
weights, or quantization. Bitwise gates, rather than an assumed primitive
contract, establish the observed rounding identity.

vLLM commit:

```text
b52d6a5925ebf3dd8e32763491863797e0d0e1b1
xpu: use exact M8 MM for Laguna BF16 attention
```

No XPU-kernel source or binary rebuild was needed because both alternatives
are PyTorch/oneDNN BF16 primitives. The unchanged XPU-kernel identity is:

```text
210a6eb604500c80bc5989d4b9fc59e75f1bb316
78a7218de45ee46b3734dc977c0d6115607ff7536706c0be2d4728b4ca2c40be  libgrouped_gemm_xe_2.so
625af4bbe792effde9f2f54c319f807a5c49b9756be313f9307d90da9ff5149e  _xpu_C.abi3.so
f222d3e2d2a8a331e3c85f12e0d02a17aa7a89147bbbcc8ac2c2a816629a405f  _moe_C.abi3.so
```

## Four-card component exactness and before/after counters

Changing inputs and weights were tested for 16 epochs per shape and rank.
Every physical QKV result, its Q/K/V slices, and every O result is bitwise
identical: **640/640** physical-path checks. The standalone logical Q/K/V
diagnostics add 256 checks, for **896/896** overall across four cards.

Matched cold ComputeBasic queries below include a synchronization boundary
after each selected kernel. The query itself perturbs absolute time, so these
numbers are for matched before/after hardware diagnosis, not cycle accounting.

| Physical projection | EU active record -> native M8 | Query ms record -> native M8 | DRAM read GB/s record -> native M8 |
|---|---:|---:|---:|
| Full fused QKV | 10.401% -> 10.445% | 0.073229 -> 0.092781 | 173.640 -> 137.073 |
| Sliding fused QKV | 10.785% -> 10.748% | 0.103571 -> 0.096473 | 168.469 -> 180.850 |
| Full O | 11.301% -> 11.532% | 0.056758 -> 0.068432 | 168.052 -> 139.375 |
| Sliding O | 10.147% -> 11.311% | 0.071565 -> 0.082472 | 199.550 -> 173.219 |

The four-card L3-hot enqueue-amortized component timing superficially improves
all shapes, which is why the cold counters and full gate were mandatory:

| Physical projection | Four-card mean record -> native M8 ms |
|---|---:|
| Full fused QKV | 0.052602 -> 0.040375 |
| Sliding fused QKV | 0.050504 -> 0.036843 |
| Full O | 0.047761 -> 0.035243 |
| Sliding O | 0.047921 -> 0.035220 |

Native M8 therefore did not reproduce the expert-kernel occupancy mechanism.
It raised EU activity materially only for sliding O, reduced it slightly for
sliding QKV, and slowed three of four cold counter queries. The hot apparent
win is primitive-launch/cache behavior and does not survive the endpoint.

Component/profile evidence:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/bf16-attn-mm-component-6a570e70b-210a6eb-20260723/
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/bf16-attn-mm-counters-r4-5b8ac553-210a6eb-20260723/
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/bf16-attn-baseline-cold-6a570e70b-210a6eb-20260723/
```

The `5b8ac553` counter-directory label was assigned before the focused vLLM
commit was amended. The tested source commit is `b52d6a592`; the isolated
PyTorch primitives and unchanged XPU binaries are captured above.

## Full two-start exact and performance gate

Both fresh starts used TP4/EP4, one active sequence, eager exact DFlash depth
7, BF16 KV, `--no-async-scheduling`, seed 1, `enable_thinking=false`, no prefix
cache/history/response reuse, and `max_tokens=512` on the fixed 13-prompt
realistic suite.

| Gate | Start A | Start B |
|---|---:|---:|
| Teacher token arrays | 13/13 | 13/13 |
| `cached_tokens=0` | 13/13 | 13/13 |
| 512-token long-then-next | 2/2 | 2/2 |
| 863-input/512-output rollover | 1/1 | 1/1 |
| Cross-start token arrays | 13/13 | 13/13 |
| Median tok/s, tokens 1-100 | **32.29886858244683** | **32.17100003502565** |
| p10 / mean tok/s | 25.772319 / 37.919609 | 25.676389 / 37.563660 |
| Median TTFT, ms | 5719.562 | 5792.712 |
| Median full after-TTFT tok/s | 42.328189 | 42.138449 |
| Median wall full tok/s | 27.259008 | 27.012716 |
| Acceptance | 4642/12040 (38.554817%) | 4644/12026 (38.616331%) |
| Delta from 33.43893 | -1.140061 (-3.409384%) | -1.267930 (-3.791778%) |

Evidence:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/bf16-attn-mm-dflash-A-b52d6a592-210a6eb-20260723T011109Z/
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/bf16-attn-mm-dflash-B-b52d6a592-210a6eb-20260723T012000Z/
```

## Disposition and next lever

The experiment is preserved behind a default-off flag; the launcher defaults
it to zero. Runtime was reverted by stopping the candidate service, and the
record flags remain the restoration path. No payload exists because the lower
start does not exceed 33.43893.

The recommended next bounded exact lever is the **1.42 ms/cycle attention
non-GEMM bucket**, beginning with a trace split of target QK, Q/K RMSNorm, and
RoPE and then one default-off fusion that preserves operation and rounding
order. It is larger than shared-expert/router GEMM (1.01 ms/cycle) and
TopKGating (0.56 ms/cycle). If an arithmetic-order-preserving attention fusion
is not available, shared-expert/router GEMM occupancy is the safer fallback.

No DeepSeek held-out pack was used and nothing was written under
`/mnt/fast-ai`. Protected DeepSeek option4-decoder branches and `preserve/*`
tags were unchanged. Postflight stopped the endpoint and workers; `xpu-smi ps`
showed only its own probe on all four cards.
