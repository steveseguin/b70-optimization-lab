# Qwen3.8 Q8 recurrent-quad local activation staging

Date: 2026-08-17

Status: **closed as endpoint-neutral; do not promote**

The accepted recurrent GDN quad launches 24 independent SG16 row subgroups
per workgroup. Every subgroup consumes the same 5,760-byte reordered Q8_1
activation. A default-off, exact-shape arm copied those bytes once per
workgroup with aligned 16-byte transfers, synchronized once, and made the
unchanged row body read the local copy. It retained all 24 row subgroups and
did not change any DP4A, scale multiplication, FP32 accumulation, subgroup
reduction, or output operation.

The candidate `libggml-sycl.so.0.19.0` SHA-256 was
`ed9bcef981fed2b7987e29dd09289f097926f531a01426badcd7bc2466c632b0`;
the accepted control was
`e75b960307fccee661073e67d8288b3893f421617ea83a100cf9b8f9de38b4b5`.
A bounded `p64/n1` TP2 smoke selected the arm on both B70s, retained all 192
recurrent-quad fusion hits, and ended with `VERIFY_MISMATCH=0`.

Two same-binary, position-complementary `llama-bench` gates were positive:

| Gate | Control (tok/s) | Local activation (tok/s) | Delta |
| --- | ---: | ---: | ---: |
| `p64/n256/r3`, A-B-B-A | 37.068920 | 37.171984 | +0.278% |
| `p64/n512/r3`, B-A-A-B | 36.647437 | 36.795157 | +0.403% |

Both candidate positions beat their matched controls in both gates. The
required adjacent fresh-server endpoint pair did not preserve that gain,
however:

| Metric | Control | Local activation | Delta |
| --- | ---: | ---: | ---: |
| Conventional first-100 median | 36.488662 | 36.490442 | +0.0049% |
| First-100 mean | 36.680135 | 36.738265 | +0.158% |
| Full-512 after-TTFT median | 36.462877 | 36.491962 | +0.080% |
| Full-512 after-TTFT mean | 36.480679 | 36.525657 | +0.123% |
| Full-512 wall median | 35.986755 | 36.008617 | +0.061% |

Both endpoint arms passed 12/12 complete output hashes, 12/12 cache-zero
checks, and the fresh-response/final-gate policy; their hash arrays were
identical. The mechanism therefore preserves quality but is service-neutral.
The activation was already cache-resident enough that one SLM fill and barrier
could improve the isolated decode loop only marginally, with no meaningful
realistic-serving benefit.

The accepted source and deployed library were restored exactly. Both GPUs
remained normal and the boot log had no Xe fault, reset, hang, or wedged event.
Raw evidence is under
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-quad-local-y`;
candidate/control libraries are under
`/mnt/fast-ai/artifacts/qwen38-q8-quad-local-y-20260817`.
The retained zero-context patch applies to the accepted source with
`git apply --unidiff-zero`.
