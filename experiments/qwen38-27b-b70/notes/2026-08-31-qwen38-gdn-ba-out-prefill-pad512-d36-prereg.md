# Qwen3.8 GDN BA + output prefill pad D36 preregistration

Date: 2026-08-31

Status: **preregistered before D36 model requests**

D35r proved the loaded GDN output projection gives the same complete result in
three processes that supplied the same input, and its row-zero value matched
the independent M=512 reference in all four. The fourth process diverged
upstream: its process-dependent loaded `in_proj_ba` result altered the recurrent
core and normalized output. QKVZ and hidden input remained exact.

D36 changes only layer-0 GDN call 2 in the diagnostic hook. It runs
`in_proj_ba` at M=512 from a dispatcher-ordered padded copy of the real M=71
hidden tensor, slices BA back to 71 rows, runs the production recurrent core
and norm, then applies D35r's M=512 treatment to `out_proj`. QKVZ and every
unrelated model call remain ordinary.

Across four fresh processes, BA, recurrent-core output, normalized tensor,
output row zero, and complete output must each have exactly one hash. Output
row zero must remain
`bbec363c094e89d23a3fa5046063f358f63b67e4dfa50cddc5417cf608c524b5`.
The 64 generated token IDs must be identical. A pass authorizes a model-scoped
production candidate only; strict varied-prompt quality, determinism, and cold
performance gates remain mandatory.
