# Qwen3.8 TP1 stacked INT4 cross-process D7 result

Date: 2026-08-31

Status: **negative causal screen; 78/78 cases exact**

All six TP1 stacked runtime widths repeated bitwise at M=1 and every actual
strict-suite prefill row count. Each case repeated within a process, all four
fresh-process hashes matched, and the four complete receipts were
byte-identical. This closes the TP1 width gap that D1 did not test.

The result rules the screened standalone oneDNN INT4 calls out. It does not
cover model-loader stacking/packing or prove whole-model determinism. D8 will
hash every loaded parameter and buffer after vLLM constructs the real model in
fresh processes.

Structured result:
`../data/2026-08-31-qwen38-tp1-stacked-int4-cross-process-d7-result.json`.

Raw evidence remains under
`/mnt/fast-ai/bench-results/qwen38-tp1-stacked-int4-cross-process-20260831-d7`.
