# Qwen3.8 GDN out-projection prefill pad D35r preregistration

Date: 2026-08-31

Status: **preregistered before D35r model requests**

D35's global INC-linear hook crashed during engine initialization and is
technical-invalid. D35r changes only the already isolated layer-0 GDN
`out_proj` at call index 2. It reconstructs the production stages exactly as
D31r, creates an M=512 tensor from the bit-identical `[71, 6144]` normalized
input through dispatcher-visible XPU operations, invokes the unchanged loaded
projection, slices the first 71 rows, records every boundary, and returns that
output. All other model calls and all other INT4 layers are unchanged.

Across four fresh processes, the normalized input, output row zero, and full
output must each have exactly one hash. Row zero must equal D32's direct M=512
reference `bbec363c094e89d23a3fa5046063f358f63b67e4dfa50cddc5417cf608c524b5`.
All 64 generated token IDs must also be identical. A boundary pass permits a
model-scoped production patch; it is not itself a quality or speed claim.
