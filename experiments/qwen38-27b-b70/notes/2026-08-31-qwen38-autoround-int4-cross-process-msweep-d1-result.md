# Qwen3.8 AutoRound INT4 cross-process M-sweep D1 result

Date: 2026-08-31

Status: **negative TP2-component screen; 104/104 shape/M cases exact**

All eight preregistered **TP2 per-shard component widths** repeated bitwise
within each process and produced one identical SHA-256 across four fresh
containers at M=1 and all 12 strict-suite prefill row counts (48--78). The four
complete process receipts were byte-identical (`e3c6ffc6...966d`).

Audit correction: this closes the M-axis gap only for those TP2 component
widths. It does **not** cover the failing TP1 deployment's stacked runtime
widths (notably attention QKV/gate, GDN QKVZ, and merged MLP gate/up). The
earlier phrase "all production shapes" was too broad and is withdrawn. Do not
broaden or remove the oneDNN INT4 pad on this evidence. It is a negative scoped
operator diagnostic, not model correctness or performance authority.

The TP1 stacked widths require a separate cross-process screen.

Condensed structured result:
`../data/2026-08-31-qwen38-autoround-int4-cross-process-msweep-d1-result.json`.
The complete raw result remains under the immutable campaign root with SHA-256
`adfc3c3d...1305`.
