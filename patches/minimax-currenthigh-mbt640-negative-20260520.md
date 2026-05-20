# MiniMax Current-High MBT640 Negative

This was a recipe/env-only screen. No source patch is required to reproduce it.

Run the current promoted MiniMax stack with this scheduling change:

```bash
LABEL=minimax-currenthigh-mbt640-20260520 \
MAX_BATCHED_TOKENS=640 \
BENCH_REPEATS=4 \
RUN_EXTENDED_QUALITY=1 \
RUN_REPEAT_ARITHMETIC_QUALITY=1 \
REPEAT_ARITHMETIC_RUNS=16 \
/home/steve/llm-optimizations-publish/scripts/run-minimax-strict-quality-gated-candidate.sh
```

All other current-high env flags should match `notes/2026-05-19-minimax-moe-full-forward-customop-plus-output-ar.md`.

Outcome: strict quality passed, but mean output was `88.835750` tok/s versus the promoted `89.314195` tok/s. Keep `MAX_BATCHED_TOKENS=512` for promoted p512/n1536 MiniMax runs.
