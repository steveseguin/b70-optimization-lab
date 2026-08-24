# 7797 stale-build storage rotation

Date: 2026-08-24. Status: **complete; recovery verified before exact local
removal.**

The 7797 build became stale before r2 launch, but its USB build packet did not
yet contain a Docker image archive. Keeping both stale images while building a
successor would have left less than the unchanged 12-GiB qualification reserve.
No broad Docker prune was used.

Both exact tags were exported together to:

```text
/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/current-main-builds/20260824T153134Z-7797b6022c-baaa05bb4e/images-7797b6022c.docker.tar.zst
```

The archive is Docker-loadable and verifies as follows:

- SHA-256 `849a4849fa89399d2726f1dfa4d5a057be463ca49ad3d5853d2fd85e19880318`;
- `5,798,607,216` compressed and `5,819,691,008` uncompressed bytes;
- `zstd -t` passes;
- 51 unique, traversal-safe tar entries;
- exactly two tags and their exact OCI index digests;
- 28 layers for each image;
- six-file append-only rotation manifest SHA-256
  `1001215e59fbb3752abfa2ff39db5cdecd0aa8e215970f80b8631552e173eaee`.

The 9,569-file, 1,188-directory build root was relocated beside the image
archive. All `924,176,258` file bytes reproduce the pre-move content manifest
`cc562994343df30aee925b6f49586b5a6e44fd09907d8a614665781fcba33cf0`.
Because the USB filesystem is NTFS/fuseblk, its exposed POSIX modes normalize
to `0755`; do not claim metadata preservation. The source Git tar, wheel,
image archive, receipts, logs, and file checksums retain every reproducible
identity and payload needed from the build.

Only after all archive, content, and original 14-file packet checks passed were
the two exact stale local IDs removed:

```text
sha256:295de005ad89735c92aced11179d05db08dd694badff3722de3f1ceb9e5994f1
sha256:a385f20ca68b62f18d670722617ed69583fe9154b537c108f04b704029950abd
```

The official base, qualified 0ecc stock image, 79bb stock image, all run
evidence, and TP2 78-/TP4 152-decision artifacts remain. Root free space rose
from `14,422,744` to `22,689,052` KiB (21.64 GiB). The removed pair can be
restored without rebuilding:

```bash
archive=/mnt/usb-models/llm-optimization-artifacts/qwen-current-main-transition-20260823/current-main-builds/20260824T153134Z-7797b6022c-baaa05bb4e/images-7797b6022c.docker.tar.zst
zstd -dc "$archive" | docker load
```

The complete machine-readable receipt is
[`2026-08-24-qwen38-7797b6022c-storage-rotation.json`](../data/2026-08-24-qwen38-7797b6022c-storage-rotation.json).
