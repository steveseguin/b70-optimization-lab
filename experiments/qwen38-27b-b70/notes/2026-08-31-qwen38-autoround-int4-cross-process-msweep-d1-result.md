# Qwen3.8 AutoRound INT4 cross-process M-sweep D1 result

Date: 2026-08-31

Status: **negative causal screen; 104/104 shape/M cases exact**

All eight production INT4 GEMM shapes repeated bitwise within each process and
produced one identical SHA-256 across four fresh containers at M=1 and all 12
strict-suite prefill row counts (48--78). The four complete process receipts
were byte-identical (`e3c6ffc6...966d`).

This closes the actual MTP0 decode/prefill coverage gap left by the earlier
M=65-only screen. Do not broaden the oneDNN INT4 pad on this evidence. It is a
negative operator diagnostic, not model correctness or performance authority.

Next, compare two fresh TP1 eager native-GDN servers. That separates
Inductor/AOT from a shared rank-local runtime or recurrent-state defect.

Condensed structured result:
`../data/2026-08-31-qwen38-autoround-int4-cross-process-msweep-d1-result.json`.
The complete raw result remains under the immutable campaign root with SHA-256
`adfc3c3d...1305`.
