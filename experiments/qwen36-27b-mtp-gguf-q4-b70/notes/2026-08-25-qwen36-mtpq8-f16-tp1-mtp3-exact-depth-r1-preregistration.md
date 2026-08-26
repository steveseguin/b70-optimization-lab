# Embedded-Q8 MTP3/F16 TP1 exact-depth R1 preregistration

This create-only packet measures the proven embedded-MTP Q8 artifact at TP1,
MTP3, F16 target/draft KV, and graph off at exact active contexts
0/2/4/8/16/24/32K. It uses the known-good llama.cpp `15586e2d` VDR2 runtime,
not the newer graph-patch runtime and not the Q4_K_M MTP1 lane.

One fresh MTP0 server lifetime runs the seven cache-disabled exact-token
fixtures in ascending order. A second fresh MTP3 lifetime repeats the same
seven requests, then runs the exact/JSON/arithmetic/copy, repeat-stability, and
approximately 29.4K needle battery. Each candidate depth must produce a new,
conserved draft-counter receipt and exactly match the corresponding MTP0
output-token hash. Every exact-depth and quality request must report zero
cached tokens. There is no speed floor.

The two-lifetime design avoids fourteen model reloads. It does not weaken the
per-cell gates: prompt caching, context checkpoints, context shift, graph, and
KV unification are disabled, while the exact-depth client checks the submitted
token count, returned usage, cache count, output length, and 99-interval timing
for every request.

Static inspection is inert:

```bash
python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r1.py --check
```

Execution requires a clean pushed `main`, all four canonical locks, idle GPU0,
the exact acknowledgement printed by `--check`, and a nonexistent ext4 output
root. The runner never builds source or launches a graph. A passing terminal
may contribute seven scoped MTP3 serving cells after separate result review;
it cannot replace protected graph-off values, change a featured headline, or
authorize a graph, TP2/TP4, cross-artifact, or LocalMaxxing claim.
