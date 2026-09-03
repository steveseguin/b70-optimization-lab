# Qwen3.8 Flash-Next FP8 A68 client admission negative

Date: 2026-09-02 21:52--22:08 EDT
Status: procedural negative; no request reached the server; no promotion claim

A68 (the A67 full-decode-graph deterministic-oneDNN server with the bounded
root-NVMe read cap raised to 64 GiB) loaded normally: four
`mkldnn.deterministic=True` lines, weights at 22:03, healthy at 22:07. The
frozen client then exited 1 at its first hash pin:

```
sha256sum: .../tools/verify-q38-a48-fullgraphdet-runtime.py: No such file or directory
```

The A59-to-A67 generator renames the `fullgraph` token to `fullgraphdet` in
every non-hash segment, which also rewrote the client's pinned helper file
name `verify-q38-a48-fullgraph-runtime.py`. The supervisor tore the server
down when the client exited (final status 143); no request, quality row,
or speed row exists, and the kernel log holds no GPU event.

A69 (`tools/rewrite-q38-a67-to-a69-battery.py`) is A68 with the helper file
name restored in the client; the helper's pinned SHA-256 is unchanged
because the file never moved. Attempt 69 / port 19741. The A68 prereg's
reading rules apply to A69 unchanged. The A67 client carries the same
renamed pin but was never run (A67 used the probe).
