# Laguna exact M=8 Q/K RMSNorm + RoPE fusion: two-start speed negative

Date: 2026-07-22 (America/Toronto; runs completed after 00:00 UTC)

## Result first

The default-off exact M=8 fusion is bitwise correct and materially reduces the
isolated component, but it is **not a reproducible record**. Fresh-start
medians were **34.233360069506844** and **33.19070223154202 tok/s**. The
required lower start is **0.2482277684579799 tok/s (-0.7423317%)** below the
approved **33.43893 tok/s** record `cmrwot89400gqnz014oodtlbp`.

Both starts matched the canonical deterministic q=1 teacher **13/13**, matched
each other **13/13**, and reported `cached_tokens=0` **13/13 + 13/13**. The
512-token long-then-next pair passed **2/2 + 2/2**, and the 863-input/512-output
rollover row passed **1/1 + 1/1**. No third start was run, no favorable repeat
was selected, and no LocalMaxxing payload was staged or submitted.

## Selected fusion and arithmetic contract

The selected bucket was Q/K RMSNorm plus RoPE, worth `0.264944 + 0.137574 =
0.402518 ms/cycle` in the retained endpoint profile. The nominally larger
`0.519914 ms/cycle` gate chain was not selected because reproducing PyTorch
XPU's FP32 softplus bitwise inside a new SYCL kernel was a higher exactness
risk. KV write is smaller (`0.093803 ms/cycle`) and sits behind the attention
backend boundary.

The new selector is:

```text
VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=1
```

It is default-off and fails closed unless execution is the eager target exact
verifier at exactly M=8, parity probing is off, all participating tensors are
BF16, head dimension is 128, and the TP4 shape is one of Laguna's physical
full/sliding cases. DFlash draft layers and all other row counts retain the
record path.

The existing generic `fused_qk_norm_rope` was not reused because it changes
both the reduction tree and the norm-to-RoPE BF16 boundary. The Laguna-only
kernel instead preserves:

- eight adjacent BF16 inputs accumulated serially by each lane;
- the incumbent 16-lane shift RMSNorm reduction tree;
- BF16 rounding after `x * rrms`;
- BF16 weight multiply and result rounding;
- the existing BF16 cosine/sine cache; and
- the incumbent NeoX multiply/subtract/add order, including 64/128 rotary
  dimensions for full attention and 128/128 for sliding attention.

It emits contiguous Q and K outputs like the two incumbent RMSNorm calls and
leaves V unchanged. Two RMSNorm launches plus one joint RoPE launch become one
fused launch per attention layer.

## Source, build, and binary identity

- vLLM branch: `experiment/laguna-s-2.1-xpu-bringup-20260721`;
- vLLM commit: `d503073ec3573c6208cc2a06339815ec040ee984`
  (`xpu: select exact Laguna M8 QKNorm RoPE fusion`);
- XPU-kernel branch: `experiment/laguna-s-2.1-fwht-20260721`;
- XPU-kernel commit: `9525343e74b1a434b6af7d05583e1385a891c919`
  (`xpu: fuse exact Laguna M8 QKNorm and RoPE`); and
- tracked gate/launcher commit: `f325c6289191d46fff45231a8dfc23c53f16439c`.

Only the changed generic XPU extension was rebuilt:

```bash
source /opt/intel/oneapi/setvars.sh
ninja -C build/temp _C.abi3.so
```

Build log:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/build-laguna-m8-qknorm-rope-20260722.log
```

The log retains the initial missing-include compile failure and the successful
focused retry; the installed hash below is from the successful build.

Installed binary identities:

```text
bd337e35e8c5735f7e7ab2e4ff97835931c86a6daa51241329c3997a6b61f5b4  _C.abi3.so
625af4bbe792effde9f2f54c319f807a5c49b9756be313f9307d90da9ff5149e  _xpu_C.abi3.so
f222d3e2d2a8a331e3c85f12e0d02a17aa7a89147bbbcc8ac2c2a816629a405f  _moe_C.abi3.so
78a7218de45ee46b3734dc977c0d6115607ff7536706c0be2d4728b4ca2c40be  libgrouped_gemm_xe_2.so
```

The candidate `_C` and hashes are archived under:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/binaries/m8-qknorm-rope-9525343-20260722/
```

## Four-card component exactness and launch/timing gate

The tracked harness used changing QKV values, norm weights, BF16 RoPE caches,
and positions for 16 epochs per physical shape and rank. Q and K were checked
independently. Every value was bitwise identical: **64/64 per card, 256/256
overall**.

| Component | Record -> fused ms/layer |
|---|---:|
| Full attention, 12Q/2K, rotary 64 | 0.036766 -> 0.012671 |
| Sliding attention, 18Q/2K, rotary 128 | 0.035514 -> 0.012045 |
| Weighted 12-full + 36-sliding cycle | **1.719706 -> 0.585667 ms/cycle** |

The isolated enqueue-amortized component improves by **1.134039 ms/cycle
(65.9438%)**. This is a deliberately repeated, L3-hot component diagnostic and
is not substituted for endpoint throughput. Launches fall from **3 to 1 per
layer**, or **144 -> 48 per 48-layer target cycle**.

Per-rank weighted cycle results:

| Rank | Exact | Record -> fused ms/cycle |
|---:|---:|---:|
| 0 | 64/64 | 1.639780 -> 0.553224 |
| 1 | 64/64 | 1.773097 -> 0.568942 |
| 2 | 64/64 | 1.714744 -> 0.621642 |
| 3 | 64/64 | 1.751202 -> 0.598859 |

Evidence:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/qknorm-rope-component-d503073-9525343-20260722/
```

## Full two-start exactness and performance gate

Both starts used the approved eager depth-7 exact DFlash recipe: TP4+EP4, one
active sequence, BF16 KV, `--no-async-scheduling`, seed 1,
`enable_thinking=false`, prefix/cache/history/response reuse off, the record
batched-exact/fused-W1/route-W2/route-interleave flags, and `max_tokens=512` on
the fixed 13-prompt suite.

| Gate | Start A | Start B |
|---|---:|---:|
| Teacher token arrays | 13/13 | 13/13 |
| `cached_tokens=0` | 13/13 | 13/13 |
| 512-token long-then-next | 2/2 | 2/2 |
| 863-input/512-output rollover | 1/1 | 1/1 |
| Cross-start token arrays | 13/13 | 13/13 |
| Median tok/s, tokens 1-100 | **34.233360** | **33.190702** |
| p10 / mean tok/s | 26.207640 / 38.836543 | 27.041462 / 39.048293 |
| Median TTFT, ms | 5715.674 | 5753.877 |
| Median full after-TTFT tok/s | 43.127039 | 44.568640 |
| Median wall full tok/s | 27.863904 | 27.508534 |
| Acceptance | 4643/12033 (38.5856%) | 4643/12033 (38.5856%) |
| Delta from 33.43893 | +0.794430 (+2.3758%) | **-0.248228 (-0.7423%)** |

The two-start metric spread is **1.042658 tok/s (3.1414% of the lower start)**.
The exact outputs and acceptance counters are identical, so the failed record
gate is not a quality or speculation-policy change. The isolated launch win
did not reproduce as a stable endpoint-median win: the median-defining
`shell-safety-review` row moved from 34.233360 to 33.190702 between starts,
while row-level timing changes had mixed signs. Under the no-flaky-numbers
rule, the lower fresh start is authoritative.

Evidence:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/qknorm-rope-dflash-A-d503073-9525343-20260723T014703Z/
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/qknorm-rope-dflash-B-d503073-9525343-20260723T015326Z/
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/qknorm-rope-two-start-exactness-d503073-9525343-20260723.json
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/qknorm-rope-cross-start-repro-d503073-9525343-20260723.json
```

Compact tracked result:

```text
data/laguna-s-2.1-m8-qknorm-rope-negative-20260722.json
```

## Disposition and next lever

The source and binary are preserved, the selector remains default-off, and the
candidate service was stopped. The approved record recipe remains unchanged.
No payload exists because the lower start did not exceed 33.43893.

The recommended next bounded lever is the **1.014246 ms/cycle shared-expert /
router GEMM family**, starting with a shape/occupancy split and only then an
exact M=8 enumeration or projection fusion. It is larger than TopKGating
(`0.560374 ms/cycle`) and is the lower-risk fallback after attention fusion did
not clear the reproducibility gate. If that family has the same small-GEMM
occupancy limits as QKVO, TopKGating is the next single-kernel target.

No DeepSeek held-out pack was used and nothing was written under
`/mnt/fast-ai`. Protected DeepSeek option4-decoder branches and `preserve/*`
tags were unchanged. Postflight stopped the endpoint and workers; all four B70s
were free with only the transient `xpu-smi` probe visible.
