# Qwen3.8 layer-0 GDN-output call-2 D30 result

D30 is a positive causal finding. All four fresh processes reached decode call
2 with the same token (369) and the same output history, but the complete
layer-0 `QwenGatedDeltaNetAttention` output had four different SHA-256 hashes.
The first generated-token difference remained at index 60.

This excludes the decoder layer's later post-attention norm and MLP from the
first divergence. The defect is in the GDN path: its input projections,
convolution/recurrent state update, gated norm, or output projection. D31
captures those production boundaries without synchronizing before the suspect
operation.
