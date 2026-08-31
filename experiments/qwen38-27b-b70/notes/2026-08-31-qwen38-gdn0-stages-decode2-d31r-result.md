# Qwen3.8 layer-0 GDN stages call-2 D31r result

D31r completed across four fresh processes with identical token histories.
The boundary comparison is decisive:

| Boundary | Unique SHA-256 hashes |
| --- | ---: |
| hidden input | 1 |
| QKVZ projection | 1 |
| BA projection | 4 |
| recurrent core before norm | 1 |
| output gate | 1 |
| gated norm / flattened norm | 1 |
| final `out_proj` | **4** |

The BA projection contains process-dependent bits, but they did not alter the
recurrent-core output in this observed transition. The final INT4
`out_proj`, given bit-identical input, directly creates the first layer-output
divergence. This production-weight finding supersedes the standalone D7
negative screen for this boundary; D7 did not exercise the model-loaded
projection and its primitive state.

D32 sweeps small row padding on this exact loaded projection to find the
lowest deterministic decode shape before implementing a general repair.
