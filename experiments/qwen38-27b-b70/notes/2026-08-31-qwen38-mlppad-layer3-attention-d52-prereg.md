# D52 preregistration: repaired-MLP layer-3 attention split

Date: 2026-08-31

This synchronized causal diagnostic is preregistered before D51 completes and
is not a performance or quality claim. If D51 places the first split at layer
3 full attention, D52 will retain the all-layer dense-MLP repair and reconstruct
the production full-attention path at prefill call 2. It hashes the exact input,
input norm, packed QKV projection, post-norm/post-RoPE Q and K, V, output gate,
raw attention result, gated attention result, output projection, post-attention
norm/residual, and repaired MLP output.

The run is authorized only if D51 implicates attention. It uses four fresh TP1
processes on GPU 0, the frozen local ext4 model and image, eager mode, disabled
prefix caching, isolated cache directories, and the frozen `sql-debugging`
screen. The first stage with multiple hashes is the finding. Snapshot-induced
synchronization is intentional localization instrumentation; no measured speed
is publishable and complete-text agreement cannot erase an internal split.
