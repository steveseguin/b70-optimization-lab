# 6648 stale-build storage rotation

Date: 2026-08-24. Status: **complete; recovery verified before exact local
removal.**

The 6648 build became stale during its fresh TP1 diagnostic. Its original USB
packet passed all 14 checksums but did not yet contain Docker images or the
complete build root. Keeping both stale images while building the literal-newest
successor would also have reduced the qualification reserve. No broad Docker or
filesystem prune was used.

Both exact 6648 tags were exported together to:

```text
/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/current-main-builds/20260824T165532Z-6648eb118d-baaa05bb4e/images-6648eb118d.docker.tar.zst
```

The Docker-loadable archive verifies as follows:

- SHA-256 `697a3ad906d797474f29360855bcdfd7e6e607b93bfd510c9c6633b152b9428f`;
- `5,798,503,281` compressed and `5,819,692,544` uncompressed bytes;
- `zstd -t` passes;
- 51 unique, traversal-safe tar entries;
- exactly two expected tags and exact OCI index digests;
- 28 layers for each image;
- six-file append-only rotation manifest SHA-256
  `8414454007fd35dd1b4a169a2e542842d4e52803b37a559cda21264c8cd40e41`.

The 9,569-file, 1,188-directory build root was copied beside the image archive.
All `924,175,820` file bytes reproduce the source-side content manifest
`08035c593eef4d474f88da178cdc75675bbe0da278e83ae675fc4cdf39c5bcde`.
Because the USB filesystem is NTFS/fuseblk, do not claim POSIX metadata
preservation. The source Git tar, built wheel, image archive, receipts, logs,
and byte checksums preserve the reproducible identity and payloads.

Only after both the source and destination passed the same full manifest were
the two exact stale local IDs and duplicated ext4 build root removed:

```text
sha256:945b121e92ee023098fca39919329eed82d6ec5bd7ddb2c3ec3e5d1c47f3e545
sha256:00757757bb66515733395fbca3b26e752d3bea8c04e91b7c2a4e048190100e28
```

The live official nightly base, qualified 0ecc stock image, 79bb stock image,
raw 6648 hardware/campaign evidence, model files, and TP2 78-/TP4 152-decision
artifacts remain. Root free space rose from `13,889,548` to `22,053,912` KiB.
A separate Docker-builder-only prune then removed the now-unused archived-build
cache, no runtime image, and no evidence; final measured headroom was
`22,472,388` KiB (21.43 GiB). The builder cache is now empty.

The removed pair can be restored without rebuilding:

```bash
archive=/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/current-main-builds/20260824T165532Z-6648eb118d-baaa05bb4e/images-6648eb118d.docker.tar.zst
zstd -dc "$archive" | sudo docker load
```

The complete machine-readable receipt is
[`2026-08-24-qwen38-6648eb118d-storage-rotation.json`](../data/2026-08-24-qwen38-6648eb118d-storage-rotation.json).
This operation changes no captured speed, result classification, overlay, or
qualification. The next action remains a fresh build from the literal newest
vLLM and XPU-kernel heads over the live official nightly, followed by a newly
named TP1 packet and then TP2/TP4.
