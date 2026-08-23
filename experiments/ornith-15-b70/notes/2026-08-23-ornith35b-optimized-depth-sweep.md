# Ornith 1.5 35B-A3B optimized context-depth sweep

Date: 2026-08-23

The complete accepted eight-feature patch stack was measured on one Intel Arc
Pro B70 at existing context depths 0, 2,048, 4,096, 8,192, 16,384, 24,576, and
32,768 tokens. Each depth used `llama-bench` `pp2048` and `tg128`, five
repetitions, flash attention on, F16 KV, graph off, and one unchanged model
load. Every published point comes directly from a raw benchmark row; no value
is interpolated or extrapolated.

Decode measured 125.830789 tok/s at depth zero, 113.113549 tok/s at 8K, and
90.323869 tok/s at 32K. Prefill measured 1402.996941 tok/s at depth zero,
1286.068940 tok/s at 8K, and 1100.398253 tok/s at 32K.

Canonical evidence and the generated chart are in
`repro/ornith-15-35b-a3b-q4km-b70/`:

- `ornith-15-35b-a3b-q4km-optimized.sweep.json`
- `ornith-15-35b-a3b-q4km-optimized.meta.json`
- `optimized-depth-sweep.svg`

The stock patch-off sweep is retained separately for historical comparison.
These raw engine rates must not be presented as server-suite rates.
