# Qwen3.8 global Python INT4 prefill pad D35 result

D35 is **technical-invalid**. Process 1 segfaulted during engine initialization
immediately after checkpoint loading and before readiness or any model request.
There is no determinism, quality, or performance result.

The hook applied M=33…511→512 to every INC INT4 linear, including vLLM's
initialization/profile execution. That scope was broader than the proven
boundary and changed unrelated model-loading/runtime surfaces. GPU state
remained normal, the kernel journal contained no GPU/reset/I/O fault, and the
host retained 13 GiB available memory after the container exited.

D35r narrows the diagnostic to the exact loaded layer-0 GDN `out_proj` call
isolated by D31r. No global quantized-linear method is modified.
