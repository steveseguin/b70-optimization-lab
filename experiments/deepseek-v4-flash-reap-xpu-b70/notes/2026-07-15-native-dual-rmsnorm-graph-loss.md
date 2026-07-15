# Native dual Q/KV RMSNorm graph loss

Date: **2026-07-15**

Status: **bitwise-exact kernel win; paired full-model performance rejection**.

## Boundary and implementation

Each of the 43 DeepSeek V4 layers applies one dual Q/KV RMSNorm after the
fused WQA/WKV projection. The existing Triton kernel normalizes BF16 Q1024 and
KV512 rows in one launch. Its four-card median cost was 137.306-145.938 us per
call in the standalone gate, an optimistic 5.90-6.28 ms/token across 43 layers.

XPU-kernel commit `ef307a8f45a0dc3794a8775e2e5d6c7484b63a1b` adds a guarded
M=1 Xe2 operator with explicit output tensors. The first SG16 prototype was
fast but one adversarial graph epoch differed by one BF16 element. Reading the
cached Triton LLIR exposed the required reduction order: 128 work-items, eight
adjacent BF16 values per work-item, SG32 reduction, and four subgroup results.
Mirroring that topology repaired the mismatch. This reduction-order detail is
the important correctness lesson; broad random agreement was not sufficient.

The final four-card gate passed:

- 40/40 changing eager inputs on every card, bitwise exact;
- 8/8 changing XPU graph replays on every card, bitwise exact and non-stale;
- native median 110.864/112.918/111.982/125.164 us on cards 0-3;
- projected standalone savings 1.137/1.290/1.242/0.893 ms/token.

vLLM commit `d8d7cf1988549e81337ff4df4cd8f70de5d9255a` exposes the path only
under `VLLM_XPU_V4_NATIVE_DUAL_RMSNORM=1`, for XPU M=1 Q1024/KV512. M>1 and
all default-off behavior remain unchanged.

## Full-model A/B

The candidate used the exact 40 tok/s record identity plus only the native
dual-RMSNorm flag. Six alternating cold requests returned
`1073, 437, 1073, 437, 1073, 437`, all with `cached_tokens=0`. Two fixed
12-prompt strict suites passed every freshness and token-timing gate:

| Lane | Median tok/s | p10 tok/s |
| --- | ---: | ---: |
| native candidate 1 | 39.992846 | 39.531170 |
| native candidate 2 | 39.917368 | 39.559080 |
| same-commit flag-off control | **40.094966** | **39.694963** |

The candidate is 0.255% and 0.443% slower than the paired flag-off control.
The standalone event timing therefore did not predict the reusable command
graph result. A lower isolated kernel duration is not enough when replacing a
graph-resident Triton node; command-list execution, compiler scheduling, and
occupancy must be judged end to end.

Eleven of 12 output hashes changed between the two candidate suites themselves
(all 12 differed from the historical record suite), so hash changes cannot be
assigned to this exact operator. That is consistent with the already
documented K160 nondeterminism floor. Arithmetic replay and the focused
raw-tensor gates remain the relevant correctness evidence.

## Decision

Keep both commits as default-off research artifacts, but reject promotion and
do not submit LocalMaxxing. The trustworthy record remains 40.020972 tok/s.
Do not revisit a standalone dual RMSNorm replacement. The next fusion must
remove a producer/consumer boundary—preferably WQ_B output plus Q normalization,
RoPE, and KV insertion—and must clear the same exact >=0.50 ms/token real-model
gate before another server load.

Raw evidence:

- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/qkv-rmsnorm-native-dual-v2-card{0,1,2,3}-20260715Tnativev2.json`;
- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/native-dual-rmsnorm-canary-20260715T1045Z`;
- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/native-dual-rmsnorm-paired-control-20260715T1010Z`.
