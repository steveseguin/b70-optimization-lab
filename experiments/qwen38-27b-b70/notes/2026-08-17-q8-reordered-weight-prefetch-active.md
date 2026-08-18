# Qwen3.8 27B Q8 reordered-weight prefetch

Date: 2026-08-17

Status: **closed as a `-2.615%` performance regression; do not repeat unchanged**

## Hypothesis

The accepted Q8 reordered row body demand-loads one aligned 16-byte weight
vector per lane and then executes the exact DP4A/FP32 accumulation work for
that iteration. The earlier two-iteration operand-preload experiment moved the
next ordinary load into registers but did not issue a device cache prefetch.
Intel oneAPI 2026.1 exposes an in-kernel prefetch primitive with cache-level
hints, so a bounds-checked prefetch of the next row chunk may overlap B70 HBM
latency without increasing the live DP4A operand set.

The treatment must cover every accepted reordered-Q8 decode family:

- standalone MMVQ, including the down projection and output head;
- fused gate/up pair;
- fused attention Q/V/K triple;
- fused recurrent QKV/Z/alpha/beta quad.

Each lane will prefetch only its next aligned 16-byte weight vector, only when
that next chunk remains within the same row. Actual loads, Q8 scale reads,
DP4A order, FP32 accumulation order, subgroup reduction, tensor split, model,
F16 KV, and target-only execution remain unchanged.

## Gate

Use a default-off runtime door and a same-binary off/on smoke first. Require
the expected dispatch marker on both B70s and `VERIFY_MISMATCH=0`. If the arm
is live and safe, compare candidate-off against the promoted binary to exclude
codegen drift, then use fully position-complemented fresh-process decode
screens. Endpoint and semantic gates are allowed only for a repeatable gain.

The existing transferred PVC note that prefetch was null did not close this
arm because it measured a different architecture and kernel geometry. The
BMG-G31 result below now closes the exact all-family treatment.

## Implementation and AOT proof

The isolated candidate adds `GGML_SYCL_MMVQ_Q8_PREFETCH=1`. Separate
compile-time specializations preserve the arithmetic body and keep the hot
loop free of a runtime branch. The bounds-checked helper asks L1 for the next
iteration's aligned 16-byte reordered-Q8 vector in standalone, multi-column,
pair, triple, and processed recurrent-quad MMVQ.

The clean Release build used oneAPI 2026.1.1, `bmg_g31` AOT, F16 and Level
Zero support on, and graph/DNN/host-memory fallback off. It ran at `-j2` under
`MemoryHigh=6G`, `MemoryMax=8G`, and `MemorySwapMax=8G`.

Candidate hashes:

- `libggml-sycl.so.0.19.0`:
  `60fe7f64419768fa5fb345432fe2bf38918573857bbb5a9b2d641b9884d9b7ee`;
- `llama-bench`:
  `d17992da5941db787f88e737b7e5f9d185a3976d3398968a4cc08f25e483f042`;
- `llama-server`:
  `327190e2effb23c8cb700b27dbf7def40b7aa22c940e8567163e56c46fd07417`.

`clang-offload-extract` located the MMVQ image at candidate image 135. `ocloc
disasm` proved the treatment pair kernel contains cacheable UGM reads with a
null destination, while its control specialization contains no such sends.
Both arms remain SIMD16, 128 GRFs, and eight EU threads. Thus the requested
prefetch survived AOT and did not reduce reported occupancy. The focused
increment has decoded SHA-256
`20ec24b131f5c13b8ffbf9c1a97b2feb0852d5c81b901c8bf9240fc53d13a788`.

## Safety and result

The correct TP2 smoke used `SYCL0/SYCL1`, equal `1/1` tensor split, Q8 target,
F16 KV, FlashAttention, SG24 recurrent geometry, no speculation, and the full
accepted fusion stack. The treatment announced on both B70s, all expected
fusion counters fired, and shutdown reported `VERIFY_MISMATCH=0`. A preliminary
comma-separated device invocation was correctly discarded because
`llama-bench` interpreted it as two independent one-card cases rather than
TP2.

Adding a second kernel specialization materially changed the door-off AOT
codegen, so a same-binary A/B would not isolate the prefetch. The decisive
fresh-process bracket therefore compared the promoted binary directly around
the door-on treatment, using `llama-bench -p 64 -n 128 -r 1`:

| Position | Binary | Decode tok/s |
| --- | --- | ---: |
| A1 | accepted DP4A2 x SG24 | 36.036107 |
| B | prefetch treatment | 35.085181 |
| A2 | accepted DP4A2 x SG24 | 36.018324 |

The accepted mean was `36.0272155 tok/s`; prefetch regressed `2.614786%`.
Every run ended at `VERIFY_MISMATCH=0`, both B70s remained normal, and no new
Xe fault/reset/hang appeared. This is a clean performance rejection. The
endpoint and semantic gates were intentionally skipped because a treatment
this far below both bracketing controls cannot be promoted.

Structured result:
[`2026-08-17-q8-reordered-weight-prefetch-negative.json`](../data/2026-08-17-q8-reordered-weight-prefetch-negative.json).
Focused patch:
[`q8-reordered-weight-prefetch-negative-20260817.diff.gz.b64`](../patches/q8-reordered-weight-prefetch-negative-20260817.diff.gz.b64).
Raw local evidence is under
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-prefetch/` and
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-prefetch-aot/`.
