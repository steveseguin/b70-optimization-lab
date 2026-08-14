# Qwen ignored-artifact archive

Date: 2026-08-14
Disposition: verified copy-only archive; source trees retained

## Why

Two Qwen experiment directories occupied about 10 GiB on the root filesystem,
almost entirely through Git-ignored build/dependency outputs and diagnostic
weights. The tracked notes, patches, configs, and results are valuable and must
stay discoverable. This archive provides a recovery point before any later
generated-file cleanup.

## Source directories

- `experiments/qwen27_graphsafe_flash_attention/`
  - tracked files: 8 at archive audit time;
  - total archive objects: 12,189;
  - large ignored content includes `staged-package/`, `work/`, and Python cache.
- `experiments/qwen36-27b-autoround-int4-b70/`
  - tracked files: 418 at archive audit time;
  - total archive objects: 483;
  - large ignored content includes diagnostic `*.safetensors`, ESIMD build
    products, shared objects, and Python caches.

## Verified archives

Archive root:

`/mnt/usb-models/bench-results/llm-optimizations-ignored-artifacts/2026-08-14`

| Archive | Bytes | Entries | SHA-256 |
| --- | ---: | ---: | --- |
| `qwen27-graphsafe-flash-attention-experiment.tar` | `5,301,340,160` | `12,189` | `542b1d0a0ec18703a2e4e442418c3ba22394ef079d68c934bca5dc401f1e4f5c` |
| `qwen36-27b-autoround-int4-experiment.tar` | `5,332,080,640` | `483` | `29d8d21193155cff4d215fdbe1b20af6774caf4facb37c7c96e29b923be240b1` |

Each archive was created as uncompressed PAX tar directly on the external
volume, hashed in full, and read back with `tar -tf`. Archive entry counts
exactly matched source-tree object counts. The archive directory contains its
own `README.md` and `SHA256SUMS`.

## Restore and cleanup boundary

Restore commands and verification commands are in the drive-local README. The
archive operation did not remove source files. A later cleanup may remove only
the audited Git-ignored generated content after:

1. `sha256sum -c SHA256SUMS` passes on the mounted archive volume;
2. no process or experiment owns the source directory;
3. `git status --ignored` confirms every proposed deletion is ignored;
4. exact deletion targets are recorded before execution.

Never run a broad `git clean` against either experiment directory. Tracked
research remains authoritative in Git even when ignored generated artifacts
are restored from the external archive.
