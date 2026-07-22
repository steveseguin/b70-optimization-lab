# Laguna S 2.1 batched-exact DFlash verification — 2026-07-22

## Result first

- Exactness: **7/7 cold prompts matched the fresh deterministic q=1 target
  token-for-token**, comprising six 128-token realistic prompts and the
  511-token rollover prompt. Every q=1 and DFlash request had
  `cached_tokens=0`.
- Exact DFlash median: **37.58636639775746 tok/s** for generated tokens 1–100
  after TTFT; p10 **22.00194725636536**, mean **36.85918234729524**.
- Acceptance: **540/1743 = 30.98106712564544%**. The seven requests emitted
  786 tokens over 249 cycles, or **3.1566265060240966 emitted/cycle**.
- This is **5.045846x** the serialized-exact 7.448971812987762 tok/s result,
  a gain of 30.137394584769698 tok/s. It is 8.949% of the 420 tok/s lower
  roofline and 7.298% of the 515 tok/s upper roofline.
- The decode cycle fell from approximately 426.0 to **83.983 ms**. Collective
  calls fell from 777 to **98/cycle** (97 all-gathers plus one draft-side
  all-reduce), an 87.39% reduction.
- This is a candidate first Laguna LocalMaxxing record. It was **not
  submitted**; Claude owns the submission gate.

## What changed

vLLM commit `4a25d9afbbf71eddbd8edce1815e3b6265c41ab3` and XPU-kernel
commit `6fc06b08cd10a9e9e7d15e62e1afcf06e7ab6c73` replace the q=8
target row loop with one deterministic batched verifier:

1. The speculative target context is tagged explicitly. Only that context
   selects the batched q=2..8 contract, so short prefill tails retain the
   conservative serialized fallback.
2. Attention remains the paged-decode-equivalent implementation from the
   exactness repair: all eight verifier positions are represented as eight
   one-token pseudo-sequences in **one paged-decode launch**, never the
   numerically different chunk-prefill kernel.
3. Target BF16 projections, routers, transforms and vocabulary projection
   preserve eight independent M=1 numerical lanes in a single `torch.bmm`.
   This keeps M=1 accumulation order while removing the Python row loop.
4. Each target TP/EP combine is one all-gather followed by the new fused
   fixed rank-0,1,2,3 BF16-sum kernel. There are 96 such deterministic sums
   per q=8 cycle.
5. Routed INT4 MoE uses a direct `[row, top-k slot]` M=8 route. It performs
   deterministic W1, activation, W2 and identity gather without the atomic
   row-count/remap path. The trace has 94 direct M8 INT4 kernels per cycle.

The path requires both:

```text
VLLM_XPU_EXACT_SPEC_ATTN=1
VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1
```

## Component gates

Before model-level promotion, the following B70 component comparisons all
used `torch.equal` and reported zero differing elements:

- fused rank-order BF16 sum versus the old explicit rank-0,1,2,3 adds;
- eight-lane BF16 `bmm` versus eight sequential `F.linear` calls for the
  target projection/router/vocabulary shapes;
- direct-route q=8 W1 versus eight q=1 calls;
- direct-route q=8 W2 versus eight q=1 calls;
- direct-route q=1 versus the old atomic-remap/grouped-GEMM teacher, including
  routes owned by remote EP ranks.

The first full native build exposed only an `at::Tensor`/`torch::Tensor`
namespace compile error in the new utility binding; that was fixed before the
committed rebuild. The final build log is:

`/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/build-batched-exact-6fc06b0-20260722.log`

Loaded native-module hashes are:

| Module | SHA-256 |
|---|---|
| `_xpu_C.abi3.so` | `671ce1111b854ca4f3a5275af6d0b701c4dc4b18d78c47f12dfdf10a98bbe103` |
| `_moe_C.abi3.so` | `f222d3e2d2a8a331e3c85f12e0d02a17aa7a89147bbbcc8ac2c2a816629a405f` |
| `libgrouped_gemm_xe_2.so` | `285c9bce2001d05b89719645d8afa98a93b589e476fe6e540582009ec90e9f2a` |

## Mandatory exactness gate

Fresh q=1 teacher:

`/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/batched-exact-q1-4a25d9a-6fc06b0-20260722`

Batched-exact DFlash:

`/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/batched-exact-dflash-4a25d9a-6fc06b0-20260722`

All six realistic rows have identical complete 128-token arrays and output
hashes between those packets. The 511-token rollover emitted the same 18-token
array on q=1 and DFlash:

```text
[785, 3638, 11417, 25406, 466, 340, 2168, 444, 1093,
 38446, 71, 20266, 365, 330, 24446, 3920, 83, 24]
```

The fresh q=1 rollover repeated identically in a second cold request. This
teacher differs from the older serialized packet because q=1 now uses the
same new direct-MoE/rank-sum primitive as q=8; the six realistic output hashes
remain unchanged. The machine-readable comparison is `exactness.json` in the
DFlash packet.

## Throughput

The strict six-prompt realistic packet reports:

| Metric | Result |
|---|---:|
| tokens 1–100 after TTFT median | **37.58636639775746 tok/s** |
| p10 / mean | 22.00194725636536 / 36.85918234729524 tok/s |
| full-response median | 38.65411111915881 tok/s |
| wall full median | 14.468466258841346 tok/s |
| median TTFT | 4937.246673449408 ms |
| accepted / drafted | 540 / 1743 |
| acceptance | 30.98106712564544% |
| emitted / cycle | 3.1566265060240966 |

The serialized exact result had 31.221% acceptance and 3.1734 emitted/cycle,
so the speedup is verifier execution, not a favorable acceptance change.

## New cycle profile

Trace packet:

`/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/batched-exact-dflash-cycle-profile-4a25d9a-6fc06b0-20260722`

Nine steady q=8 contexts per rank were retained after dropping two initial
cycles. oneCCL device timestamps remain corrupted under Kineto and are not
used. Collective time is the rank-0 inclusive CPU API span; noncollective time
is the cross-rank XPU mean. Normal cycle time is emitted/cycle divided by the
non-profiled primary throughput.

| Stage | ms/cycle | Share | Calls/cycle |
|---|---:|---:|---:|
| Fixed-order collective API | 13.654 | 16.26% | **98** |
| Noncollective XPU kernels | 16.496 | 19.64% | — |
| Host/Python/launch residual | **53.833** | **64.10%** | — |
| Total normal cycle | **83.983** | 100% | — |

Host/launch residual fell from 215.2 to 53.8 ms, a **74.98% absolute
reduction**. Its proportional share rose from 50.5% to 64.1% because
collective and device work collapsed even faster; it did not meet the hoped
for percentage-share reduction. Collective share fell from 35.4% to 16.3%.
The trace proves one verifier-wide paged-decode launch per each of 48 layers,
96 rank-order sum kernels, and 94 direct M8 expert kernels per cycle.

`summary.json` is the raw streaming trace summary and `profile-derived.json`
records the count and residual derivation.

## Candidate identity and next lever

The complete identity is:

`/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/batched-exact-dflash-4a25d9a-6fc06b0-20260722/identity.txt`

The MoE/EP lane is ready. Exact direct `[row, slot]` routing and fixed-order
EP reconstruction have passed their component and full-model gates. The next
lever is to replace the remaining **47 layer-level EP all-gather + rank-sum
pairs** with a dedicated deterministic fixed-rank transaction, then persist or
fuse the 47-layer direct W1/activation/W2 sequence. The profile's 97
all-gathers are now the dominant structured launch/communication count (48 TP
projection combines, 47 EP combines, one other target combine and one vocab
combine); this can be attacked without reopening atomic remap exactness.

## Commits and safety

- vLLM: `4a25d9afbbf71eddbd8edce1815e3b6265c41ab3`, branch
  `experiment/laguna-s-2.1-xpu-bringup-20260721`.
- XPU kernels: `6fc06b08cd10a9e9e7d15e62e1afcf06e7ab6c73`, branch
  `experiment/laguna-s-2.1-fwht-20260721`.
- DeepSeek option-4 branches and all `preserve/*` tags were untouched.
- No held-out pack was used, no LocalMaxxing submission was made, and all
  model/cache/build/run writes stayed on the Corsair artifact root. There were
  no `/mnt/fast-ai` writes.
- The profiling service was stopped after capture and all four B70s were freed.

