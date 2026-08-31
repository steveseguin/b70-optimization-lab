# Qwen3.8 decoder layer-7 trace D12 result

D12 reproduced the token-60 branch (two runs per token) with identical
positions and four different layer-7 hidden-state/residual receipts. The defect
is at or before layer 7. Only layer 7's post-execution output was synchronized.

Layer 3 is the next boundary: it separates the first three GDN layers from the
first full-attention layer and layers 4–7. No performance claim is promoted.
