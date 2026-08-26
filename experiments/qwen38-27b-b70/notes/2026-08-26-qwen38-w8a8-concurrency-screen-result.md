# Qwen3.8 FP8-to-W8A8 concurrency screen: 952.58 tok/s ceiling, rejected

This screen tested whether repacking the official Qwen3.8-27B block-FP8 body
to oneDNN W8A8 could move the two-B70 HTTP concurrency lane beyond 875 tok/s.
It did on speed, but not on quality. The complete compact result is
[`../data/2026-08-26-qwen38-w8a8-concurrency-screen-summary.json`](../data/2026-08-26-qwen38-w8a8-concurrency-screen-summary.json).

## Outcome

The fastest exploratory candidate measured `952.58 tok/s` at 64 simultaneous
users after warmup, versus the matched supported-FP8 P2P control's measured
`774.85 tok/s`. Its single-user rate was `32.46-32.48 tok/s`, versus
`21.53 tok/s` for that control. These are measured values at a 256-token
service limit; they are not long-context results and are not extrapolated.

The candidate is **not promotable**. Its first small quality screen passed all
seven sequential exact-answer cases, five repeat hashes, and 128/128 concurrent
answers. Larger independent gates then exposed output-changing failures:

- fresh clip `0.8175` plus INT8 head: `510/512` concurrent answers;
- the same body with the BF16 head restored: `764/768`;
- guarded oneDNN variants ranged from `452/512` to `959/1280`.

The supported FP8 control passed `384/384` under the same concurrent canary
method. Candidate failures included arithmetic `54`, `57`, or `58` where `60`
was required, and code result `30` where `14` was required. They therefore
cannot be dismissed as harmless token-ID or phrasing differences.

The speed mechanism itself is real. Production-shape attribution fixtures
measured the INT8 body GEMMs at roughly `43 us` for attention QKV and `115 us`
for each large MLP projection at `M=64`; the sharded output head measured a
`1.26x` operator-level speedup. Those fixtures are stored under
`../data/qwen38-int8-gemm-production-shapes-r30/`,
`../data/qwen38-int8-gemm-production-shapes-f16-r31/`, and
`../data/qwen38-lm-head-int8-production-shape-r29/`. They are explicitly
operator microbenchmarks, not endpoint throughput claims.

## What the screen ruled out

- Two `max` reductions and activation clipping can make a sequential smoke
  look clean, but a fixed clip ratio is not robust across fresh graphs and
  mixed live batch shapes.
- The INT8 output head is a real speed win, but removing it did not remove the
  body failures.
- Keeping selected early layers in FP8 did not monotonically improve the two
  boundary cases.
- P2P-off was slower (`~820 tok/s` at 128 users) and still failed a larger
  concurrent gate.
- A 64-token W8A8 / smaller-batch FP8 dual path cannot repair a first token
  already chosen incorrectly at batch 64.
- Explicit PyTorch-to-oneDNN input and completion dependencies changed the
  failure distribution but did not restore quality.
- Scratchpad ring sizes 1, 16, and 64, plus a zero-scratch diagnostic, changed
  outputs. None passed the control-matched gate. Ring64 and zero-scratch are
  negative diagnostics and were not retained as candidate changes.

## Decision

`952.58 tok/s` is retained only as a research speed ceiling. It must not appear
on the neural.download model board as a validated result and must not become a
beginner package. The 875 objective remains open for a quality-qualified lane.
The next credible approaches are more accurate activation quantization or a
target-verified speculative path; further prompt-specific clip tuning is
closed.

The reusable concurrent exact-answer harness added by this campaign is
[`../scripts/qwen38-concurrent-quality-canary.py`](../scripts/qwen38-concurrent-quality-canary.py).
It records every measured response and explicitly marks that no result is
extrapolated.

For audit and continued kernel research, the exact experimental source deltas
are preserved as the
[vLLM patch](../patches/vllm-qwen38-w8a8-body-head-experimental-20260826.patch)
and
[vLLM XPU kernels patch](../patches/vllm-xpu-kernels-qwen38-w8a8-body-head-experimental-20260826.patch).
They reverse-check exactly against the isolated worktrees used here. They are
not a supported recipe: applying them reproduces an experimental mechanism,
not a quality-qualified result.
