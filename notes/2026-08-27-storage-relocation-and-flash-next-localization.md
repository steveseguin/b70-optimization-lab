# Storage relocation and Flash-Next localization

Date: 2026-08-27

## Outcome

Three cold trees were moved from internal NVMe to the mounted external NTFS
drive, with their original paths retained as compatibility symlinks. The
Qwen3.8 Flash-Next FP8 checkpoint was then copied in the opposite direction
and fully verified on local NVMe. Its certified 18-file runtime stage was
packaged separately with deterministic metadata, split parts, and a verified
receipt.

This note records storage and package verification only. It does not claim a
GPU boot from the localized checkpoint.

## Cold trees moved to USB

| Lane | Source/compatibility path | Final external destination | Source inventory |
| --- | --- | --- | --- |
| Qwen 27B EAGLE data | `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data` | `/mnt/usb-models/archived-fast-ai-bench-results/qwen36-27b-autoround-int4-b70-eagle-data` | 184,228,530,276 apparent bytes; 822,346 files; 96 links; 541 directories |
| DeepSeek V4 Flash evidence | `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu` | `/mnt/usb-models/archived-fast-ai-bench-results/deepseek-v4-flash-xpu` | 23,948,877,437 apparent bytes; 7,386 files; 0 links; 737 directories |
| Gemma 4 26B Q8 model tree | `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf` | `/mnt/usb-models/llm-models/gemma4-26b-a4b-it-q8-gguf` | 61,054,291,085 apparent bytes; 26 files; 0 links; 6 directories |

The audit roots are:

- `/mnt/fast-ai/storage-relocation-20260827/eagle/`;
- `/mnt/fast-ai/storage-relocation-20260827/deepseek/`;
- `/mnt/fast-ai/storage-relocation-20260827/gemma/`.

Each `verification-summary.txt` records a zero-change rsync comparison,
matching source/destination tree inventories, and a complete destination
SHA-256 pass. After switching the source path to its compatibility symlink,
all three `post-switch-changes.txt` and `post-switch-rsync.stderr` artifacts
were empty.

Gemma was verified while its destination still had the temporary name
`/mnt/usb-models/llm-models/.gemma4-26b-a4b-it-q8-gguf.incoming-20260827`.
That exact verified directory was renamed to the final path in the table before
the compatibility link and post-switch comparison were made.

## Flash-Next checkpoint localized to NVMe

Active path:

```text
/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8
```

Retained external backup:

```text
/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8
```

The full local-tree verifier passed with this frozen identity:

- repository: `Qwen/Qwen3.8-Flash-Next-FP8`;
- revision: `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- root files: 144;
- total root bytes: 185,563,783,127;
- indexed shards: 131;
- indexed tensors: 152,089;
- tree-metadata SHA-256:
  `4a3793bd4a795ea6761b3d322200b4a1fd8300cdeb75cc127d330d513f590eb2`;
- config SHA-256:
  `99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d`;
- index SHA-256:
  `0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6`.

Receipt:

```text
/mnt/fast-ai/llm-models/.verification/Qwen3.8-Flash-Next-FP8-20260827.json
SHA-256 6ae22291119e8c8a01597bda9fe4b1fb5850912655ec188e363a88eb6de58470
```

The receipt's `model_root` is the pre-promotion path
`/mnt/fast-ai/llm-models/.Qwen3.8-Flash-Next-FP8.incoming-20260827` because
verification completed before the checked directory was renamed to the active
path. This is provenance, not a second checkpoint.

## Certified runtime package

The original external runtime stage was retained unchanged. Its generated
Python cache files were excluded by copying only the 18 files declared in the
frozen manifest into a clean local candidate. Every copied SHA-256 passed,
there were no extra `.py` or `.so` files and no cache artifacts, and the
packager then verified a clean extraction before writing its receipt.

Artifact root:

```text
/mnt/fast-ai/qwen38-runtime-publication/
```

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `qwen38-flash-next-runtime-stage-2f829747.tar` | 1,968,250,880 | `6bf1b547e3887c86007f5ef5ad7c67be365ce4888f0e2c0a1f360dde7a7b13c3` |
| `qwen38-flash-next-runtime-stage-2f829747.tar.part-0000` | 1,073,741,824 | `ea8d91b4a184b26a04d18f9f4ac58fb6e116c9fc750e8532fb1ad0cc27f46ca1` |
| `qwen38-flash-next-runtime-stage-2f829747.tar.part-0001` | 894,509,056 | `38ba225d4908ad976b2b08b0ac945f6d95cd4528143ebe231d58c075068b88b4` |
| `qwen38-flash-next-runtime-stage-2f829747.tar.receipt.json` | 4,401 | `ac6cddf7bc193b6ccd3d837c0b461c099e7f0c8fc97a1997ab1c7bb736f088b5` |

The tar contains exactly 20 members: deterministic metadata, the frozen
manifest, and the 18 declared payload files. Concatenating parts `0000` and
`0001` reproduces the tar SHA-256. The embedded manifest SHA-256 is
`9fa443fdb7a6d0042cf04f859cc6fd6a7bdc09943e16cafb4ea084573c892d2b`.

## Filesystem boundary and free space

The external drive is NTFS mounted through `fuseblk`/ntfs-3g at
`/mnt/usb-models`. It can hold cold checkpoint, result, and evidence trees,
but it cannot be used as an `overlay2` or containerd data root. Every
compatibility symlink into that drive depends on the mount being present.

The 2026-08-27 19:55 EDT `df -B1` snapshot was:

| Filesystem | Mount/use | Available bytes | Displayed use |
| --- | --- | ---: | ---: |
| `/dev/nvme0n1p2` ext4 | internal NVMe backing `/mnt/fast-ai` | 121,202,786,304 | 87% |
| `/dev/sda2` fuseblk | `/mnt/usb-models` | 511,215,669,248 | 88% |
