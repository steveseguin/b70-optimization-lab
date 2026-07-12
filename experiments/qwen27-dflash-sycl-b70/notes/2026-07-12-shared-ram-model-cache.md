# 2026-07-12 Shared-RAM Model Cache

## Result

Implemented and exercised an identity-checked, byte-identical RAM cache for the
Qwen27 target and DFlash GGUFs. This is a development-initialization artifact,
not the planned B70 reordered-weight pack and not a decode optimization.

The source models are on external NTFS (`/dev/sda2`). The internal NVMe had only
14 GiB available, which is less than the 16,056,476,800-byte target file, so a
second on-disk copy or native pack would have been unsafe. `/dev/shm` has 63 GiB
capacity and is shared by all four workers.

## Artifact

`scripts/qwen27-model-cache.py` provides atomic `prepare`, shallow `status`,
deep SHA-256 `verify`, mmap page `warm`, admitted `path`, and dry-run-safe
`drop`. Entries are keyed by the recorded source SHA-256. Their metadata records
source and cached checksums/sizes, tool revision, `bmg-g31`, kernel ABI/layout,
llama.cpp commit and dirty-patch checksum, Linux kernel, and Intel Level Zero /
OpenCL package versions.

The worker controller now prefers an admitted target or draft cache entry. It
falls back to the original source path when an entry is absent or fails exact
identity/size admission. This makes reboot/cache loss safe.

## Measurements

Initial staging, including source SHA-256 calculation:

| Artifact | Bytes | Stage time | Rate |
|---|---:|---:|---:|
| target Q4_0 | 16,056,476,800 | 13.683 s | 1,119.1 MiB/s |
| DFlash Q4_K_M | 1,033,066,720 | 0.909 s | 1,083.7 MiB/s |

Deep cache verification took 8.648 s for the target and 0.577 s for the draft.
Touching every mmap page took 1.308 s and 0.087 s respectively.

Two sequential GPU3 `llama-bench` one-token process runs measured 9.62 s from
the source path and 9.33 s from the RAM path, a 0.29 s / 3.0% warm-to-warm
improvement. Both reported equivalent decode (`25.92` versus `25.95 tok/s`).
The source was necessarily hot in the Linux page cache after staging, so this
comparison understates cold external-disk savings and must not be described as
a cold-start benchmark. Evidence is under
`/mnt/fast-ai/bench-results/qwen27-model-cache/`.

## Boundary And Next Work

The cached file retains original GGUF layout. llama.cpp currently performs
SYCL reorder into device-only buffers after loading. A true offline reordered
pack requires a versioned loader/backend ABI capable of binding packed tensor
offsets directly; serializing the closed DPAS experiment's layout would be
misdirected. Golden real-model activation and pristine device-state capture
also remain outstanding.
