# Qwen target-Q8/F16 TP1 fa0 graph-port parent sentinel R4

State: **sealed, preregistered, inert, and not launched**.

R4 repeats only the same 64-token graph-off/cache-zero versus
graph-on/cache-eight parent sentinel on the final cache-scaled pointer-stable
Q8 memo source. It uses a distinct campaign, acknowledgement, and create-only
result root ending in `r4`.

The source is sealed at `ce4c8541...` for `common.hpp` and `25152136...` for
`ggml-sycl.cpp`; the incremental capacity patch is `3def9e5e...` and must be
reverse-applicable. The rebuilt `llama-cli` remains `68ab26cf...`; the backend
is `7d03bc06...`.

The effective closure was regenerated from the actual launcher with the frozen
oneAPI library path. It still contains 34 rows, but two—not one—changed:
`libggml-sycl.so.0` and `libllama-server-impl.so`. R4 seals both changes and
re-resolves every DSO during `--check`.

No predecessor static check is called: R4 independently verifies final source,
reverse patch applicability, build receipts, model identity, and the complete
effective DSO closure.

Even a pass is parent-sentinel-only. It grants no curve, site, speed, quality,
record, TP2/TP4, or protected-value replacement authority.

```text
RUN qwen36-q8-f16-tp1-fa0-graph-port-sentinel-20260825-r4
```

```text
/mnt/fast-ai/bench-results/qwen36-q8-f16-tp1-fa0-graph-port-sentinel-20260825-r4
```
