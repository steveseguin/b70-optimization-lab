# Reference Lab Storage Layout

**For outside readers:** every absolute path beginning `/mnt/fast-ai/` or
`/mnt/usb-models/` anywhere in this repository is a path on the maintainer's
reference lab host. Those paths do not exist on your machine and are not
expected to. They are recorded so that a result stays traceable to the exact
bytes it was measured against, not as instructions you can run unmodified.

When following a recipe from `repro/` or `community/`, substitute your own
model directory for any such path. Nothing else about the recipe depends on
where the weights happen to live.

**For the maintainer:** this is the map of what sits where, and which storage
has to be mounted before a lane will run.

Last verified: 2026-08-30 EDT.

## Internal NVMe

`/dev/nvme0n1p2`, 915 GB ext4, always present.

| Path | Size | Notes |
| --- | --- | --- |
| `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8` | 185.56 GB | Active local Flash-Next checkpoint; pinned verification is described below |
| `/mnt/fast-ai/llm-models/laguna-s-2.1` | 70 G | Active campaign model: 68 G `int4` target, 2.1 G `dflash-int4` draft |
| `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf` | symlink | Compatibility path to the Gemma 4 Q8 tree now on USB |
| `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-hf-tokenizer` | 62 M | Tokenizer for the above |
| `/mnt/fast-ai/llm-cache/hf` | compatibility metadata | The old Qwen3.6-27B snapshot path now resolves to its verified USB copy |
| `/mnt/fast-ai/bench-results` | 205 G | Run evidence; several `CURRENT.md` record identities point here |
| `/mnt/fast-ai/llm-optimization-artifacts` | 23 G | Sealed run roots |
| `/mnt/fast-ai/deepseek-v4-corpora` | 25 G | Prompt corpora |

Through 2026-08-21, only the active Laguna model and the Gemma 4 26B pair were
kept on NVMe as working weights after the 2026-07-25 relocation. The Gemma
tree moved to USB and Flash-Next moved onto NVMe on 2026-08-27, as recorded
below. This preserves the earlier storage history without treating it as the
current layout.

## External USB Drive

`/dev/sda2`, 3.6 TB NTFS, volume label `CorsairExternal`, mounted at
`/mnt/usb-models`.

On 2026-08-08 the drive was still physically present but unmounted. An NTFS
`$MFT`/`$MFTMirr` record-3 mismatch prevented `ntfs-3g` from mounting it. The
model tree was first inventoried through a read-only kernel `ntfs3` mount, SMART
reported no media/data-integrity errors, and `ntfsfix` then repaired the mirror
record and reset the NTFS journal. The drive is mounted read/write again with
about 1.8 TB free. The pre-repair inventory and key-model checksums are under
`/mnt/fast-ai/storage-recovery/`; the drive-local recovery record is
`/mnt/usb-models/.storage-health/README.md`.

`ntfsfix` is not a replacement for Windows filesystem repair. At the next safe
maintenance window, cleanly unmount the drive, attach it to Windows, run
`chkdsk /f`, and reboot Windows twice before considering the NTFS metadata
fully checked.

On 2026-08-21 the drive was **not visible in `lsblk`**, not merely unmounted.
Do not redirect queued downloads to the internal NVMe: it had only about
12 GiB free. After reconnecting the drive, repeat the mount and health checks,
then use the revision-pinned [model intake queue](../model-intake/README.md).

**This drive does not auto-mount.** If it is not mounted, every path below
fails with a "no such file or directory" error that looks like missing data
rather than a missing drive. Mount it first:

```bash
sudo mount -t ntfs-3g -o rw,uid=1000,gid=1000,umask=022 /dev/sda2 /mnt/usb-models
```

The 2026-08-08 17:05 maintenance reboot confirmed this behavior. The drive was
remounted read/write with the command above; the four stable Qwen aliases,
selected FP8 snapshot/config, 27B GGUF size, and archived B2 runtime size were
then rechecked before the next model lane.

Note that `mount -o remount,rw` does **not** work on this filesystem; ntfs-3g
silently keeps the old mode and writes fail with a misleading `ENOENT`.
Unmount and mount fresh instead.

Relocated on 2026-07-25, verified byte-for-byte before the source was removed:

| Model | Size | Files |
| --- | --- | --- |
| `deepseek-v4-flash-xpu` | 114 G | 110 — K160 target plus DSpark draft, paused record lane |
| `minimax-m2.7-int4-autoround` | 121 G | 78 |
| `gemma4-12b-it-int4-autoround-intel` | 7.8 G | 32 |
| `gemma4-12b-it-int4-autoround-intel-vllm-compat` | 32 M | 29 |

Already resident before that move: `qwen3.6-27b-fp8-vrfai`,
`qwen36-27b-awq-int4-cyankiwi-8f269fb`, `qwen3.6-35b-a3b-int4-autoround-abhinand`,
`minimax-m2.7-reap-autoround-w4a16`, `gemma3-12b-it-int4-autoround-opea`,
`gemma4-12b-it-int4-autoround-vishva007`, `gemma4-26b-a4b-it-dflash-hf`,
`gemma4-26b-a4b-it-eagle3-gguf`, `gemma4-26b-a4b-it-qat-gguf`,
`gemma4-e4b-it-gguf`. The drive also holds an `hf-cache/` tree with further
Qwen3.6-27B quantizations.

Use the following top-level conventions for new material:

- `llm-cache/hf/` is the canonical Hugging Face cache;
- `llm-models/` holds complete directly runnable model directories;
- `models/` holds standalone GGUF files and source-specific groupings;
- `bench-results/` and `llm-optimization-artifacts/` hold evidence, not model
  weights.

The older `hf-cache/` tree is intentionally preserved until its snapshots have
been reconciled into `llm-cache/hf/`. Do not merge or delete cache trees by
filename alone. The drive-local `/mnt/usb-models/MODEL-STORAGE.md` records the
same convention for operators working outside this repository.

Verified or repaired on 2026-08-08:

| Model | Location | Verification |
| --- | --- | --- |
| Qwen3.6-27B MTP Q4_K_M | `models/qwen36-27b-mtp-gguf/Qwen3.6-27B-Q4_K_M.gguf` | 17,106,773,120 bytes; published SHA-256 match |
| Qwen3.6-35B-A3B-FP8 | `llm-cache/hf/hub/models--Qwen--Qwen3.6-35B-A3B-FP8` | pinned `95a723d0...`; 56/56 remote-aware checksum pass |
| Qwen3.6-27B BF16 backup | `llm-models/Qwen-Qwen3.6-27B-6a9e13bd6` | 55.59 GB; full source checksum and 15/15 safetensors header pass |
| Qwen3.6-35B-A3B BF16 backup | `llm-models/Qwen-Qwen3.6-35B-A3B-995ad96e` | 71.93 GB; repaired, quarantined old mismatches, full source checksum and 26/26 header pass |

Stable aliases under `/mnt/fast-ai/llm-models/` are
`qwen3.6-27b-mtp-gguf`, `qwen3.6-35b-a3b-fp8-qwen`,
`qwen3.6-27b-bf16-qwen`, and `qwen3.6-35b-a3b-bf16-qwen`. The first two
require the USB mount. As of the 2026-08-30 reclaim below, the BF16 aliases
also resolve to the verified USB copies.

## 2026-08-30 Internal-NVMe Reclaim

The following older local copies were removed after their external copies were
verified. Lightweight compatibility paths preserve existing recipes, but all
three now require `/mnt/usb-models` to be mounted.

| Removed local copy | Retained external copy | Compatibility treatment |
| --- | --- | --- |
| `/mnt/fast-ai/llm-cache/hf/models--Qwen--Qwen3.6-27B` | `/mnt/usb-models/llm-models/Qwen-Qwen3.6-27B-6a9e13bd6` | Recreated the pinned `snapshots/6a9e13bd...` path as a symlink |
| `/mnt/fast-ai/model-staging/Qwen-Qwen3.6-35B-A3B-995ad96e` | `/mnt/usb-models/llm-models/Qwen-Qwen3.6-35B-A3B-995ad96e` | Replaced the old staging path with a symlink |
| `/mnt/fast-ai/llm-models/qwen3.8-27b-int4-autoround-devan` | `/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan` | Replaced the old model path with a symlink |

The two Qwen3.6 destinations retain their full-copy `BACKUP-VERIFIED.md`
receipts. The Qwen3.8-27B INT4 source and destination passed a fresh full-tree
`rsync -nrcL` comparison immediately before deletion. The operation reclaimed
146,530,455,552 bytes: internal free space increased from 100,875,149,312 to
247,405,604,864 bytes (`94 GiB` to `231 GiB` as reported by `df -h`).

The active `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8` tree was not moved.
Its config and index hashes were checked before and after the reclaim and still
match the pinned values in the Flash-Next section below. Keeping it on NVMe is
intentional: recent measured model loading from USB took about 583 seconds,
whereas the localized checkpoint has loaded in roughly 71--80 seconds.

## 2026-08-27 Cold-Tree Relocation

Three cold trees were copied to USB, checked against their source inventories
and per-file SHA-256 lists, switched to compatibility symlinks, and checked
again through those symlinks. The retained receipts are under
`/mnt/fast-ai/storage-relocation-20260827/`; each lane's
`verification-summary.txt` records `tree_cmp=pass` and `sha256_check=pass`.
All three `post-switch-changes.txt` and `post-switch-rsync.stderr` files are
empty.

| Tree | Apparent bytes | External destination | Compatibility path |
| --- | ---: | --- | --- |
| Qwen 27B EAGLE data | 184,228,530,276 | `/mnt/usb-models/archived-fast-ai-bench-results/qwen36-27b-autoround-int4-b70-eagle-data` | `/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data` |
| DeepSeek V4 Flash evidence | 23,948,877,437 | `/mnt/usb-models/archived-fast-ai-bench-results/deepseek-v4-flash-xpu` | `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu` |
| Gemma 4 26B Q8 model tree | 61,054,291,085 | `/mnt/usb-models/llm-models/gemma4-26b-a4b-it-q8-gguf` | `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf` |

The Gemma verification summary retains its temporary destination name,
`/mnt/usb-models/llm-models/.gemma4-26b-a4b-it-q8-gguf.incoming-20260827`.
That verified directory was renamed to the final destination shown above
before the compatibility symlink and post-switch checks were completed.

## Qwen3.8 Flash-Next Local Checkpoint

The active checkpoint path is
`/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`. The external source copy is
retained at `/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8`; it is a backup,
not the active path.

The full verifier receipt is
`/mnt/fast-ai/llm-models/.verification/Qwen3.8-Flash-Next-FP8-20260827.json`
(SHA-256
`6ae22291119e8c8a01597bda9fe4b1fb5850912655ec188e363a88eb6de58470`).
It passed against `Qwen/Qwen3.8-Flash-Next-FP8` revision
`bcd9f01ddc9cff2316eb84281bebcd5b058bddce`: 144 root files,
185,563,783,127 bytes, and 131 indexed shards. The frozen tree-metadata
SHA-256 is
`4a3793bd4a795ea6761b3d322200b4a1fd8300cdeb75cc127d330d513f590eb2`;
the config and index SHA-256 values are respectively
`99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d`
and `0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6`.
The receipt records the pre-promotion incoming path because the full check ran
before the verified directory was renamed to the active path. No GPU boot from
the localized path had been attempted at this storage checkpoint.

The matching 18-file runtime package is retained under
`/mnt/fast-ai/qwen38-runtime-publication/`:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `qwen38-flash-next-runtime-stage-2f829747.tar` | 1,968,250,880 | `6bf1b547e3887c86007f5ef5ad7c67be365ce4888f0e2c0a1f360dde7a7b13c3` |
| `qwen38-flash-next-runtime-stage-2f829747.tar.part-0000` | 1,073,741,824 | `ea8d91b4a184b26a04d18f9f4ac58fb6e116c9fc750e8532fb1ad0cc27f46ca1` |
| `qwen38-flash-next-runtime-stage-2f829747.tar.part-0001` | 894,509,056 | `38ba225d4908ad976b2b08b0ac945f6d95cd4528143ebe231d58c075068b88b4` |
| `qwen38-flash-next-runtime-stage-2f829747.tar.receipt.json` | 4,401 | `ac6cddf7bc193b6ccd3d837c0b461c099e7f0c8fc97a1997ab1c7bb736f088b5` |

The package receipt reports a clean extraction and exact hashes for all 18
files. Concatenating the two numbered parts reproduces the tar SHA-256. The
embedded source manifest SHA-256 is
`9fa443fdb7a6d0042cf04f859cc6fd6a7bdc09943e16cafb4ea084573c892d2b`.

The USB filesystem is NTFS through `fuseblk`/ntfs-3g. It is suitable for cold
trees, model backups, and evidence, but not for an `overlay2` or containerd
data root. Compatibility paths into USB also require the drive to be mounted.
At 2026-08-27 19:55 EDT, `df -B1` reported 121,202,786,304 bytes available on
the internal ext4 filesystem and 511,215,669,248 bytes available on USB.

## Old Paths Still Work

Each relocated model left a symlink behind at its original NVMe path:

```
/mnt/fast-ai/llm-models/deepseek-v4-flash-xpu
    -> /mnt/usb-models/llm-models/deepseek-v4-flash-xpu
```

So the ~168 documents in this repo that reference
`/mnt/fast-ai/llm-models/...` remain correct **while the drive is mounted**,
including symlinks stored inside the moved trees, which use absolute paths and
resolve back through the compatibility link. No recipe, config, or note needed
editing.

The single failure mode to remember: with the drive unmounted, those paths look
like deleted models rather than an unmounted disk.
