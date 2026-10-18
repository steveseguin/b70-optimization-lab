# Disk cleanup, 2026-10-18 (root 14 GB free before the packet 84 record chain, which needs 14.32 GB)

## Packet 45 closed GPU window trees → RAID archive (01:11–01:13 UTC)

- Moved: `packet45-merged3/build/{speed3-c4096-dr1-gpu, speed3-c4096-dr0-s24-gpu, speed6-c4096-dr1-s23-cards01-gpu, speed6-c4096-dr1-s23-cards23-gpu, speed7-c4096-dr1-s23-cards01-gpu, speed7-c4096-dr1-s23-cards23-gpu, k2probe-c4096-dr1-s23-cards01-gpu}` (exact directories, no globs).
- Archive: `/mnt/raid-models/own-xpu-runtime-archive/packet45-merged3/window-trees-20261018T011112Z.tar.gz` (3.0 GB), with its sha256 and a per-file SHA manifest `window-trees-20261018T011112Z.sha256` (261,242 files, hard links included).
- Verified before deletion: member count equals the manifest; every member's content hash was recomputed from the archive and matched.
- Kept on root (referenced by packet 78 seals): `speed6-c4096-dr1-s23-cards01-gpu/K2/run0/dispatch-measured.json` (hash re-checked after restore). `fusion-rope.hpp` and `fusion-fixtures` were not touched.
- Root free: 14 GB → 20 GB.
- The first attempt stopped at its member-count check (it did not count hard-link entries); nothing was deleted, and its partial archive files were removed.


## Reference-preserving cleanup before packet 97 (2026-10-18, started 03:12 UTC)

**Outcome: 4,023,844,864 allocated bytes reclaimed (4.02 GB), below the requested 5 GB minimum and 6 GB stop threshold.**
The selected files contain 5,116,007,904 logical bytes, but hard links and filesystem allocation make that a misleading measure of recovered disk space. The allocation figure deduplicates inodes and counts an inode only when all its links were removed. No unsafe deletion was used to make the target.

Host: `steve-b70s`, root filesystem `/dev/nvme0n1p2`. The saved initial reading at 2026-10-18 03:13:06 UTC was 15,527,235,584 bytes free. At 2026-10-18 03:42:50 UTC, after removing this audit's verified temporary files, packet 97's read-only storage precheck reported **18,402,914,304 free / 18,812,225,206 required; margin -409,310,902 bytes; passed=false**. Other lane work continued writing during the cleanup, so the difference between the two free-space readings is not the amount reclaimed. Packet 97 is not certified storage-ready by this cleanup.

All work was CPU/disk only under `nice -n 19 ionice -c3 taskset -c 8-15,24-31`, with Python `-B` and executed programs' stdin `/dev/null`. No GPU job, service, sudo, setting change or credential display was performed. The packet 49 oracle, packet 17 reference, packets 84/90–97/58g/58s, and screen code were not changed. Existing work on shared `main` was left alone. Only this record is committed.

### Reference decisions

Whole-repository searches included hidden and ignored files, excluding only `.git`, for exact candidate paths, their parent paths, relative aliases and packet names. The full `experiments/own-xpu-runtime`, `scripts`, and its `ops` consumers were covered. Broad `/home/steve` and results-root references were inspected for dynamic path construction. The retained audit contains patterns, complete reference-file indexes, relevant source hits, inventories and decisions. Searches reported 68 inaccessible root-owned cache/STOP files in the unrelated old Qwen lane; no permission workaround was attempted. No own-runtime, scripts or ops reference file was inaccessible in these searches. This is a recorded search limitation, not a claim that every unrelated cache was readable.

- `packet49c-round2`, `packet49d-round3`, `packet56-draft-prefix`: removed only old raw `.bin`/`.bf16` outputs under completed late windows `W2m`, `WS`, `WSs`, `WS128x`, `WS128`. Their exact file lists are in their manifests. Kept every receipt, `window.json`, dispatch result, log, JSON/JSONL file, source/build artifact, native fixture and all early `K0/K1a/K1b/K2/W0p` and `KD` contents. The shared screen wrapper still uses packet 56 binaries/seals/fixtures. Submission collectors and `resume_chain` were read, including early-tree recursive checks.
- Four packet 79 A screens, five packet 81 A screens, and five packet 83 B grid screens: their measured arms and controls have explicit negative closeouts in `DO-NOT-REPEAT.md`. Removed only per-run Level Zero cache, duplicate input vocabularies, and five raw files in each completed `after-suite/rank1/draft-final-state`. Kept all JSON/JSONL, timing data, receipts, logs and compressed state metadata. `read_screens.py` hashes the retained JSON/JSONL; packet comparison code opens retained receipt files; no live consumer of the removed raw leftovers was found. This closure applies to those exact measured arms, not their open model lanes.
- `packet67-roofline/build`: eight raw candidate/expected fixture files from closed losing arms. Kept the `fixture-gnu-b/repeat-1` pair used by five live selections and all source, executable and receipt files. Its verifier still passes.
- `packet83-draft-bytes/build/mini`: closed mini-check raw `.bin`/`.bf16` only; retained metadata and logs.
- `packet57-attribution`: only old duplicate input vocabularies and after-suite draft raw state from completed `W57-control` and `W57-attribution`; retained KD/K0/builds and all JSON/JSONL. Packet 59/66 analysis consumes retained metadata.
- `packet52-freeorder` and `packet53-expert-order`: four standalone test executables from explicitly closed device rounds. Whole-repo exact/parent/name searches found no live external reader; their own closed seal/window code is the only executable reader. All sources, seals and receipts remain.

The final supplemental audit added 48 old private packet 57 driver-cache files and four packet 48b whole-boot log copies. No seal or live verifier opens these files; packet 48b per-window kernel logs and native proof remain. Packet 57 KD raw stays because a generic submission verifier can read it. The packet 56w tree stays: its apparent size follows symlinks and its regular files have shared hard links. Packet 49b CPU fixture outputs are reopened by seal checks and stay.

Kept in full: the recent packet 61x, 64 and 70 result trees (no eligible exact closeout, evidence younger than 12 hours); packet 70's K2 replay remains needed by packets 75/79/80/81. No v3 evidence qualified. Other older build trees were audited and kept where their arm was pending, binaries were sealed/shared, or raw outputs remained verifier inputs. In particular packet 24's large K1 outputs are reopened by its admission checks, packet 18 fixtures feed later controls, and packet 13 lacked a matching closure. Packet 15/23/36/45/62 dynamic readers were treated conservatively. Uncertainty meant keep.

### Archive procedure and retained file lists

There are 39 source-tree archives below. Each archive is a single `tar.gz` file on NTFS, with payload names `payload/<path relative to original root>`. Each embeds `.cleanup/manifest.json`, `.cleanup/manifest.sha256`, `.cleanup/kept.json`, and `.cleanup/plan.json`. The manifests enumerate every exact selected path, size and SHA-256; the plan records its original root and reason. The kept list records exact retained paths and hashes at that stage. No loose per-file payload was copied to NTFS.

Before **each** deletion: read and SHA-256 verify every archive payload member; verify hard-link members through their previously verified target; match the exact member-name set; independently count GNU `tar -tvzf` entries beginning `-` or `h`; verify the archive hash; recheck every selected source and every kept file; check accessible process file descriptors for selected open paths. Only those exact verified paths were unlinked, with no deletion globs or recursive source-tree removal. Kept hashes were checked again afterwards. Directories and symlinks remained.

Across these archives, 125,538 source files were removed. The GNU member counts include four embedded metadata files per archive. Final retained verification checked **18,571 files**, all matching their hashes. The definitive final kept list is `root-cleanup-20261018T0312/final-kept.json` inside the supplemental audit archive below: it subtracts files subsequently archived from earlier per-stage kept lists. In particular a first screen archive's kept list includes final-state files subsequently stored in its separate final-state archive.

Archive base: `/mnt/raid-models/own-xpu-runtime-archive/`. Every source-tree archive filename is `unreferenced-bulk-20261018T0312.tar.gz` in the directory named in the table. Original roots are given immediately after the table. Sizes are bytes; reclaimed means allocated bytes, not logical bytes.

| Archive directory | Removed files | Reclaimed bytes | tar.gz bytes | Members (`-` + `h`) | Archive SHA-256 |
| --- | ---: | ---: | ---: | ---: | --- |
| `packet49c-round2` | 39664 | 790949888 | 468652468 | 21236 + 18432 | `18d62318b4694f8f21bdcb2fa58841c13543e02a7e494af84bccfb4b899917f1` |
| `packet49d-round3` | 39664 | 790949888 | 468656487 | 21236 + 18432 | `0ed4fdaa8b671c10e05743f7c70cb018210fd1d8dd294df89dfaea1a43e43eaf` |
| `packet52-freeorder-closed-test-build` | 2 | 34385920 | 9021499 | 6 + 0 | `d90eda44f0d7e78aa617e0fefa778ee1ad99e2157bac6539ddfc53b759bd4fcb` |
| `packet53-expert-order-closed-test-build` | 2 | 33542144 | 8822848 | 6 + 0 | `02fa723c56dc965b5c6370e71f2376f585b5b04384aa9f5aeda79bcfc6cedd10` |
| `packet56-draft-prefix` | 39664 | 790949888 | 468639593 | 21236 + 18432 | `9ebb8f28158be4736685bc75901413624ee60b4faaeb21f7834c4c5d324767d3` |
| `packet57-W57-attribution` | 17 | 43814912 | 17889953 | 21 + 0 | `39d0b461ad1e9363f5e6d28bcd63adcf266325e793d4b7623f999ff5c0505daf` |
| `packet57-W57-control` | 17 | 43814912 | 17888670 | 21 + 0 | `35f2fd4664ed7050aebbc5e46cc2cc1b57d8ac50f590eec1cd9831218f7796f7` |
| `packet67-roofline-build` | 8 | 504492032 | 378829592 | 12 + 0 | `6bd9db32125695a35800c10ee23824afe4afe906ec25c7f95de832f4d5f7ef0a` |
| `packet83-mini` | 5526 | 22634496 | 1052461 | 5530 + 0 | `eafcbe2846cd1c4e2dcd048390c0ac2c3b32d688da27d502a743f8e6a3b1c859` |
| `screen-p79-A-0-1` | 61 | 57380864 | 23158297 | 65 + 0 | `fd65b81a3f9e8b5badee731474c4e590694f494c35c8eea73ec28b001ac29176` |
| `screen-p79-A-0-1-final-state` | 5 | 9703424 | 44306 | 9 + 0 | `76aa0bb605f3be7ae101b0e0541beb8089182392fb33783ba72857822e71aefd` |
| `screen-p79-A-1-0-split23` | 60 | 57085952 | 23090021 | 64 + 0 | `133b8d2ce330360c6141f4ed8bcabda2801452cca32b05b4ea172ab3da261067` |
| `screen-p79-A-1-0-split23-final-state` | 5 | 9703424 | 44322 | 9 + 0 | `2fe60ffc8b7dfd6261ba25953dfb16382986bce5b28b4516f67449adcf0cb966` |
| `screen-p79-A-2-0` | 60 | 57085952 | 23090158 | 64 + 0 | `a8f08c961648fab85dd225b1cdc5eec74c44ec4df9823dc1326817d8932a91ab` |
| `screen-p79-A-2-0-final-state` | 5 | 9703424 | 44295 | 9 + 0 | `6d9b3848a327be9fd94f8e6f57208d20a8397a944cf1c1548f671f4093559b81` |
| `screen-p79-A-3-1` | 61 | 57380864 | 23157992 | 65 + 0 | `ae9d9a25ef8dda2bd68e16042b5b54df5201ef329e9d6209cb72a9407432495a` |
| `screen-p79-A-3-1-final-state` | 5 | 9703424 | 44305 | 9 + 0 | `850c13c1cbb22b2ab30cae76e79b74d209412d0cfe14ddd74034d02c33f79278` |
| `screen-p81-A-0-production` | 61 | 57888768 | 23286075 | 65 + 0 | `5119a4cf00f43f52f9ed86d9b7889a51f539360053fa09141f8e724ea8f743a8` |
| `screen-p81-A-0-production-final-state` | 5 | 9703424 | 44307 | 9 + 0 | `e2cf4f49fe528863aab40abc0d88115e264d418b49c63ee76257e3b26a915e8d` |
| `screen-p81-A-1-gate-input-packed` | 61 | 57888768 | 23286155 | 65 + 0 | `6edb54f483a9eda7b949a18f0efeda93a2292993eade677697b9912250b9b39e` |
| `screen-p81-A-1-gate-input-packed-final-state` | 5 | 9703424 | 44322 | 9 + 0 | `f4a040615b74273b867fc49f678f97b301d32cf13782582c71e383d87f98b1ce` |
| `screen-p81-A-2-down-input-packed` | 61 | 57888768 | 23286041 | 65 + 0 | `3d87fe683cdd3b354669834f1cefd32fb26fee32ea4f41996195879c8469528a` |
| `screen-p81-A-2-down-input-packed-final-state` | 5 | 9703424 | 44316 | 9 + 0 | `110425e03ed6f6acde700b0a55219b454af248bd85bbc4aac24a639f84515b56` |
| `screen-p81-A-3-input-packed` | 61 | 57888768 | 23286181 | 65 + 0 | `94f83ed4cf86279e94a473349b30a91ba366385140e1a2b8ec177e78c7ef3c30` |
| `screen-p81-A-3-input-packed-final-state` | 5 | 9703424 | 44312 | 9 + 0 | `116f7959c4f31e52443f2c038553e9b46176a7150d304b618d0f9520069d20c4` |
| `screen-p81-A-4-production` | 61 | 57888768 | 23285896 | 65 + 0 | `9bfd9d5df09891692b5bcfb122985cd3a7234aa0d0ab59d2c6a707b517226faa` |
| `screen-p81-A-4-production-final-state` | 5 | 9703424 | 44319 | 9 + 0 | `377c4428af80ee24931dcf4f2e15b7c695f43d3b3c5e25b8ebbb0d004247b6f4` |
| `screen-p83-B-grid-0-production` | 61 | 57401344 | 23164993 | 65 + 0 | `e3314f0b4022905fb97ac8dd2794f4251859cb9c146674dc87e879f529852b0b` |
| `screen-p83-B-grid-0-production-final-state` | 5 | 9703424 | 44309 | 9 + 0 | `9c4e75ecb56efe673676231edc6248bf2674b198984f231dce694ccbc2b364cd` |
| `screen-p83-B-grid-1-q4-g32` | 61 | 57401344 | 23164904 | 65 + 0 | `a6b4faba96d62b548c1e90b54aee35a9e89d632c2a13c10a308f2894e87942a4` |
| `screen-p83-B-grid-1-q4-g32-final-state` | 5 | 9703424 | 44309 | 9 + 0 | `9aaf1eba16b0c7c391ecf3aae40ebab8afb577dd465796d95ca0dae2c0153448` |
| `screen-p83-B-grid-2-prefix990` | 61 | 57401344 | 23165268 | 65 + 0 | `e229bfe359ecb548bf0a56824989cee2b058146153a7ca6fd5b6451a423b5fba` |
| `screen-p83-B-grid-2-prefix990-final-state` | 5 | 9703424 | 44316 | 9 + 0 | `42a2061f1f5245cf614ec6ff642a28e6c12b9d3cd7613464e1886c098a09f4bc` |
| `screen-p83-B-grid-3-prefix985` | 61 | 57401344 | 23164967 | 65 + 0 | `75ac33dc95d7aa121edb5bbbc9d22f4869bcd7bda72cd0247c69951ac54b8c36` |
| `screen-p83-B-grid-3-prefix985-final-state` | 5 | 9703424 | 44315 | 9 + 0 | `69b2ce1c7443074dc043de1fb430e2639e6c5b6a4bff6ec10f3cc3eeb7b40c7a` |
| `screen-p83-B-grid-4-production` | 61 | 57401344 | 23165075 | 65 + 0 | `3e9b15334ee4e11d4f44b6f24f6ef7a869231243b16bf01a0cf546ab07bc10d8` |
| `screen-p83-B-grid-4-production-final-state` | 5 | 9703424 | 44320 | 9 + 0 | `ed58745ab2d15f14601cb2bd89bc912975ae932d3c3b82f7e1962410cee641f0` |
| `packet48b-old-boot-logs` | 4 | 6520832 | 946181 | 8 + 0 | `2d4e77285d041a3fb4b1945330135a9966145f0edef9283202d748e0d25c4c39` |
| `packet57-private-driver-cache` | 48 | 20557824 | 4679433 | 52 + 0 | `0f59ffb9538adbf166bf73cab515e3650403394868cd77e62e0836a0188ca9b4` |

Original source roots (all absolute; each manifest path is relative to its root):

- `packet49c-round2`: `/home/steve/own-xpu-runtime-results/packet49c-round2`
- `packet49d-round3`: `/home/steve/own-xpu-runtime-results/packet49d-round3`
- `packet52-freeorder-closed-test-build`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet52-freeorder/build`
- `packet53-expert-order-closed-test-build`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet53-expert-order/build`
- `packet56-draft-prefix`: `/home/steve/own-xpu-runtime-results/packet56-draft-prefix`
- `packet57-W57-attribution`: `/home/steve/own-xpu-runtime-results/packet57-attribution/build/device-cards01-a/W57-attribution`
- `packet57-W57-control`: `/home/steve/own-xpu-runtime-results/packet57-attribution/build/device-cards01-a/W57-control`
- `packet67-roofline-build`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet67-roofline/build`
- `packet83-mini`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet83-draft-bytes/build/mini`
- `screen-p79-A-0-1`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p79-A-0-1`
- `screen-p79-A-0-1-final-state`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p79-A-0-1/run/after-suite/rank1/draft-final-state`
- `screen-p79-A-1-0-split23`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p79-A-1-0-split23`
- `screen-p79-A-1-0-split23-final-state`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p79-A-1-0-split23/run/after-suite/rank0/draft-final-state`
- `screen-p79-A-2-0`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p79-A-2-0`
- `screen-p79-A-2-0-final-state`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p79-A-2-0/run/after-suite/rank0/draft-final-state`
- `screen-p79-A-3-1`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p79-A-3-1`
- `screen-p79-A-3-1-final-state`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p79-A-3-1/run/after-suite/rank1/draft-final-state`
- `screen-p81-A-0-production`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p81-A-0-production`
- `screen-p81-A-0-production-final-state`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p81-A-0-production/run/after-suite/rank1/draft-final-state`
- `screen-p81-A-1-gate-input-packed`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p81-A-1-gate-input-packed`
- `screen-p81-A-1-gate-input-packed-final-state`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p81-A-1-gate-input-packed/run/after-suite/rank1/draft-final-state`
- `screen-p81-A-2-down-input-packed`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p81-A-2-down-input-packed`
- `screen-p81-A-2-down-input-packed-final-state`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p81-A-2-down-input-packed/run/after-suite/rank1/draft-final-state`
- `screen-p81-A-3-input-packed`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p81-A-3-input-packed`
- `screen-p81-A-3-input-packed-final-state`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p81-A-3-input-packed/run/after-suite/rank1/draft-final-state`
- `screen-p81-A-4-production`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p81-A-4-production`
- `screen-p81-A-4-production-final-state`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p81-A-4-production/run/after-suite/rank1/draft-final-state`
- `screen-p83-B-grid-0-production`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p83-B-grid-0-production`
- `screen-p83-B-grid-0-production-final-state`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p83-B-grid-0-production/run/after-suite/rank1/draft-final-state`
- `screen-p83-B-grid-1-q4-g32`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p83-B-grid-1-q4-g32`
- `screen-p83-B-grid-1-q4-g32-final-state`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p83-B-grid-1-q4-g32/run/after-suite/rank1/draft-final-state`
- `screen-p83-B-grid-2-prefix990`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p83-B-grid-2-prefix990`
- `screen-p83-B-grid-2-prefix990-final-state`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p83-B-grid-2-prefix990/run/after-suite/rank1/draft-final-state`
- `screen-p83-B-grid-3-prefix985`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p83-B-grid-3-prefix985`
- `screen-p83-B-grid-3-prefix985-final-state`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p83-B-grid-3-prefix985/run/after-suite/rank1/draft-final-state`
- `screen-p83-B-grid-4-production`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p83-B-grid-4-production`
- `screen-p83-B-grid-4-production-final-state`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p83-B-grid-4-production/run/after-suite/rank1/draft-final-state`
- `packet48b-old-boot-logs`: `/home/steve/own-xpu-runtime-results/packet48b-production/evidence`
- `packet57-private-driver-cache`: `/home/steve/own-xpu-runtime-results/packet57-attribution/build/driver-cache`

Initial audit archive: `/mnt/raid-models/own-xpu-runtime-archive/cleanup-audit-20261018T0312/audit.tar.gz` (34,270,636 bytes), SHA-256 `9205232957c66c98cb7f2fa42a55b219a4276324b798f510ce6eef85904cef14`. Its `_audit-manifest.json` hashes all 357 audit files. Full content verification and GNU member count (358 regular + 0 hard links) passed before exact-path deletion of the temporary audit copies. This recovered 364,249,088 bytes of this task's scratch allocation, **not counted** toward the original-data reclamation target. The initial audit contains the deletion/verification implementation, inventories, reference searches, the first 37 source-tree reports/manifests/kept lists, before/after collector maps and check logs. The final two source-tree reports and definitive kept list are in the supplemental audit.

Restore source files by verifying the listed archive SHA-256, reading `.cleanup/plan.json` for the original root and `.cleanup/manifest.sha256` for file identities, then extracting only the required `payload/` members into that root with the first path component stripped. Preserve existing retained files. A full restore can use GNU tar `--strip-components=1 --wildcards 'payload/*'`; do not extract the embedded metadata over source files. Verification code and exact member lists are retained in the audit archive.

### Validation after removal

The first complete post-removal checks below were followed by another full rerun after the final 27 MB removal. Neither run launched devices:

- `python3 -B experiments/own-xpu-runtime/ops/lane-queue/lanequeue.py plan --lane A`: exit 1. The current packet 97 composite control already has its output directory; direct child-plan capture confirms `new screen evidence output required`. The other four queued rows passed. Earlier baseline also failed the freshness guard on an in-progress queued job; queue contents progressed during this task.
- The same command with `--lane B`: exit 1. `packet86-hc-loadkeep-B` already had its output directory; the other six rows passed. Baseline also had an existing-output failure. A subsequent captured read-only plan found that row had already left the queue; queue state was not modified by cleanup.
- Packet 84 `ops/packet84-orchestration/verify_ready.py`: same failure before and after, `chain already started`, after its source/hash checks.
- Packet 91 `verify_ready.py`: same preexisting false readiness/preparation assertion before and after.
- Packet 97 `verify_ready.py`: false readiness/preparation assertion before and after. Its source was concurrently updated by ongoing work, so traceback line numbers differ; readiness files were not changed here.
- `check_inputs.py` for packets 84, 91 and 97: **PASS** on 14,675 / 14,246 / 14,147 static files respectively, errors empty, `device_executed=false`, `model_payload_read=false`. These full static input checks supplement the readiness scripts that stop early on existing state.
- Packet 49c / 49d / 56 record collectors: before/after maps of source path, hash and byte count match exactly, covering 1,089 / 1,091 / 1,093 record members. No removed file was an actual collector input.
- Packet 67 verifier: **PASS** before/after; only its build-size accounting changed. Its report writer was redirected to audit scratch so the check did not change repository evidence.
- All final retained-file hashes passed. No missing-input failure was observed. The storage precheck still fails by the margin stated above; neither that failure nor existing queue/readiness failures are presented as a pass.

The request's 5 GB target remains unmet. The next safe action requires a newly closed, fully audited candidate or completion of ongoing work; protected or referenced files were not traded for disk space. No packet 97 chain was launched by this cleanup.

Supplemental audit archive: `/mnt/raid-models/own-xpu-runtime-archive/cleanup-audit-extra-20261018T0312/audit.tar.gz` (1,428,867 bytes), SHA-256 `0947de9851a18e00fdb223393c9cbffc89f84ce091f1f1ee1753dbad872aa9c8`. All 37 files were fully content-verified against its embedded manifest; GNU count 38 regular + 0 hard links. Its `root-cleanup-20261018T0312/final-kept.json` is the final list of all 18,571 retained files, whose hashes passed after the last source deletion. It also contains the last two archive reports and the final checks. Its 9,887,744 bytes of temporary copies were removed only after verification and are excluded from reclaimed original data.

Final rerun after **all** source removals (queue contents continued progressing):

| Check | Result |
| --- | --- |
| `lane-A` at 2026-10-18 03:41:32 UTC | exit 1 |
| `lane-B` at 2026-10-18 03:41:35 UTC | exit 1 |
| `verify-84` at 2026-10-18 03:41:33 UTC | exit 1 |
| `verify-91` at 2026-10-18 03:41:33 UTC | exit 1 |
| `verify-97` at 2026-10-18 03:41:33 UTC | exit 1 |
| `inputs-84` at 2026-10-18 03:41:57 UTC | exit 0 |
| `inputs-91` at 2026-10-18 03:41:57 UTC | exit 0 |
| `inputs-97` at 2026-10-18 03:42:06 UTC | exit 0 |

Final queue rows, captured verbatim without environment values:

Lane A:

```json
{"name": "p97b-d27742791d5b859d-composite-A-1-candidate", "line": 1, "plan": "FAILED", "reason": "CPU plan failed (seal, inputs or fresh outputs); inspect packet plan directly"}
{"name": "p97b-d27742791d5b859d-composite-A-2-control", "plan": "passed", "seal": "checked by packet plan/wrapper"}
{"name": "packet94-A-grid", "plan": "passed", "seal": "checked by packet plan/wrapper"}
{"name": "packet92-A-grid", "plan": "passed", "seal": "checked by packet plan/wrapper"}
```

Lane B:

```json
{"name": "packet86-exp-constgrid-B", "line": 1, "plan": "FAILED", "reason": "output directory already exists"}
{"name": "packet86-exp-onecached-B", "plan": "passed", "seal": "checked by packet plan/wrapper"}
{"name": "p97b-d27742791d5b859d-composite-B-0-control", "plan": "passed", "seal": "checked by packet plan/wrapper"}
{"name": "p97b-d27742791d5b859d-composite-B-1-candidate", "plan": "passed", "seal": "checked by packet plan/wrapper"}
{"name": "p97b-d27742791d5b859d-composite-B-2-control", "plan": "passed", "seal": "checked by packet plan/wrapper"}
{"name": "packet98-smoke-B", "plan": "passed", "seal": "checked by packet plan/wrapper"}
```

The last direct child-plan capture again identifies existing output as the active-job rejection. Final input checks all passed; readiness failures remained the same existing state assertions described above.


## Second pass after coordinator closures (2026-10-18, started 03:44 UTC)

**Reclaimed 2,048,720,896 allocated bytes (2.05 GB); stopped immediately after crossing the requested 2 GB threshold.** This exceeds the additional 1.5 GB requirement. Nine source trees were archived, containing 79,797 removed regular-file paths, including hard-link paths. The allocation count deduplicates inodes and counts an inode only when all its links were removed. Logical bytes and concurrent changes in filesystem free space are not substituted for reclaimed allocation.

At the first filesystem reading, root had 18,313,216,000 bytes available. Before deletion, packet 97's storage check reported 18,151,378,944 free against 18,812,225,206 required (failed). At **2026-10-18 03:53:53 UTC**, after source removal and verified audit-scratch cleanup, it reports **19,952,496,640 free / 18,812,225,206 required; margin 1,140,271,434 bytes; passed=true**. Both lanes continued writing during this task. This is a point-in-time storage check, not full launch readiness or a reservation against later screen writes.

Only this cleanup record is committed. Existing shared-main changes were preserved. Work was CPU/disk only: archive/check programs ran under `nice -n 19 ionice -c3 taskset -c 8-15,24-31`, Python used `-B`, and executed programs had stdin `/dev/null`. Source hashing and archive writes/reads used per-file `POSIX_FADV_DONTNEED` after reading/flushing where supported, including the input-check read wrapper. No global cache drop, host setting, GPU, service, sudo or secret display was used.

### Reference decisions and retained inputs

The owner's newly closed list authorized this pass. Whole-repository exact-path and parent/name searches included hidden and ignored files except `.git`; Python/shell consumer searches also included ignored files. The broad search recorded the same 68 inaccessible unrelated Qwen cache/STOP paths as the earlier pass. The source-code search had no access errors. Search indexes, complete source hits, candidate plans and protected-path intersections are in the audit archive.

- **Packets 80 and 84:** removed only `.bin`/`.bf16` leftovers under completed `W2m`, `WS`, `WSs`, `WS128x`, and `WS128` windows in `build/device-cards01-a`. Kept all early `K0/K1a/K1b/K2/W0p` trees, the entire KD tree, every window-bound receipt, all JSON/JSONL/log files, binaries, seals and source/build inputs. `resume_chain.file_inventory` recursively reads the early trees; these remain complete. Submission collection still opens KD fixture bytes; those remain too. No selected raw file was a window-bound collector receipt.
- **Five `p84s-*` screen trees:** removed private `run/adapter/build/driver-cache` files, duplicate input `vocab.bin` files, and the five raw after-suite draft-state files where present. This includes `p84s-B-3-control-refused-58f-undrained`; its refusal, kernel and coordination evidence remains. All JSON/JSONL, timestamps, output tokens, receipt hashes, logs, summaries and compressed state metadata stay available.
- **Two packet 95 screens:** the same bulk-only selection in `p95-exp-grid-prefetch-B-grid-B-0-production` and `p95-exp-grid-prefetch-B-grid-B-1-exp-grid-prefetch`. The third screen was left intact because the threshold had been reached.
- **Packet 95 build and all packet 90 evidence remain untouched.** Packet 97's source adapter verifies source seals and comparison inputs even for closed choices; there was no need to remove those dependencies. Packet 90 E1/production qualification inputs remain complete.
- Packet 91/97 prior-chain seal paths and both full static input inventories were checked against the selected exact-path set: no intersection. The prior-chain seals name packet 80/84 build objects outside these completed chain trees; all remain. Submission prepared `evidence.json.gz` and `result.json` files are tracked and remain intact. No tracked file was selected for deletion.

Packets 91, 93, 97, 98, 58g/58s, the packet 49 oracle, packet 17's `wa-reference`, and `screen/v4-lanes` code were not changed. Historical raw-state analysis that needs an archived byte must restore that member first; current collectors, screen comparisons and readiness inputs retain their files.

### Archives and restoration

Archive base: `/mnt/raid-models/own-xpu-runtime-archive/`. Each directory below contains one `unreferenced-bulk-20261018T0344.tar.gz`. Every archive embeds `.cleanup/manifest.json`, `.cleanup/manifest.sha256`, `.cleanup/kept.json`, and `.cleanup/plan.json`; the plan records the original absolute source root and the manifest enumerates exact paths, sizes and SHA-256 values. Payload names are `payload/<relative source path>`.

Before each exact-path unlink, every archive member's content was verified against the per-file manifest; hard-link members were verified against their already verified target. The exact member-name set and an independent GNU tar regular-plus-hard-link count matched. The archive SHA, all selected source bytes and all kept-file hashes were then rechecked. Accessible process descriptors were checked for selected open paths. No recursive deletion or deletion glob was used; directories and symlinks remain. Kept hashes passed immediately after removal and again in the final combined check (9,062 retained files).

| Archive directory | Removed files | Reclaimed bytes | tar.gz bytes | Members (regular + hard links) | Archive SHA-256 |
| --- | ---: | ---: | ---: | ---: | --- |
| `packet80-record-bundle-late-raw` | 39664 | 790949888 | 469581521 | 21236 + 18432 | `f19419f61bef4455626258736eb2c759c43c6e5af53312ce02e8c8c2b9856483` |
| `packet84-record-bundle-late-raw` | 39664 | 790949888 | 469577378 | 21236 + 18432 | `451b4edb1b70c573a7a4528295fcca3816a179dc09d66d414e811aead4349f92` |
| `screen-p84s-B-0-control` | 68 | 68046848 | 23440155 | 72 + 0 | `2f5f53375a1d064b313fabe157979e91b409f4201839c373ace2f4d94ecb8c05` |
| `screen-p84s-B-1-candidate-a` | 68 | 68046848 | 23440295 | 72 + 0 | `47edb7ad0ead13a1762c665f686fe21abb48e2d19cfab6bf9f359198ca2352a9` |
| `screen-p84s-B-2-candidate-b` | 66 | 67751936 | 23367673 | 70 + 0 | `a97f33765504ab63f8b93afee1ee5852bdbe8bb1514e07b2ac6015d7d4b994b4` |
| `screen-p84s-B-3-control` | 68 | 68046848 | 23440219 | 72 + 0 | `cef59f9e6103d5f9d6a1c6610b2345ffff83fa46c5b27ebc406dc004746bc937` |
| `screen-p84s-B-3-control-refused-58f-undrained` | 63 | 58343424 | 23393598 | 67 + 0 | `da9b55b91e4f006aefec7117e4d52d68e57e4a209b7b3693254706f3dc79e0b4` |
| `screen-p95-exp-grid-prefetch-B-grid-B-0-production` | 68 | 68292608 | 23496762 | 72 + 0 | `2a4ff917e0fd6cb21ff07fb920a1490715de20f1912f45b0cf48c50628173efd` |
| `screen-p95-exp-grid-prefetch-B-grid-B-1-exp-grid-prefetch` | 68 | 68292608 | 23496383 | 72 + 0 | `cc07ba743ae27699bac684cec2bc5468d4371bc429c3591041b540a1c84274d8` |

Original source roots:

- `packet80-record-bundle-late-raw`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet80-record-bundle/build/device-cards01-a`
- `packet84-record-bundle-late-raw`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet84-record-bundle/build/device-cards01-a`
- `screen-p84s-B-0-control`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p84s-B-0-control`
- `screen-p84s-B-1-candidate-a`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p84s-B-1-candidate-a`
- `screen-p84s-B-2-candidate-b`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p84s-B-2-candidate-b`
- `screen-p84s-B-3-control`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p84s-B-3-control`
- `screen-p84s-B-3-control-refused-58f-undrained`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p84s-B-3-control-refused-58f-undrained`
- `screen-p95-exp-grid-prefetch-B-grid-B-0-production`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p95-exp-grid-prefetch-B-grid-B-0-production`
- `screen-p95-exp-grid-prefetch-B-grid-B-1-exp-grid-prefetch`: `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p95-exp-grid-prefetch-B-grid-B-1-exp-grid-prefetch`

Audit archive: `/mnt/raid-models/own-xpu-runtime-archive/cleanup-audit-20261018T0344/unreferenced-bulk-20261018T0344.tar.gz` (13,508,517 bytes), SHA-256 `e065089a4f9a7c5b5591932dd0114bf05b5f200b4adaa1003a7faf74542710ca`. All 116 audit payload files were content-verified; GNU member count 120 regular + 0 hard links, including four embedded metadata files. Its `payload/final-kept.json` is the final retained-file hash list. It also preserves reference searches, exact deletion/verification code, all per-tree reports/manifests, before/after input inventories, collector maps, screen comparisons and check logs. Verified temporary audit copies were deleted exactly; their 101,978,112 allocated bytes are **excluded** from the 2.05 GB original-data reclamation claim.

Restore by checking the archive SHA-256, reading `.cleanup/plan.json` for the original root, and extracting the required `payload/` members into that root with one path component stripped. For a complete payload restore, GNU tar supports `--strip-components=1 --wildcards 'payload/*'`; preserve existing retained files and check the restored bytes against the embedded manifest. Do not extract `.cleanup` over source files.

### Validation after removal

| Check | Before exit | After exit |
| --- | ---: | ---: |
| `lane-A` | 0 | 1 |
| `lane-B` | 0 | 1 |
| `verify-80` | 1 | 1 |
| `verify-84` | 1 | 1 |
| `verify-91` | 1 | 1 |
| `verify-97` | 1 | 1 |
| `inputs-91` | 0 | 0 |
| `inputs-97` | 0 | 0 |
| `storage-97` | 1 | 0 |

- Packet 91 input check: **PASS**, 14,246 static files, no errors; `device_executed=false`, `model_payload_read=false`.
- Packet 97 input check: **PASS**, 14,147 static files, no errors; `device_executed=false`, `model_payload_read=false`. Full per-window inventories are retained in the audit.

- Packet 80/84 readiness still rejects `chain already started`; packet 91/97 readiness still rejects the preexisting readiness/preparation flags. These are not reported as passes. All check logs and lane-plan rows are retained in the audit.
- Both lane plans passed before removal. After removal, lane A's `p97b-d27742791d5b859d-composite-A-2-control` and lane B's `packet86-exp-onecached-B` rejected existing output directories; the other five A rows and four B rows passed. The direct A child-plan capture confirms `new screen evidence output required`. Those jobs subsequently left the live queue during this audit; no queue file was edited here.
- Both unchanged submission replays pass against the committed prepared bundles. Packet 80's collector map remains identical across 1,101 members; packet 84's map remains identical across 1,103 members. Packet 84's existing collector has an API mismatch: it calls `verify_receipt(window)` without the now-required `data=` argument. This failed before removal. The audit-only collector adapter supplied the actual admission receipt bytes to the unchanged verifier; it did not skip verification or edit repository code. The ordinary saved-bundle replay passes without that adapter.
- Packet 84's composition comparison passes unchanged. Packet 97's packet 90 and packet 95 source-adapter outputs are identical as parsed JSON before/after (statuses `winner` and `no-winner`), including their source/receipt hash maps. This checks the retained qualification evidence beyond readiness scripts that stop at existing flags.
- No missing-input regression was observed. The final storage result above is separate from the existing preparation blockers. No packet 97 chain was launched.
