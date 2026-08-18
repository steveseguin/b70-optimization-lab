# Qwen3.8 Q8 crossed two-chain DP4A schedule

Date: 2026-08-17

Status: validated deep-decode positive, primary endpoint neutral; optional
research arm, not promoted to the default reproduction or model-board headline

## Candidate

The accepted reordered-Q8 block uses two independent integer DP4A chains with
striped packed-word pairing, `0->2` and `1->3`. A prior adjacent schedule,
`0->1` and `2->3`, was negative. This materially different candidate crosses
the second operations: `0->3` and `1->2`.

All four signed-byte dot products remain matched to their original activation
words. Their exact integer partials are added before the unchanged weight
scale, activation scale, FP32 per-block accumulation, and subgroup reduction.
The represented Q8 weights, floating-point operation order, tensor split, KV
format, and model graph do not change.

The candidate was built cleanly from the accepted DP4A2 x SG24 source with
oneAPI 2026.1.1 Release AOT for `bmg_g31`. Its hot object and library were
genuinely distinct:

- accepted `mmvq.cpp.o`: `b791488df254d024652f25c45f67612591bbb62d738a9b572ab2eb1d1dbe6225`;
- candidate `mmvq.cpp.o`: `c6c509b3bfed1e50572c33db5e80b1da613b571757f89685ef6ffe5e90c0ce63`;
- accepted SYCL library: `e75b960307fccee661073e67d8288b3893f421617ea83a100cf9b8f9de38b4b5`;
- candidate SYCL library: `ac16d9e83c830befa3d937848e5190a9513c3ed2b70b345fe140f3f9b7afe5fc`;
- candidate `llama-bench`: `a3b0a11425c4db508d71d876d1ec9c6bbace68ecc8bd88064818ea9b0f23de82`.

The exact source increment is
[`q8-dp4a-cross-deep-positive-20260817.diff`](../patches/q8-dp4a-cross-deep-positive-20260817.diff).

## Correctness gate

A strict TP2 p0/n1 smoke ran the candidate with Q8 hit verification enabled.
It compared all 1,980 live Q8 memo hits byte-for-byte and reported
`VERIFY_MISMATCH=0`. The integer regrouping is exact by construction.

The later service gate produced the same complete-output SHA-256 list as the
promoted Qwen3.8 oracle for all 48 responses, with `cached_tokens=0` for every
request. No speculation, MTP, DFlash, prompt reuse, or response reuse was
enabled.

## Direct long-decode gate

Two fully complementary p64/n512/r3 brackets used one candidate executable
and swapped only `libggml-sycl`, so all host libraries were identical. The
runtime was the accepted target-only equal-TP2 configuration with F16 KV,
FlashAttention, b1024/ub256, `level_zero:1,0`, and `SYCL0/SYCL1`.

| Order | Accepted striped DP4A2 | Crossed DP4A2 | Delta |
| --- | ---: | ---: | ---: |
| A-B-B-A | `37.229761500` | `37.505213000` | `+0.739869096%` |
| B-A-A-B | `37.138804000` | `37.427288500` | `+0.776773802%` |
| pooled eight processes | `37.184282750` | `37.466250750` | **`+0.758298881%`** |

The candidate was positive in both opposite orders, outside the ordinary
within-process variation. Performance runs used the production memo setting;
the strict verifier was confined to the preceding correctness smoke because
verifying every hit deliberately cuts throughput by more than half.

## Realistic endpoint decision

Two adjacent fresh-process pairs were run in opposite order, control then
candidate and candidate then control. Every suite used the fixed 12 unique
prompts once, generated up to 512 tokens, disabled the prompt cache, and
passed the complete-output oracle.

| Arm/run | Conventional first-100 median | Full decode median | Wall median |
| --- | ---: | ---: | ---: |
| control 1 | `36.694084653` | `36.557636977` | `36.095747908` |
| candidate 1 | `36.696181539` | `36.696926600` | `36.248178645` |
| candidate 2 | `36.694129247` | `36.787385770` | `36.270808947` |
| control 2 | `36.675655561` | `36.587837537` | `36.142352117` |

Pooled arm means:

- primary conventional first-100: `36.695155393` candidate versus
  `36.684870107 tok/s` control, **`+0.028036862%`**;
- full 512-token decode: `36.742156185` versus `36.572737257 tok/s`,
  **`+0.463238305%`**;
- full wall rate: `36.259493796` versus `36.119050012 tok/s`,
  **`+0.388835762%`**.

The long direct result and both full-decode endpoint pairs consistently favor
the crossed schedule at depth, but the repository's primary first-100 metric
is resolution-class neutral. Therefore this is retained as an exact optional
deep-generation candidate, not substituted into the default repro and not
used to raise the model-board or LocalMaxxing headline. A future retry must
target a materially deeper fixed endpoint suite or a different compiler/GPU;
do not rerun the same first-100 gate unchanged.

Raw local evidence is under
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-dp4a-cross/`.
No Xe fault, reset, hang, timeout, device-lost event, or kernel panic appeared,
and no hardware, PCI, power-management, driver, or kernel policy was changed.
