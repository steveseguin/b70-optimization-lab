# Qwen3.6 exact-depth process-census repair

Date: 2026-08-25. Scope: queued and fresh campaigns only.

The Q4_K_M q8_0-KV r1 campaign exposed a false-positive boundary in the shared process census. Searching every process's complete command line for `llama-bench` also matches ordinary evidence tools whose later arguments name `llama-bench.json` or `llama-bench.stderr.log`. R1 therefore failed closed after its benchmark and parser passed.

Fresh Q4_K_M q8_0-KV r2 and the still-queued UD-Q4_K_XL wrappers use the bounded correction: llama executables are classified by exact `comm` or executable `argv[0]` basename, including Linux's truncated `llama-batched-b` comm. vLLM is classified by exact EngineCore identity, a Python `-m vllm.entrypoints…` pair, or a real `vllm serve` executable/verb pair. Regression fixtures prove that `bash`, `sha256sum`, `tail`, and `rg` may mention evidence filenames or vLLM-like log names without being classified as model processes, while the real llama and vLLM process forms remain blocked.

The completed Q4_K_M F16 runner is not changed. It remains the exact source artifact for its completed campaign. Q4_K_M q8 r2 overrides the classifier in the fresh wrapper instead of rewriting that history.

The Q4_0 F16 wrapper is also not changed. Its inherited broad `pgrep -af` census ran only before the GPU subprocess; unlike the Q4_K_M failure path, it has no post-benchmark idle scan. The Q4_0 F16 campaign had already completed before this repair was prepared. Modifying its wrapper afterward would detach the checked-in source from the code that actually produced the receipt. Future wrappers must use the exact comm/`argv[0]` classifier rather than inheriting that historical scanner.
