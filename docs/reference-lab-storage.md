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

Last verified: 2026-08-08.

## Internal NVMe

`/dev/nvme0n1p2`, 915 GB ext4, always present.

| Path | Size | Notes |
| --- | --- | --- |
| `/mnt/fast-ai/llm-models/laguna-s-2.1` | 70 G | Active campaign model: 68 G `int4` target, 2.1 G `dflash-int4` draft |
| `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf` | 57 G | Gemma 4 26B Q8 reference/production lane |
| `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-hf-tokenizer` | 62 M | Tokenizer for the above |
| `/mnt/fast-ai/llm-cache/hf` | 46 G+ | Hugging Face cache |
| `/mnt/fast-ai/bench-results` | 205 G | Run evidence; several `CURRENT.md` record identities point here |
| `/mnt/fast-ai/llm-optimization-artifacts` | 23 G | Sealed run roots |
| `/mnt/fast-ai/deepseek-v4-corpora` | 25 G | Prompt corpora |

Only the active Laguna model and the Gemma 4 26B pair are kept on NVMe as
working weights. Everything else was relocated on 2026-07-25 to free the disk,
which had reached 98% full.

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

**This drive does not auto-mount.** If it is not mounted, every path below
fails with a "no such file or directory" error that looks like missing data
rather than a missing drive. Mount it first:

```bash
sudo mount -t ntfs-3g -o rw,uid=1000,gid=1000,umask=022 /dev/sda2 /mnt/usb-models
```

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
