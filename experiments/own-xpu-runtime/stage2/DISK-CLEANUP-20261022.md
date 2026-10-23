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

## 2026-10-23 addendum 2 (before the packet195 record chain)

Root was at 27 GB after the packet192–194 windows. Same archive-then-verify procedure, exact directories:

| Source | Files | Archive (uncompressed tar) | sha256 |
| --- | --- | --- | --- |
| `packet187-record-bundle-v3/build/device-cards01-p187-a` (git-ignored chain output of the 60.659520 record, superseded by packet190 and packet195; per-window receipts tracked under `packet187-record-bundle-v3/evidence/device-cards01-p187-a/`) | 43,054 | `/mnt/usb-models/own-runtime-archives/packet187-record-bundle-v3-raw-outputs-20261023.tar` (1,251,379,200 B) | `739c905ac7e5597948d1e1406b34b57b567c20da35d704698a2e682a530e74d1` |
| `packet188-twocard-k3-composite/v5/evidence/device-row{0,1,2}-*/run` (untracked raw per-view outputs; the tracked summaries, kernel logs and bracket-summary.json stay) | 2,318 | `…/packet188-twocard-k3-composite-raw-outputs-20261023.tar` (580,188,160 B) | `135d438735137e6cf5dd889af20c85c4092e3fc499841b7ea6f6417fa9cc7d7c` |
| `packet189-twocard-k3x/v5/evidence/device-row{0,1}-*/run` (untracked raw per-view outputs; tracked summaries stay) | 1,878 | `…/packet189-twocard-k3x-raw-outputs-20261023.tar` (441,856,000 B) | `de8143b6ecac2b9b28a9c5d3c26f8b62e7a72d81f4b407d766a33201a151bb2f` |

Per-file sha256 manifests beside each tar as `<name>.sha256`; member counts equal the source counts; one extracted file per archive matched its manifest hash before deletion. Root free afterwards: 31.0 GB (2.68 GB above the record-chain launcher floor).
