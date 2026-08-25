# Clean fa0 graph-port build result

The focused two-file graph cache/evidence port built successfully on the exact
`fa0f3b25` Qwen optimization base. Both `llama-bench` and `llama-cli` linked,
and the 329 MB AOT `libggml-sycl` contains the new cache/evidence markers.

The runtime-relevant CMake delta from the proven graph-off sibling is only
`GGML_SYCL_GRAPH=OFF` to `ON`. DNN and host-memory fallback remain off, the
target remains `bmg_g31`, and dynamic GGML backend loading is off. A separate
compile-command cache-typing difference is recorded as non-runtime metadata.

This is a build result, not GPU evidence. It changes no existing graph-off
measurement or protected featured speed and grants no curve, quality, website,
or LocalMaxxing authority. The next gate is the committed same-new-binary
Q8/F16 TP1 graph-off/on parent sentinel.
