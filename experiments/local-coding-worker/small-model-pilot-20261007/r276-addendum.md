# Second runtime candidate: existing R276 container

The host-venv attempt is closed before model load, with zero inference requests.
Its XPU platform import could not resolve `libgdn_attn_kernels_xe_2.so` even
though the library exists locally. This is a loader-path failure, not evidence
of a hardware fault or a proven ABI mismatch. All four cards passed both health
checks; render nodes were idle afterward. The original evidence is preserved
in [venv-failure](venv-failure/summary.json); the host runtime was not changed.

Use the already installed base R276 container next, rather than repairing that
editable environment. Immutable image ID:
`sha256:521eb277c0733f8c2ce47aea1bb98ed576c6f1ad63bf5baf22d38fc07abf54ad`.
CPU-only container checks passed for XPU platform import and the Qwen3.5 model
architecture. Runtime: vLLM0.27.2rc1.dev77+gac7509e2b.xpu, torch2.13.0+xpu,
transformers5.15.0. These checks did not load a model or access a GPU.

The container must run from `/tmp` with its installed site-packages explicitly
selected, avoiding the other vLLM source copy in its default working directory.
Disable its optional linear row-chunk, graph, GDN split/speculative and draft-head
optimizations. Patched kernels are still intrinsic to this pinned image: this is
an R276 pilot, not an unmodified stock-runtime result.

This is one separately identified container startup, not a retry policy. Retain
the existing BF16/no-MTP/eager16K profile and the one-canary, two-task gates.
No rebuilding, new model download, inference retry or server restart is planned.
The supervisor owns the actual container identity through graceful shutdown
and verifies that it stopped; Docker CLI exit alone is insufficient.
