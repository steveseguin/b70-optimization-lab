# MiniMax M2.7 Allreduce Async-Wait Screen Negative

Date: 2026-05-21

## Candidate

Screened `VLLM_XPU_ALLREDUCE_ASYNC_WAIT=1` on top of the promoted 4x B70
MiniMax M2.7 AutoRound INT4 recipe. This keeps the same model math and still
waits for each collective, but it routes the runtime XPU `dist.all_reduce`
through `async_op=True` plus `work.wait()`.

The goal was to test whether the oneCCL/PyTorch async work-handle path reduced
per-collective framework overhead for the current clone-safe custom allreduce
stack.

## Result

Screen only; no LocalMaxxing submission.

- Model: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- Hardware: 4x Intel Arc Pro B70 32GB
- Engine: vLLM XPU, TP4, llm-scaler WS INT4 path
- Shape: p512/n1536, ctx2048, batch 1, `max_num_batched_tokens=512`,
  block size 256
- Compilation: PIECEWISE graph with `compile_sizes=[1]`
- Repeats: 4 warm in-process repeats after one warmup
- Output tok/s: `82.752554`, `82.736696`, `82.806481`, `82.765218`
- Mean output tok/s: `82.765237`
- Mean total tok/s: `110.353650`
- Output tok/s stdev: `0.029869`

Current same-method promoted warm controls are about `92.3-92.9` output tok/s,
so this candidate is roughly 10-11% slower.

## Decision

Reject. Do not run the full strict quality gate and do not submit to
LocalMaxxing. The candidate is a software-only communication-path toggle, but
the performance regression is too large to justify further validation.

Keep the default synchronous `dist.all_reduce` path for promoted runs.

## Artifacts

- JSON:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/allreduce-async-wait-screen-20260521T082822Z/minimax-allreduce-async-wait-screen-p512n1536.json`
- Log:
  `/home/steve/bench-results/minimax-m2.7-post-repro-optimization/allreduce-async-wait-screen-20260521T082822Z/minimax-allreduce-async-wait-screen-p512n1536.log`
- Data summary:
  `data/minimax-m27-allreduce-async-wait-negative-20260521.json`
