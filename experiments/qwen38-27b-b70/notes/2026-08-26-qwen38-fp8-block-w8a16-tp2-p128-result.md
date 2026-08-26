# Qwen3.8 official FP8 block-W8A16 TP2 result

Status: **quality-qualified candidate; target exceeded; clean-host replay still open**.

The official Qwen3.8-27B-FP8 checkpoint already stores block-scaled FP8
weights. The pinned XPU kernel package also already ships
`_xpu_C::fp8_gemm_w8a16`, but vLLM's block-FP8 linear integration always
quantized FP16 activations to FP8 and selected the W8A8 primitive. The
[default-off patch](../patches/vllm-qwen38-fp8-block-w8a16-20260826.patch)
adds an environment-gated W8A16 dispatch and skips that activation
quantization only when `VLLM_XPU_FP8_BLOCK_W8A16=1`.

## Measured result

The comparison used the same overlay image, model, two B70s, TP2 topology,
p128 scheduler, P2P collective settings, and HTTP fixture. The only control
difference was whether the environment gate was present.

| Metric | Default-off W8A8 | Block W8A16 | Change |
| --- | ---: | ---: | ---: |
| one fresh user, after TTFT | 21.872717 tok/s | **35.011369 tok/s** | **+60.07%** |
| c128 aggregate, conditioned median | 860.460981 tok/s | **1,112.570323 tok/s** | **+29.30%** |

The aggregate headline is the median of repeats 2-5. Repeat 1 is declared
conditioning and retained in the raw receipt rather than silently deleted.
The four included W8A16 values span 1,112.131274 to 1,122.931847 tok/s
(`0.472%` CV). Every repeat returned all 16,384 requested completion tokens,
reported zero cached prompt tokens, and produced no cross-base oracle
collision.

The same server measured a one-pass concurrency screen of 833.70, 980.90,
1,064.72, 1,090.40, and 1,122.99 aggregate tok/s at c64, c80, c96, c112, and
c128 respectively. These are five observed points, not a fitted curve. The
confirmed headline remains the conditioned c128 median above.

## Exact 2K–32K context replay

The same W8A16 overlay was replayed in the package's distinct one-slot,
33,024-token-capacity service. All six exact-token fixtures passed cache-zero,
no-truncation, 128-returned-token, and context-capacity gates.

| Exact prompt | Default-off decode | W8A16 decode | Decode gain | W8A16 TTFT |
| ---: | ---: | ---: | ---: | ---: |
| 2,048 | 21.835160 | **35.201648** | +61.22% | 1.011 s |
| 4,096 | 21.673278 | **34.756821** | +60.37% | 1.635 s |
| 8,192 | 21.270146 | **33.592729** | +57.93% | 3.219 s |
| 16,384 | 20.927452 | **32.830415** | +56.88% | 6.550 s |
| 24,576 | 20.650133 | **32.046666** | +55.19% | 10.072 s |
| 32,768 | 20.389854 | **31.489587** | **+54.44%** | **13.740 s** |

At 32K the measured TTFT fell from 21.873 to 13.740 seconds, a 37.18%
reduction. Each marker is one fresh-server sample using the existing grade-C
repeated-token shape fixture. These are observed operating points, not a fit
or a natural-prose latency claim. Raw receipts live in
[`qwen38-fp8-block-w8a16-tp2-http-depth-20260826-r2/`](../data/qwen38-fp8-block-w8a16-tp2-http-depth-20260826-r2/).

## Quality and mechanism gates

- 7/7 sequential exact-answer cases passed.
- Eight sequential repeats were byte-identical.
- 1,024/1,024 concurrent arithmetic/code semantic cases passed at c128.
- All performance requests returned complete raw token IDs with cache zero.
- Greedy output remains batch-shape-dependent, so the concurrency receipt is
  `output-isolation-qualified-shape-variant`, not a claim of universal
  sequential token identity.
- At the production M=64 operator shapes, the W8A16 primitive reduced median
  QKV / gate-up / down GEMM time from 87.19 / 145.47 / 121.35 microseconds to
  32.46 / 77.90 / 69.49 microseconds. Those values are mechanism attribution,
  not endpoint throughput.

The exact overlay image is
`sha256:ced02d013fe356faac513f2598b4da1f11fd8e20a9bb8fb9a443564fda460556`,
built from the pinned upstream image and vLLM commit
`ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9`. The original base path remains
the default when the gate is absent.

## Boundaries and open work

The 1,112.57 tok/s aggregate result uses a 256-token-capacity,
128-active-slot service and short unique prompts. The 2K–32K rows use a
separate one-slot service and are reported independently; no hybrid workload
is inferred between them. The model files were direct-I/O verified against all
66 publisher identities. The patch, Docker overlay, launch, benchmark, and raw
receipts are repository-local; a clean supported-host replay and beginner
driver recovery path remain certification gaps.

Structured summary:
[`2026-08-26-qwen38-fp8-block-w8a16-tp2-p128-summary.json`](../data/2026-08-26-qwen38-fp8-block-w8a16-tp2-p128-summary.json).
Raw evidence:
[`qwen38-fp8-block-w8a16-tp2-p128-20260826-r1/`](../data/qwen38-fp8-block-w8a16-tp2-p128-20260826-r1/).
