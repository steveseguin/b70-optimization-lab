# Sharded Target Argmax Record

Date: **2026-07-18**

Status: **promoted TP4+EP single-session, target-verified record**

## Outcome

The guarded sharded target-argmax verifier raises the unchanged K160/DSpark7
endpoint to a new **80.820052 tok/s** strict-suite record. Three independent
strict medians are **80.820052 / 76.900178 / 78.287226 tok/s** and their median
is **78.287226 tok/s**, improving the preceding run-of-three median of
77.572536 tok/s. All 36 realistic requests were fresh and cache-zero. Four
ordered exact-canary suites passed 24/24 before, between, and after the strict
suites.

This is one active generation, not aggregate throughput. The K160 target is
unchanged and verifies DSpark7 accepted tokens at fixed M=8. The primary
metric is generated tokens 1-100 after TTFT on 12 unique cold prompts.
LocalMaxxing approved the result as `cmrquta9905w3lg013m5vxoqx`.

| Strict suite | Median tok/s | p10 tok/s | Mean tok/s | Full after TTFT | Wall full | TTFT ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| screen | **80.820052** | 71.669556 | 80.033410 | 80.745485 | 67.762818 | 342.777657 |
| confirmation | 76.900178 | 67.222630 | 71.596104 | 78.298482 | 63.019793 | 332.471646 |
| third | 78.287226 | 68.156104 | 78.303030 | 79.800183 | 63.588906 | 327.572847 |

## Why the old boundary was expensive

Target verification projected a full 129,280-token vocabulary on each decode
step, all-gathered the sharded logits, materialized the FP32 sampler input, and
then reduced that full tensor even though the promoted endpoint permits only
plain greedy sampling. A fresh target-sample profile measured about 1.62 ms of
host scope, 0.492 ms of noncollective device work, 0.454 ms in the vocabulary
projection, and 0.082 ms in the full-logit all-gather. This was a useful
boundary because most of that movement did not contribute information to a
top-1 decision.

## What changed

For the narrow, fail-closed contract—temperature-zero greedy sampling, no
grammar, logprobs, penalties, bias, bad words, synthetic rejection, or draft
logits—the target now projects only its local 32,320-token LM-head shard. Each
rank selects its local top-1 and the existing model interface gathers only the
small `(value, index)` candidates. A native SYCL custom op consumes the winning
target token IDs and performs the ordinary target-verified rejection/bonus
commit without reconstructing the full logits tensor.

Every unsupported sampler configuration falls back to the canonical full-logit
path. The feature is also explicit and default-off behind
`VLLM_XPU_GREEDY_SHARDED_TARGET_ARGMAX=1`.

The native target-token rejection boundary passed 40/40 changing eager and
40/40 changing graph cases on every B70. Its isolated latency was
8.93-9.32 us eager and 8.83-9.10 us captured. The companion exact bonus-stat
reuse reduced the existing rejection microbenchmark from 22.76-23.19 us to
19.52-20.57 us captured, but is only a bundle component rather than the
headline mechanism.

## Problems found and resolved

The first endpoint reached the new path but failed its first request because
vLLM supplies draft token IDs as `int32` while the native op initially required
`int64`. The contract was corrected to accept either `int32` or `int64` draft
IDs, rebuilt, and independently gated with the real `int32` shape before the
service was relaunched. Preserve the failed artifact as useful integration
evidence; it was not benchmarked or promoted.

Several attempts to express the tiny commit boundary as a new Triton kernel
segfaulted inside `libsycl`, including a constexpr variant of an already
qualified kernel. The production implementation therefore uses a small native
SYCL op with an explicit schema and fixed shape instead of adding an unstable
JIT boundary.

Two Markov bias-scale screens were also negative and remain rejected:

- scale 0.75: 74.952573 tok/s, no acceptance improvement;
- scale 1.25: 73.449448 tok/s, generally worse acceptance.

These results show that retuning draft probabilities is not a substitute for
removing the expensive verifier transaction.

## Identity and evidence

- vLLM: `264c7f2f7df21ddeeab32ecca0353133344f1ac9`;
- XPU kernels: `31315673737d95da0f79179c8f755260ef02c1d6`;
- oneCCL: `48fda4f0e074db005596d6899d5227d3f0316c12`;
- promoted endpoint: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-sharded-target-argmax-candidate-20260718T2100Z`;
- first dtype-failure endpoint: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-sharded-target-argmax-candidate-20260718T2053Z`;
- native four-card gate: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/native-target-token-rejection-20260718`;
- bonus-reuse control: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/greedy-rejection-bonus-control-20260718`;
- bonus-reuse candidate: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/greedy-rejection-bonus-reuse-candidate-20260718`;
- scale 0.75: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-markov-scale075-dev-20260718T2015Z`;
- scale 1.25: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-markov-scale125-dev-20260718T2020Z`.

## Decision and next boundary

Promote the guarded sharded target-argmax transaction. Keep both Markov-scale
changes rejected and keep the unstable Triton variants out of the tree. The
remaining verifier work is the local-vocabulary projection itself plus the
small cross-rank winner exchange; the next material effort should fold the
local argmax into the sharded LM-head projection or move the complete fixed
greedy verifier/accept/commit cycle into a reusable fixed-address Level Zero
command list. Small generic sampler tweaks should not displace that work.
