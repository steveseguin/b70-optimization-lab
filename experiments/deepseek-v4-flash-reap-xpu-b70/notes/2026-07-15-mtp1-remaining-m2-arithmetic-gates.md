# DeepSeek V4 K160 MTP1 remaining M=2 arithmetic gates

Date: 2026-07-15

## Outcome

The remaining target-verifier W8A8 and MXFP4 paths are row-exact at M=2, so
they are eligible for exact performance work. The separate draft-only
`e_proj`/`h_proj` W8A16 screen is closed before model integration: although its
isolated kernel is 3.17x faster, it can save only about 0.087 ms per MTP cycle,
well below the 0.50 ms service-load gate.

The promoted row-exact MTP1 plus M=2 W8A16 service remains unchanged at
54.464909 tok/s.

## M=2 row-invariance results

The W8A8 gate compared one batched M=2 operation with two independent M=1
operations over 40 changing epochs for each remaining dense family:

- target shared-expert down, M2/N4096/K512: 40/40 bitwise exact;
- attached MTP `e_proj`/`h_proj`, M2/N4096/K4096: 40/40 bitwise exact.

Evidence:

`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/w8a8-m2-row-invariance-card2-20260715.json`

The MXFP4 gate exercised the production K160 routed-expert shape with 160
global experts, 40 local experts per EP rank, hidden size 4096, intermediate
size 2048, and top-k 6. It covered same-local, disjoint-local, and mixed-EP
expert selections over 20 changing epochs each:

- M=2 versus two M=1 calls: 60/60 bitwise exact;
- repeated M=1 control: 60/60 bitwise exact.

Evidence:

`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/mxfp4-m2-row-invariance-card3-20260715.json`

The other three card artifacts were captured earlier at the same path pattern
with `card{0,1,2}` and also pass. These results establish arithmetic safety;
they do not by themselves establish a speed opportunity because both paths are
already batched in production.

## Draft projection W8A16 screen

For M1/N4096/K4096 on card 1, the exact-shape dense benchmark measured:

- W8A8 quantization: 7.488 us median;
- W8A8 GEMM: 58.202 us median;
- W8A8 quantization plus GEMM: 63.568 us median;
- W8A16 GEMM: 20.036 us median;
- local speed ratio: 3.17x for the complete W8A8 path versus W8A16.

The W8A16 result is not bitwise equivalent to W8A8 (`max_abs=0.0625`,
`mean_abs=0.01314`). More importantly, the attached one-layer draft invokes
only `e_proj` and `h_proj` once per speculative cycle. Replacing both operations
would therefore save about `2 * (63.568 - 20.036) = 87.064 us`, or 0.087 ms per
cycle. That is only about 0.27% of the current roughly 32.6 ms cycle and cannot
clear the 0.50 ms integration gate even before accounting for full-model graph
effects.

Evidence:

`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/mtp-eh-fp8-dense-card1-20260715.json`

## Decision

Do not restart the service for draft-only `e_proj`/`h_proj` W8A16. Preserve the
benchmark shape and result as positive microkernel evidence but a rejected
end-to-end candidate. Continue with an exact M=2 MXFP4 or remaining target
verifier candidate only after a hardware gate projects at least 0.50 ms saved
per speculative cycle. Keep MTP2 and larger repeated-single-layer widths
closed.
