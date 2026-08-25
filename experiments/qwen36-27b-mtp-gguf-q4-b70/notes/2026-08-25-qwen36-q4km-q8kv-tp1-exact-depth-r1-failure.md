# Qwen3.6 Q4_K_M q8_0-KV TP1 exact-depth r1 failure

Date: 2026-08-25. State: **failed closed; no matrix cells published**.

The preregistered `llama-bench` process completed successfully, and the exact-depth parser passed all seven requested cells. The raw root contains seven complete depth points, graph-off metadata, the expected model/runtime identity, and a successful parser receipt.

The campaign nevertheless failed its frozen post-benchmark cleanup gate. The process scanner searched every process's full command line for the substring `llama-bench`. At the same time, evidence tooling was hashing files named `llama-bench.json`; the scanner therefore reported the harmless `bash` and `sha256sum` processes as active model processes. The repeated cleanup scan made the same false match, so the terminal receipt correctly recorded `state=failed` and `cleanup_passed=false` under the frozen r1 rules.

The create-only evidence root is `/mnt/fast-ai/bench-results/qwen36-q4km-q8kv-tp1-exact-depth-20260825-r1`. The tracked failure record preserves the immutable hashes and diagnostic-only rows at `experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-q4km-q8kv-tp1-exact-depth-r1-failure.json`.

R1 remains a failure diagnostic. Its complete-looking rows must not be promoted after the fact. A fresh r2 may reuse the checksum-pinned model/runtime/config identity, but it must use a new create-only root and a preregistered process classifier that recognizes llama programs only by exact process name or executable `argv[0]`. Evidence filenames in later arguments must be explicit negative regression fixtures.
