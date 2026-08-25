# Qwen3.6 Q4_0 F16-KV TP1 exact-depth preregistration

Date: 2026-08-25. State: **preregistered; not launched**.

This packet targets seven missing Qwen3.6 cells: the checksum-pinned Q4_0
child, TP1, target-only MTP0, graph off, F16 K/V cache, and exact active
depths `0`, `2048`, `4096`, `8192`, `16384`, `24576`, and `32768`.

It is the F16-KV companion to the separately isolated q8_0-KV r2 campaign.
The packet uses the same exact Q4_0 model and build-9976 llama.cpp runtime so
the KV comparison does not silently change model or engine identity. It reuses
only checksum-pinned lifecycle infrastructure: complete resolved-library
verification, the exact-DSO graph-off proof, the exact-depth parser, all four
current and legacy GPU0 locks, the `llama-batched-bench` process exclusion,
and create-only receipts. No q8_0 row, failed q8 r1 row, or quality judgment is
transferred.

The F16 output root is fresh and distinct:
`/home/steve/qwen36-matrix-runs/q4-0-tp1-mtp0-f16kv-exact-depth-20260825-r1`.
The wrapper never reads, writes, renames, or resumes either q8 run root. If the
q8 r2 arm or any other campaign owns a shared lock or GPU process, F16 fails
before creating its root.

One frozen `llama-bench` invocation uses one B70, FlashAttention on,
`pp2048`, `tg128`, and five repetitions. There is no speed floor. A slower
long-context point is still useful evidence for this exact cell and cannot
lower or overwrite any featured, promoted, or historical speed. Passing adds
seven raw-engine cells only; this is not an HTTP serving result and it does not
run a fresh quality battery.

After this packet is committed and pushed on clean `main`, and only when the
q8 arm has reached a terminal state and all four locks and GPU0 are idle:

```bash
env -u LD_LIBRARY_PATH -u LIBRARY_PATH \
  python3 -B experiments/qwen36-27b-mtp-gguf-q4-b70/scripts/run-20260825-qwen36-q4-0-f16kv-tp1-exact-depth-r1.py \
  --execute \
  --ack 'RUN qwen36-q4-0-f16kv-tp1-exact-depth-20260825-r1 d1-exact-depths r1'
```

The default invocation is inert. `--check` performs only static CPU and file
identity checks and does not acquire a GPU or touch either campaign root.
