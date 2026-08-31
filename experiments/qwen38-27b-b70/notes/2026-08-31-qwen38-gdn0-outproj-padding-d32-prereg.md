# Qwen3.8 layer-0 GDN out-projection padding D32 preregistration

Date: 2026-08-31

Status: **preregistered before D32 model requests**

D31r proves that bit-identical input to layer 0's loaded INT4 `out_proj`
produces a different M=1 result in each fresh process. D32 retains the frozen
TP1 eager MTP0 workload and, on decode call 2 only, evaluates the same loaded
projection twice at padded row counts 1, 2, 4, 8, 16, 32, 64, 128, 256, and
512. Only row 0 contains the real normalized input; all other rows are zero.
The ordinary M=1 result remains the model result.

Each size must be bit-identical within each process and across all four fresh
processes to be a repair candidate. Select the smallest passing size. This is
a causal diagnostic, not a performance or quality claim.
