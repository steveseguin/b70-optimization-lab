# Qwen3.6 Q4_K_M q8_0-KV TP1 exact-depth r2 preregistration

Date: 2026-08-25. State: **preregistered; not launched**.

R1 completed the GPU benchmark and exact-depth parser but failed closed because its full-command-line process census mistook evidence hashing of `llama-bench.json` for a running model process. R1 remains immutable diagnostic evidence and contributes zero publishable cells.

R2 repeats the same seven exact depths, model, runtime, arguments, graph-off mode, and q8_0 K/V cache in a fresh create-only root. Its only mechanism change is the process classifier: llama programs are recognized by exact process name or executable `argv[0]` basename. vLLM is recognized by exact EngineCore identity, a Python `-m vllm.entrypoints…` token pair, or a real `vllm serve` executable/verb pair. A shell, hasher, tailer, or search process may mention those strings in an evidence filename or later command argument without becoming a model process.

The classifier is regression-tested with negative evidence-filename fixtures and positive `llama-bench`, `llama-batched-bench`, `llama-server`, truncated comm, and vLLM fixtures. There is no speed floor and no new quality gate.

Launch only from clean pushed `main`, with all four locks and the host idle:

```bash
python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q4km-q8kv-tp1-exact-depth-r2.py \
  --execute \
  --ack 'RUN qwen36-q4km-q8kv-tp1-exact-depth-20260825-r2'
```
