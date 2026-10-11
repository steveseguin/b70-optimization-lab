# Laguna S 2.1: restoring archived research source

Storage consolidation, 2026-10-10. No source version, hash or experimental
verdict was discarded. Four large historical Git bundle representations. The accepted shared-elementwise and QKNorm/RoPE bundles remain unpacked, as do the other patch/bundle dependencies. The archived bundle bytes are unchanged. These original bundles already have an incomplete ancestry boundary; see the restore proof below.

The [manifest](source-archive-manifest.json) maps every original repository path
to its exact byte count and SHA-256 in [the archive](source-history-20261010.tar.xz).
Historical notes and frozen JSON receipts keep their original paths and hashes:
those paths are restoration destinations, not missing evidence.

## Verify and restore

From the lab repository root, verify every member without extracting:

```bash
python3 tools/restore-source-archives.py patches/laguna-s-2.1-xpu-b70/source-archive-manifest.json
```

Restore the original directory layout under a separate destination:

```bash
python3 tools/restore-source-archives.py patches/laguna-s-2.1-xpu-b70/source-archive-manifest.json --destination /tmp/b70-source-history
```

For an external destination, add `--require-mount /mnt/EXPECTED_MOUNT` so
an absent disk cannot redirect writes onto the parent filesystem.

Use `--member ORIGINAL_REPO_RELATIVE_PATH` to select one file. Use
`--destination .` only when a historical command needs the old path inside this
checkout; exact ignore entries keep restored bulk bytes out of new commits.
The helper verifies the archive and every member before writing, enforces the
50 GiB disk reserve, refuses conflicting files or symlink paths, and verifies
the restored bytes. It never executes a patch, build, model or historical runner.

All 76 consolidated files were restored and compared byte-for-byte before
removing their unpacked copies. [The consolidation audit](../../audits/repository-cleanup/2026-10-10/archive-consolidation.md)
records the exact consumer inventory and proof. This restores source evidence;
it does not establish binary identity, clean-host replay or permission to run.

## Inventory

Original bytes: **185,069,979**; archive bytes: **45,359,284**.
Archive SHA-256: `8dda9ff94f9f372b7ccadb1f48d2c9e216a18c44a03cc34e93137f739eb7ad71`.

| Original path relative to this directory | Bytes | Original SHA-256 |
| --- | ---: | --- |
| `vllm-laguna-confidence-tree-diagnostic-8b8cd5227-20260801.bundle` | 46267717 | `f102dc5d3ade64880d340a189f3a5c08d97584a5558ea72b97deea579c7a6956` |
| `vllm-laguna-dflash-local-tp4-rejected-448351379-20260801.bundle` | 46269936 | `18317f6a824bd8f3dc788225462cc292f8e572292061c83a0945e8da854cea98` |
| `vllm-laguna-target-inline-gathers-ce2f3dfc0-20260731.bundle` | 46265239 | `231d391d4526e7816ba69e80d211aefb0df663699846d5211e50c659c1ee9ea7` |
| `vllm-laguna-target-inline-gathers-fixed-input-v2-68a4a5f3e-20260801.bundle` | 46267087 | `a181c0036436860b24cacea057e1f285ddd1fcf75a9e010f3d32fecb65095fad` |

## Inherited Git ancestry limitation

The original and restored bundles pass `git bundle verify`, import into an
isolated bare repository, and export identical complete source trees at every
bundle tip. Their object inventories also match. However, both have the same
missing historical parent: commit `40eac9a9d92bba51ad49ca777a5517ee212ea394`
references absent `b5adb027ad03c29b46181752ba3b1cb84eff1dd4`. Both strict
`git fsck` checks therefore exit 2. No prerequisite was declared in the original
bundles, so `git bundle verify` alone missed this limitation.

The archive preserves the original evidence exactly; it does not repair or
claim complete Git ancestry. Every archived tip remains reconstructible. The two large accepted bundles
left unpacked show the same historical ancestry boundary.
