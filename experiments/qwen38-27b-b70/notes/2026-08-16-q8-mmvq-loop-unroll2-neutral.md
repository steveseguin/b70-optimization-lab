# Qwen3.8 Q8 reordered-MMVQ loop unroll: neutral

Date: 2026-08-16

## Hypothesis

Partially unrolling the dynamic reordered-Q8 block walks by two could expose
the next coalesced 16-byte load to the compiler while keeping each lane's
block order and FP32 accumulator boundaries unchanged. This differs from the
already-rejected explicit SYCL-prefetch experiment.

Five `#pragma unroll 2` directives were added: the shared reordered path, its
multi-column variant, and the accepted Q8 pair, triple, and recurrent-quad
bodies. The candidate MMVQ object differed from control in both size and
SHA-256, confirming that IntelLLVM did not discard the directives.

## Result

The candidate passed a real TP2 p64/n1 smoke with direct-Q8 mode 2, the
expected fusion census, `VERIFY_MISMATCH=0`, and a clean GPU gate. Two
complementary position-balanced brackets then used p64/n256/r3, equal TP2,
Q8_0 target weights, F16 KV, FlashAttention, b1024/ub256, and no speculation.

| Position | Arm | Decode tok/s | Within-process stdev |
| --- | --- | ---: | ---: |
| A1 | control | 36.016026 | 0.026903 |
| B1 | unroll-2 | 36.189471 | 0.042812 |
| B2 | unroll-2 | 36.825723 | 0.242363 |
| A2 | control | 36.842494 | 0.028402 |
| B3 | unroll-2 | 36.985258 | 0.101177 |
| A3 | control | 36.821349 | 0.080311 |
| A4 | control | 36.722325 | 0.132876 |
| B4 | unroll-2 | 36.513579 | 0.235053 |

The first bracket favored the candidate by `0.215%`; the complementary
bracket favored control by `0.061%`. Across all four positions per arm,
control averaged `36.6005485 tok/s`, candidate averaged `36.62850775 tok/s`,
and the net delta was only `+0.076%`. This is noise, not a promotable gain.

No endpoint or semantic-quality run was spent on a performance-neutral
candidate. The pragma is not in the promoted reproduction.

## Reproduction and retained evidence

- incremental patch: [q8-mmvq-loop-unroll2-neutral-20260816.diff](../patches/q8-mmvq-loop-unroll2-neutral-20260816.diff)
- structured result: [2026-08-16-q8-mmvq-loop-unroll2-neutral.json](../data/2026-08-16-q8-mmvq-loop-unroll2-neutral.json)
- local source: `/mnt/fast-ai/src/llama.cpp-q38-q8-loop-unroll2`
- local logs: `/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260816-loop-unroll2`

The first local smoke log used comma-separated devices and therefore emitted
two separate one-card rows; it was recognized immediately and is timing-
invalid. `smoke-tp2-p64-n1.log` uses the correct `SYCL0/SYCL1` group and is
the valid safety smoke.

