# Disk cleanup 2026-10-22 (before the packet190 record chain)

Root (`/`) had 28.35 GB free against the packet190 launcher floor of 28,324,718,708 B (25 GB + the chain's
3,324,718,708 B write reservation), a 25 MB margin. Freed, archive-then-verify, no globs:

| Source (git-ignored chain outputs of closed, superseded record bundles) | Files | Archive (uncompressed tar) | sha256 |
| --- | --- | --- | --- |
| `packet97-record-bundle/build/device-cards01-a` + `device-cards01-b` (record 56.086987, 2026-10-18; superseded) | 43,242 | `/mnt/usb-models/own-runtime-archives/packet97-record-bundle-chain-outputs-20261022.tar` (1,330,268,160 B) | `6d592d8c0d2e33d2252a006f1a01db149a15ca88103d7154e349a67047f607d8` |
| `packet103-record-bundle/build/device-cards01-a` + `device-cards01-b` (record 57.550573, 2026-10-18; superseded) | 46,769 | `/mnt/usb-models/own-runtime-archives/packet103-record-bundle-chain-outputs-20261022.tar` (1,687,910,400 B) | `d16d0aa213ae68abe093708ea34f6fdd7087c5a39d04edfaf136e39d40f79e07` |

Per-file sha256 manifests (every archived file, sorted paths) sit beside each tar as `<name>.sha256`. Verification
before deletion: tar member count equals the source file count for both; `device-cards01-b/K1a/round2/output.bin`
extracted from the packet97 tar matched its manifest hash. Both packets' tracked `evidence/` and submission
receipts are untouched. Also removed: my scratch venv (196 MB) and 28.77 MB of stopped Docker containers.

Restore: `tar xf <archive> -C experiments/own-xpu-runtime/stage2/<packet>/build/` then `sha256sum -c <name>.sha256`.

## 2026-10-23 addendum (before the one-card cache23 record chain)

Root was back at 27 GB after the packet190/191 chain outputs and evidence. Same archive-then-verify procedure, exact directories:

| Source (git-ignored chain outputs of closed, superseded record bundles) | Files | Archive (uncompressed tar) | sha256 |
| --- | --- | --- | --- |
| `packet124c-record-bundle/build/device-cards01-a` (record 58.223834, 2026-10-18; superseded) | 42,974 | `/mnt/usb-models/own-runtime-archives/packet124c-record-bundle-chain-outputs-20261023.tar` (1,221,724,160 B) | `d272c540eb89c6cab586219ee1cdfe42b8d5fd4286562e02a3dab3d9a5635c7c` |
| `packet136-record-bundle/build/device-cards01-a` (record 58.798109, 2026-10-18; superseded) | 42,974 | `/mnt/usb-models/own-runtime-archives/packet136-record-bundle-chain-outputs-20261023.tar` (1,221,775,360 B) | `e7a7e0dcf444c0215ca6caf38f5062208d8853bd7b3662a49ff3d55bca00563c` |

Per-file sha256 manifests beside each tar as `<name>.sha256`; tar member counts equal the source counts; `device-cards01-a/K1a/round2/output.bin` extracted from each tar matched its manifest hash. Both packets' tracked `evidence/` and submission receipts are untouched.
