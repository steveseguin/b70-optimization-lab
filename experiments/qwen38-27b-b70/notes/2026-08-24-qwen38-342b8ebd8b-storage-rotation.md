# 342b stale-build storage rotation

Date: 2026-08-24. Status: **complete; archive integrity and recovery inputs
verified before exact local removal.**

The 342b source identity was already stale and both qualification attempts were
closed. After the 0d7 build, root headroom was below the unchanged 12-GiB GPU
launch reserve. Unused Docker builder cache was removed first; no runtime image
or evidence was pruned. The two exact 342b images were then exported together
to:

```text
/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/current-main-builds/20260824T174812Z-342b8ebd8b-baaa05bb4e/images-342b8ebd8b.docker.tar.zst
```

Before local removal, the archive passed:

- SHA-256 `82f9741730decae4b4fa7195bb8a2075c83a9d4688cba76eb924eb567e7039d7`;
- `5,805,379,860` compressed and `5,819,693,568` uncompressed bytes;
- `zstd -t`;
- 51 unique, traversal-safe tar entries;
- exactly two expected tags and exact OCI index digests;
- 28 layers for each image;
- checksum sidecar SHA-256
  `8f744dffc36c81ba2bc9756d0ec286fe8575693c989f72f57e24f7cc440c89c5`.

Only after those checks passed were these exact stale local IDs removed:

```text
sha256:6dbd46c8d22c3fdb425dfe343e759a89c5aa443eb99f411b4f6d923eae2e54ae
sha256:23fe2e1c88e2c0f5c69b00370687a07c2c49aa1f4fea903ff9416b0223690c37
```

The 342b build root, wheel, logs, receipts, benchmark/quality evidence, and
result records remain. The 0d7 and 6a9 image pairs, nightly base, qualified
stock controls, TP2 78-decision artifact, and TP4 152-decision artifact were
explicitly retained. Root free space rose from `8,892,812` to `16,234,256`
KiB. No protected speed, result classification, or overlay changed.

Restore without rebuilding with:

```bash
archive=/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/current-main-builds/20260824T174812Z-342b8ebd8b-baaa05bb4e/images-342b8ebd8b.docker.tar.zst
zstd -dc "$archive" | sudo docker load
```

The machine-readable receipt is
[`2026-08-24-qwen38-342b8ebd8b-storage-rotation.json`](../data/2026-08-24-qwen38-342b8ebd8b-storage-rotation.json).
