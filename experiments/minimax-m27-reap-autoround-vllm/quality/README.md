# Quality Gate

Minimum gate before speed claims:

1. Deterministic short quality smoke with `run-vllm-minimax-quality-check.py`.
2. Repeat arithmetic or raw canary runs if the short smoke is clean.
3. Decode benchmark only after text quality is sane.
4. Compare output behavior against the production Lasimeri MiniMax M2.7 lane before promoting any REAP-specific optimization.

LocalMaxxing submissions require a clean quality record and repeatability summary in `results/`.
