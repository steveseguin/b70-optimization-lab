# Laguna grouped oneDNN BF16 x INT4 oracle preregistration

Date: 2026-08-01 America/Toronto

Status: **closed exact-but-slower; no model integration authorized.**

## Motivation

The protected exact BF16-KV record is `125.4619731637751 tok/s`.  At its
measured acceptance, 130 tok/s requires about `1.128 ms` less verifier-cycle
time.  The target executes one W13 and one W2 INT4 grouped GEMM in each of 48
layers.  The current stable component medians are about `0.321024 ms` and
`0.183683 ms`, or `24.226 ms` per verifier cycle.  A real 5% reduction in this
component is therefore sufficient in principle and is one of the few remaining
cost centres large enough to close the gap by itself.

Earlier Qwen work demonstrated fast resident grouped oneDNN sidecars for W8A8.
The vendored oneDNN 3.12 source also contains a GPU grouped micro-GEMM with BF16
source, signed-INT4 weights and grouped weight-scale support.  This is a new
kernel family rather than another scheduler mutation of the heavily screened
incumbent.

## Preliminary packing oracle

Before this preregistration, the already installed dense
`int4_gemm_w4a16` operator was used only as a read-only format/numerics oracle
on one isolated B70.  Laguna's signed-nibble storage must be converted once by
XORing every nibble's sign bit (`0x88` per byte) into the GPTQ offset-binary
layout and supplied with scalar zero point 8.  After that conversion, dense
oneDNN and the incumbent agree on all but 42--55 BF16 elements per changed
input for the real W13/W2 shapes; maximum differences are one or two BF16 ULPs.
This proves the original large mismatch was packing, but it does **not** satisfy
the exactness contract.  No performance claim is made from these oracle calls.

The first implementation question is therefore whether strict fpmath and the
grouped micro-GEMM's accumulation plan reproduce the incumbent raw BF16 result.
If they do not, the route stops before endpoint integration regardless of how
small the numerical difference is.

## Frozen treatment

Build a separate default-unused component operator against a oneDNN build with
`DNNL_EXPERIMENTAL_GROUPED_MEMORY=ON`.  It must consume:

- BF16 source `[120,K]` grouped by contiguous expert rows;
- 64 local experts;
- signed INT4 weights in zero-copy physical `[64,N,K/2]` byte storage,
  described logically to oneDNN as `[64,K,N]` with `acb` layout;
- immutable BF16 group-32 scales `[64,K/32,N]`;
- cumulative int32 expert end offsets `[64]`; and
- BF16 destination `[120,N]`.

The two frozen cases are W13 `N=2048,K=3072` and W2 `N=3072,K=1024`, using the
same changed-input seeds and row-count corpus as the protected transposed-scale
gate.  Cache primitive construction.  This component is an oracle only: do not
wire oneDNN's independent engine stream into graph replay.  Historical Qwen
evidence showed that direct engine-stream capture/replay can lose the device.

## Gates and stop rules

1. Prove the experimental oneDNN build accepts grouped BF16 x signed-INT4 with
   BF16 group-32 weight scales.  Record descriptors, scale mask/groups, runtime
   library identity and any primitive rejection.  Stop on unsupported schema.
2. Compare at least three changed inputs for each real shape against the
   protected GRF128/transposed-scale DSO.  Require `6/6` raw-BF16 equality,
   input immutability and identical logical tensor/row hashes.  Close the route
   immediately on any mismatch; approximate closeness is not a pass.
3. Only after exactness, use 200 warmups and 15 samples of 40 launches.  Require
   no shape worse than `0.99x` and at least `1.05x` improvement in the summed
   W13+W2 median.  The current stable reference sum is about `0.504706 ms`, so
   promotion requires at most about `0.480070 ms`.
4. A component pass authorizes design of a graph-native current-queue custom
   op based on the winning oneDNN strategy.  It does not authorize a model
   service, endpoint score, production selector, or change to the sealed
   record.  Any endpoint experiment needs a separate preregistration and must
   retain BF16 KV, M12/DFlash11, the canonical q1 teacher, cache-zero policy,
   one active generation, cold first-valid scoring and audited topology.

No target/draft/KV precision change, teacher change, prompt change, warmed
generation, retry, metric substitution, reset, reboot or privileged recovery
is authorized by this screen.

## Result

The grouped-memory implementation was built as a default-unused registration
sidecar against vendored oneDNN `3.12.0` (`80afa710...`).  The protected vLLM
extension and grouped-GEMM DSO remained hash-pinned.  oneDNN verbose output
confirmed `gpu,matmul,grouped_gemm:micro` with BF16 grouped source/destination,
signed INT4 `acb` weights, BF16 mask-7 scales and groups `32x1`; it did not use
the reference fallback.

Two runtime/build identity defects were caught before any numerical result:

- the first gate selected oneAPI 2026 while PyTorch and the record use 2025.3;
- CMake used the 2025.3 compiler executable but resolved
  `/opt/intel/oneapi/compiler/latest` headers and library to 2026, embedding
  incompatible SYCL 8 and SYCL 9 dependencies.

The final sidecar was compiled and linked entirely against explicit oneAPI
2025.3 paths.  Its SHA-256 is
`8357200e33987de704a69799c8b46f757bb60010370a6ad075c1310ebdf3a5e0`.

Exactness passed twice: the construction oracle and then the cached,
caller-output implementation each produced `6/6` raw-BF16 matches in strict
mode and `6/6` in BF16 fpmath mode.  Every comparison had zero differing
elements.  The cached exactness artifact is:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-grouped-onednn-int4-cache-00fbed3-20260801T141348Z`

The preregistered 200-warmup, 15-sample x 40-launch paired timing gate then
measured:

| shape | incumbent | oneDNN strict | oneDNN BF16 |
|---|---:|---:|---:|
| W13 | 0.321951 ms | 0.342322 ms | 0.342305 ms |
| W2 | 0.184469 ms | 0.192580 ms | 0.192930 ms |
| sum | **0.506421 ms** | **0.534902 ms** | **0.535234 ms** |

Strict reached only `0.946754x` of incumbent summed throughput; BF16 reached
`0.946167x`.  Both shapes regressed, both candidates missed the frozen
`0.480070 ms` absolute ceiling, and neither passed the paired 1.05x gate.
There is no endpoint projection and no model integration.

Formal timing artifact:

`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-grouped-onednn-int4-timing-00fbed3-20260801T141601Z`

Durable conclusion: oneDNN's grouped INT4 path is a useful exact arithmetic
oracle for Laguna, but its current micro-kernel is about 5.6% slower than the
specialized Xe2 incumbent at these sparse M=120 distributions.  Cache and
allocation overhead were removed before measurement, so further wrapper work
is not justified.  Revisit only after a materially different oneDNN grouped
micro-kernel or tile strategy, not another integration attempt.
