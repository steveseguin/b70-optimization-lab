# MiniMax Learnings To Reuse

The MiniMax M2.7 AutoRound path is the closest prior art. Relevant local
references:

- `/home/steve/llm-optimizations/notes/2026-05-08-minimax-autoround-vllm-xpu.md`
- `/home/steve/llm-optimizations/repro/minimax-m27-b70-89tps-20260520`
- `/home/steve/llm-optimizations/repro/minimax-m27-b70-110tps-ubuntu24-20260523`
- `/home/steve/llm-optimizations/localmaxxing_submissions.md`

## Process That Worked

1. Make the model fit without silently changing quality.
2. Keep every benchmark command and log path.
3. Record negative experiments with the same care as wins.
4. Separate tiny smoke tests from promoted benchmark results.
5. Require quality gates before publishing speed records.
6. Archive LocalMaxxing payloads and responses with stable labels.
7. Keep a reproducible folder once a path is promoted.

## Technical Patterns To Reuse

- Start with vLLM throughput random prompts before serving.
- Use `TP=4`, `distributed-executor-backend=mp`, and Level Zero affinity on the
  four B70 host.
- Prefer `CCL_ATL_TRANSPORT=ofi` and record `CCL_ZE_IPC_EXCHANGE`.
- Call out cold compile, warm rerun, and post-reboot differences separately.
- Inspect runtime with the existing vLLM runtime script where possible.
- Avoid `--enforce-eager` unless compiled/XPU graph paths are broken.
- For AutoRound W4A16 MoE, keep experts quantized. Unquantized MoE fallback is
  an OOM path and not a valid speed comparison.

## Quality Rules To Keep

- No speed submission without non-degenerate text checks.
- No speculative decoding unless target verification is clearly active.
- No result promotion if graph capture skips a correctness-critical collective
  or per-rank reduction.
- Record exact token hashes once deterministic prompts exist for the model.
- Treat "faster but wrong" as a finding, not a record.

## MiniMax-Specific Work Not To Copy Blindly

- MiniMax Q/K RMS collective fixes are architecture-specific.
- MiniMax attention delayed allreduce is unlikely to map directly to DeepSeek
  V4 sparse MLA.
- MiniMax llm-scaler MoE kernels may help with W4A16 MoE ideas, but DeepSeek V4
  has different routing, top-k, expert count, and hidden/intermediate sizes.
- The promoted MiniMax serving config is not a good initial DeepSeek config;
  DeepSeek V4 must start with small context until KV/cache behavior is known.
