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


## Third pass for the packet 97e rerun (2026-10-18; completed 2026-10-18 05:29:07 UTC)

**Reclaimed 2,014,814,208 allocated bytes (2.015 GB), below the 2.5 GB cap.** Removed 2,713 exact regular-file paths from 44 closed/superseded screen trees, only after verified archival. Allocation accounting deduplicates inodes and counts an inode only when every link was selected; filesystem free-space drift is not used as the reclamation claim. No further source removal is planned for this pass.

Initial root availability was 18,704,494,592 bytes. At 2026-10-18 05:29:07 UTC, root has **20,172,414,976 bytes available**, which is **1,360,189,770 bytes above** the brief's 18,812,225,206-byte launch requirement. Concurrent screens/builds continued writing. This is a point-in-time margin, not a reservation. The packet's current storage precheck also passes; its own calculated requirement differs from the brief and is retained verbatim in `after-storage-97.log`.

Work stayed on `main`, with `git pull --ff-only` reporting up to date. Only this record is committed. No GPU, service, sudo, host setting, live queue, cache outside the selected private screen trees, or packet build tree was changed. Packet 97’s failed chain was left intact, as were all never-touch packets and prepared submissions. Bulk programs ran with `nice -n 19 ionice -c3 taskset -c 8-15,24-31`, Python `-B`, and stdin `/dev/null`. Per-file `POSIX_FADV_DONTNEED` was used after bulk hashing/reading and archive writes/verification; no global cache drop occurred. Audit data was written directly to the archive disk, so no root scratch recovery is included in the result.

### Reference audit and selection

Repository-wide exact absolute/relative-path and parent/name searches included hidden and ignored files, excluding `.git` and binary/compressed payloads. The broad text search capped files at 32 MB and recorded 68 inaccessible unrelated Qwen cache/STOP paths; the Python/shell searches were unrestricted by size and had no access errors. No exact selected path was named by a Python/shell consumer. Dynamic consumers were inspected separately. The before-input inventories for packets 91/97 and tracked-file list had no selected-path intersection. No accessible process command line named a selected tree; every deletion also checked accessible process descriptors for open selected files.

- **Old `screen/v3/evidence` and `screen/evidence`:** archived private driver-cache bytes, duplicate vocabulary/input tables, raw/compressed after-suite state, old kernel boot/before captures, and both old summary copies. These screens are before packet 76 and superseded under the owner’s brief. All receipts, identity/window JSON, token text, native logs, timings and other JSONL remain. Packet 62’s diagnostic still has its receipts, rank0 timings and snapshot JSON; packet 63 still has its complete receipt inputs. Code, locks and teardown state are untouched.
- Two historical records (`packet59c-draft-select/source-diagnosis-evidence.json` and `packet56w-chain/evidence/screen-context.json`) name four archived old top-level summaries. They are historical provenance, not current code inputs; their recorded hashes are preserved. Restore the named archive member before reopening that historical summary.
- **Closed v4 screens for packets 84s, 92, 93, 94, 95 and 86:** archived only remaining raw/compressed state and old kernel boot/before captures. Every v4 JSON stays. All `kernel-window.jsonl` files stay, including packet 93x’s required analysis inputs. Packet 100’s packet 86 production attribution inputs stay. Packet 90 and all packet build trees stay.
- Current packet 97 source-adapter outputs for 90/91/92/93/94/95 are identical as parsed JSON before/after, including receipt/source hash maps. Their existing statuses remain winner/winner/failed/winner/failed/failed; those failures were not introduced here or converted into passes.

### Archives and restoration

Archive base: `/mnt/raid-models/own-xpu-runtime-archive/cleanup-third-20261018/`. Each directory below contains exactly one `verified-bulk-third.tar.gz`. Each archive embeds `.cleanup/plan.json` (absolute original root and exact selected paths), `.cleanup/manifest.json`, `.cleanup/manifest.sha256`, and `.cleanup/kept.json`. Payload members are `payload/<relative source path>`.

Every member was fully read and SHA-256 verified before deletion. Hard-link handling verifies target content, and an independent GNU tar regular-plus-hard-link count matches the manifest plus four metadata members. The archive SHA, every selected source hash/stat and every retained hash were rechecked before exact-path unlink. No recursive delete or deletion glob was used; directories and symlinks remain. All retained hashes passed immediately after each deletion and again in the final check.

| Archive directory | Files removed | Reclaimed bytes | tar.gz bytes | Members (regular + hard links) | Archive SHA-256 |
| --- | ---: | ---: | ---: | ---: | --- |
| `old-screen-v3-evidence-p56x-sleep20-A2` | 109 | 84430848 | 27232884 | 113 + 0 | `0913139e37e99d1d3490ca3d9561648fa5b2b167f020e3ba5c6b695adf1a4be1` |
| `old-screen-v3-evidence-p59c-experts-route-A` | 108 | 85528576 | 27518922 | 112 + 0 | `53f15a4ab5de5d65f958a54e2bd431b1ecfd8310c348da509de8f06706e891cb` |
| `old-screen-v3-evidence-p61x-pl-1-B` | 109 | 84582400 | 27295566 | 113 + 0 | `ab06f45b0d0554a5231db04c7f880afe140f331fc3fdd2e3e3004d7c24729fb9` |
| `old-screen-v3-evidence-p61x-pl-1split23-A` | 109 | 84582400 | 27301778 | 113 + 0 | `b61bd0515bc8ad029a4315687d729be490edc3928ded383bb487d2d83a028f11` |
| `old-screen-v3-evidence-p63-drafthc-A` | 110 | 85827584 | 27584562 | 114 + 0 | `3245ef525d5a9900fe3e1afc4a29bee779c0756b5546169020dedfe4abd66115` |
| `old-screen-v3-evidence-p63-drafthc-B` | 110 | 85827584 | 27571020 | 114 + 0 | `0a5093ae82a01072215c7d3f1d10e6031cef724daae3cadda2a89766ffe44ef4` |
| `old-screen-v3-evidence-packet56w-B` | 109 | 84422656 | 27257605 | 113 + 0 | `8757d4a7c2bb3828d043b518c91c0381ff01a8a3e2010795bcc72e7c1360773b` |
| `old-screen-v3-evidence-packet60-B` | 109 | 84570112 | 27306773 | 113 + 0 | `387cc134e80b7cc8726744562318f15bb47378781979ff6e927ca150667fd99a` |
| `old-screen-v3-evidence-packet61-A` | 109 | 84570112 | 27303980 | 113 + 0 | `9bc66d3608a224ce043bd1cb1cd09d89c2b4730c06bc0579dd186ecb7e85a453` |
| `old-screen-v3-evidence-packet61-B` | 109 | 84570112 | 27294284 | 113 + 0 | `1fe592820decf532f2ffd6f2fdc31f3157aad1ada83459950cae70efc2c18c47` |
| `old-screen-v3-evidence-packet61x-A` | 109 | 84570112 | 27290573 | 113 + 0 | `42387399ecdd3238b06d9484525445f270eba532ae5b0ef4b9785af23c6f3741` |
| `old-screen-v3-evidence-packet61x-B` | 109 | 84570112 | 27299684 | 113 + 0 | `18828b57b541641294ab704d958de05ff1074f9ab011ccf494a54a4a2a15cbb0` |
| `old-screen-v3-evidence-packet61x-B2` | 109 | 84570112 | 27287600 | 113 + 0 | `74ca71fc7ac439b291c0fced0e19790f8d78d167d580835f1640bf8970f8ae08` |
| `old-screen-evidence-p56-ctl-b` | 109 | 84414464 | 27264232 | 113 + 0 | `89a4317b52bce6c0299242b5df27d1a130ff497fefb95050abab67cadaa6864a` |
| `old-screen-evidence-p56x-spin-a` | 109 | 84422656 | 27245104 | 113 + 0 | `fd908a431849add199f3c14435a2405c703c30e8e628493d4010bdf2918f3f40` |
| `old-screen-evidence-p59-a` | 107 | 84721664 | 27340648 | 111 + 0 | `f9d5a89eb089b3ab2f1d1e2a97809f2a1d34c3bc04d48d001078603100fdd715` |
| `old-screen-evidence-p59c-attention-a` | 109 | 85364736 | 27481455 | 113 + 0 | `e30cbe66a1a349a22393f895ed3b567b16096a91b6831ec8c318144518a97aa6` |
| `old-screen-evidence-p59c-hc-a` | 110 | 85667840 | 27541173 | 114 + 0 | `b90e06b98d9ea67fff03acee756639bb1ad4b29bb5e4be5b984c83a775a2da75` |
| `old-screen-evidence-packet56-a` | 109 | 84414464 | 27265269 | 113 + 0 | `949647e46dbce665ff18a0c1880a94a567681d9f75e0d63c409a4b903160c34b` |
| `old-screen-evidence-packet56w-a` | 109 | 84422656 | 27263693 | 113 + 0 | `445c1ad3ac9f4b0450f78f7c3e6c9408a82e8c56672309856e51cf067f57ffc7` |
| `old-screen-evidence-packet60-a` | 109 | 84570112 | 27307976 | 113 + 0 | `ec621a72bce80a614f011ef90391ca40359f0e009513d8141d808d26d9e79776` |
| `v4-p84s-B-0-control` | 16 | 3964928 | 2546123 | 20 + 0 | `e496262bf4a9f1ef6b69acfc17475fc96ff5a0f8c44469b91d33dd187f73ee02` |
| `v4-p84s-B-1-candidate-a` | 16 | 3964928 | 2546612 | 20 + 0 | `9fc4f49adce855b7d5a586705070eeb63b89d29d1b7f8b16c75fc6f7c0c33699` |
| `v4-p84s-B-2-candidate-b` | 16 | 3964928 | 2546252 | 20 + 0 | `b5ff5e90a133b9b2eaf2eb2141f59f625b76b1ea915222894e186f61d8aa932c` |
| `v4-p84s-B-3-control` | 16 | 3969024 | 2547102 | 20 + 0 | `c0525ab36eac42f1b8b58848a85b536aeb8b00449f6fcb310a652e2875da7cdc` |
| `v4-p84s-B-3-control-refused-58f-undrained` | 16 | 3969024 | 2547852 | 20 + 0 | `f5c72a8c2174ec89e5f92fd713ed76b6a8e6dbd6cb83efd408a3ce7a44c4d0e3` |
| `v4-p92-A-grid-A-0-production` | 21 | 13676544 | 2592504 | 25 + 0 | `4673fd247dd61783a7b22c407f19c46fd0e14881c095ffff1ea82a3130f1ae25` |
| `v4-p92-A-grid-A-1-reply-first` | 21 | 13676544 | 2592596 | 25 + 0 | `fbd8c46174b9c815bd339e75845c0074669784120e287d86a77beb2fd784e5a0` |
| `v4-p92-A-grid-A-2-production` | 21 | 13676544 | 2592335 | 25 + 0 | `0bb82f87b9d88a791dee9a475ee800232fddea27e36ebb9f7cf5688efcfefaf7` |
| `v4-p93-B-grid-A-0-production` | 21 | 13676544 | 2592055 | 25 + 0 | `efffaf599493a587874d17dd7126d7cdca56deb08019e6631969e8c8dd033c21` |
| `v4-p93-B-grid-A-1-head-transpose` | 21 | 13676544 | 2592271 | 25 + 0 | `4a2243b765551370316b7be40aec75e7ef2939e5a6d60112f7004aef0a2b27e4` |
| `v4-p93-B-grid-A-2-production` | 21 | 13676544 | 2592463 | 25 + 0 | `d8501a84a6e47186b1084c8c503be80db5844c1284b1da53384dc7ae8785df6a` |
| `v4-p93-B-grid-B-0-production` | 21 | 13672448 | 2591392 | 25 + 0 | `b0e92bc31539579be3078ee71201cd426f2fe424c4d3714038db6ef51c77ebb3` |
| `v4-p93-B-grid-B-1-head-transpose` | 21 | 13672448 | 2591749 | 25 + 0 | `930641cbfd22fdf22c86587642284cc3578c70b753a4c2546f015ad5e32d3bf1` |
| `v4-p93-B-grid-B-2-production` | 21 | 13680640 | 2593263 | 25 + 0 | `bec15fcd3257fd619e403f322cf6e71889e46155e193c5f3db2cd1e2ff34dbd0` |
| `v4-p94-B-grid-B-0-production` | 21 | 13676544 | 2592777 | 25 + 0 | `b0bcf55fe421b8a8dcc02d345eb6d29c185f86fcde3b023bb260ad8266d7ba23` |
| `v4-p94-B-grid-B-1-hc-normfuse` | 21 | 13676544 | 2592462 | 25 + 0 | `8b3dabb5e5304ae852724ee6f96fe419780b65be8be53e83965c7b8077969e72` |
| `v4-p94-B-grid-B-2-hc-normfuse+weightcache` | 21 | 13676544 | 2592600 | 25 + 0 | `4d491ec86d8a2d798032e21cd74be9b2026e5836ff04c9c58e8b49b9a1cdef1f` |
| `v4-p94-B-grid-B-3-production` | 21 | 13676544 | 2593003 | 25 + 0 | `ab3861869c3a9908c67f93b4bcaecdc2be1a487ec785818e4803653b4c90a1ac` |
| `v4-p95-exp-grid-prefetch-B-grid-B-0-production` | 16 | 3973120 | 2548005 | 20 + 0 | `68f05a372ecf73f195157ccdd17436e98d330dbe251ce89a8498de46e9642513` |
| `v4-p95-exp-grid-prefetch-B-grid-B-1-exp-grid-prefetch` | 16 | 3973120 | 2547631 | 20 + 0 | `c5aa3427263157768d4719d43dcf91a5de5aa62327f4cf858af5706915b97512` |
| `v4-p95-exp-grid-prefetch-B-grid-B-2-production` | 21 | 13676544 | 2592200 | 25 + 0 | `77d9eb073beeb960af18ea6878d5688a3d11932bc6367045a47e9a5655010e7e` |
| `v4-packet86-A-a` | 4 | 3317760 | 522487 | 8 + 0 | `97e304632e4ad8bad391c501e85ac324394c9e877471fe4969a22f01f0ffd6e6` |
| `v4-packet86-B-a` | 14 | 11628544 | 1829193 | 18 + 0 | `a5cfc2de2f3c8f217118d8edb5bb02872692e3f70f9bcca0f62d5a3324b6f8d4` |

Source-root mapping: `old-screen-v3-evidence-<name>` maps to `experiments/own-xpu-runtime/stage2/screen/v3/evidence/<name>`; `old-screen-evidence-<name>` maps to `experiments/own-xpu-runtime/stage2/screen/evidence/<name>`; `v4-<name>` maps to `experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/<name>`. All roots are below `/home/steve/llm-optimizations/`. The embedded plan gives the exact absolute path.

Restore only required `payload/` members after verifying the archive SHA. Extract into the original root with the first path component stripped, preserving all retained files. GNU tar supports `--strip-components=1 --wildcards 'payload/*'` for a full payload restore. Check restored bytes against the embedded manifest; do not extract `.cleanup` over source files.

Audit archive: `/mnt/raid-models/own-xpu-runtime-archive/cleanup-third-20261018/audit.tar.gz` (5,058,301 bytes), SHA-256 `8c7db964b9fbac0184b8d2b8beac67b4f2139adf453c45611c3151afe36ddaaa`. Its embedded `audit-manifest.json` covers the scripts, plans, exact/parent reference searches, source manifests, per-tree reports, before/after checks, source-adapter comparisons and retained-file check. Full content verification and independent GNU count passed: 298 regular + 0 hard-link members. Audit originals also remain on the archive disk.

### Post-removal checks

| Check | Before exit | After exit |
| --- | ---: | ---: |
| `lane-A` | 1 | 0 |
| `lane-B` | 1 | 1 |
| `verify-80` | 1 | 1 |
| `verify-84` | 1 | 1 |
| `verify-91` | 1 | 1 |
| `verify-97` | 1 | 1 |
| `inputs-91` | 0 | 0 |
| `inputs-97` | 1 | 1 |
| `storage-97` | 0 | 0 |

- Lane A passes after cleanup (empty queue at that snapshot). Lane B’s `packet100-down-tile16-B-grid` rejects existing screen outputs; direct child-plan capture confirms `all screen outputs must be fresh`. `packet98c-smoke-B` and `packet87t-micro-B` pass. Baseline lanes also had failures, on the then-current jobs. Queues progressed during cleanup; no queue file was edited.
- Packet 91 input check passes before/after: 14,246 static files, no errors. Packet 97 checks the same 14,375 static files before/after; its sole error is the existing failed-chain `device-cards01-a/STOP: latched output cannot be reused`. Both checks report `device_executed=false` and `model_payload_read=false`. No missing-input error appeared. The fresh packet 97e output is not registered by this cleanup.
- Packet 91 readiness still rejects its existing readiness/preparation flags. Packet 97 readiness still rejects the changed `ops/packet97-orchestration/decision_readiness.py` hash. Packet 80/84 readiness still rejects already-started chains. These failures are retained honestly; storage sufficiency is not full readiness.
- All six packet 97 source-adapter results match before/after. No v4 receipt/JSON changed.
- Final retained-file verification passes for **16,726 files**; every selected source path is absent. No packet chain or GPU job was launched.

## 08:40 UTC: closed builds 104, 86, 102 (coordinator)
Before the packet 103 chain (storage check needs 19.0 GB free). Archived `packet104-tile-transpose/build` (272 files), `packet86-limiter-diagnostic/build` (1,899) and `packet102-iq2-ilp/build` (366) to `/mnt/raid-models/own-xpu-runtime-archive/closed-builds3-20261018/` (tar.gz + per-file sha256 manifest, every member hash-verified from the archive, hard links included) and then removed them. No inbound symlinks and no references from live packets/orchestration (packet 93 and 107 builds kept: referenced by packet 103 and 110). Root free 21.15 GB afterwards.


## disk5 — one-time root reserve to 40 GB (2026-10-18)

Started 09:12 UTC on `steve-b70s`. Initial root availability: **31,003,389,952 bytes (31.003 GB; 28.874 GiB)** on `/dev/nvme0n1p2`. Target is **40,000,000,000 available bytes**, checked after every exact candidate; stop at the first passing reading. RAID `/mnt/raid-models` is `/dev/sdb2` (`fuseblk`), initially 5,187,118,641,152 bytes available. No host setting, GPU, service or sudo action is part of this cleanup. Bulk work uses `nice -n 19 ionice -c3 taskset -c 8-15,24-31`, stdin `/dev/null`.

`git pull --rebase` refused unrelated unstaged orchestration changes. `git fetch origin` then confirmed HEAD == origin/main == `9b49c03e7b7c07b8433d5c70fcc04888ecf634fc`; main-only work and explicit-path commit apply. The repository's delegation instruction was used for read-only candidate audits.

### Whole-root survey (before any movement)

Full-depth `timeout 2400 du -x -B1 /` ran as a background tool session, writing `root-du.tsv` and `root-du.errors`. It completed (exit 1, 521,290 directory rows, 71 permission/disappearance diagnostics); this is a no-sudo survey, not a claim to see inaccessible storage. `/mnt` and `/proc /sys /dev /run` are excluded from the largest-directory list below. Parents overlap, and hard links are charged once in traversal order, so these figures must not be summed. Model storage is excluded/protected; no model candidate was selected. Full survey and search evidence will be retained in the destination's audit archive.

| Largest directory outside excluded roots | Allocated GB | Classification / decision |
| --- | ---: | --- |
| `/home` | 180.094 | Mixed parent; keep |
| `/home/steve` | 180.094 | Mixed parent; keep |
| `/home/steve/llm-optimizations` | 65.484 | Repo packet builds/evidence; protected or retained |
| `/home/steve/llm-optimizations/experiments` | 53.864 | Repo packet builds/evidence; protected or retained |
| `/home/steve/src` | 45.731 | Runtime builds/toolchains; protected except proven exact closed outputs |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime` | 37.357 | Repo packet builds/evidence; protected or retained |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2` | 37.318 | Repo packet builds/evidence; protected or retained |
| `/home/steve/.venvs` | 29.369 | Venvs; protected |
| `/opt` | 12.286 | Runtime builds/toolchains; protected except proven exact closed outputs |
| `/opt/intel` | 12.286 | Runtime builds/toolchains; protected except proven exact closed outputs |
| `/opt/intel/oneapi` | 12.286 | Runtime builds/toolchains; protected except proven exact closed outputs |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen` | 10.510 | Repo packet builds/evidence; protected or retained |
| `/home/steve/.venvs/deepseek-v4-xpu` | 10.003 | Venvs; protected |
| `/home/steve/.venvs/vllm-xpu` | 9.909 | Venvs; protected |
| `/home/steve/.venvs/deepseek-v4-xpu/lib` | 9.894 | Venvs; protected |
| `/home/steve/.venvs/vllm-xpu/lib` | 9.801 | Venvs; protected |
| `/home/steve/qwen38-current-main-runs` | 8.916 | Old run outputs/compiler caches; reject unreadable root-owned internals |
| `/home/steve/llm-optimizations/data` | 8.472 | Repo packet builds/evidence; protected or retained |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes` | 8.471 | Repo packet builds/evidence; protected or retained |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence` | 8.470 | Repo packet builds/evidence; protected or retained |
| `/usr` | 8.411 | System packages/toolchains/caches; protected |
| `/var` | 7.878 | System packages/toolchains/caches; protected |
| `/home/steve/own-xpu-runtime-results` | 7.549 | Old run outputs and evidence; retained (live lineage) |
| `/home/steve/.venvs/minicpm5-baseline-20260912` | 7.431 | Venvs; protected |
| `/home/steve/.codex` | 7.391 | Agent state/caches; protected |
| `/home/steve/.venvs/minicpm5-baseline-20260912/lib` | 7.319 | Venvs; protected |
| `/home/steve/git-archives` | 6.163 | Archives; audit exact children only |
| `/home/steve/.venvs/deepseek-v4-xpu/lib/python3.12` | 5.999 | Venvs; protected |
| `/home/steve/.venvs/deepseek-v4-xpu/lib/python3.12/site-packages` | 5.999 | Venvs; protected |
| `/home/steve/.venvs/vllm-xpu/lib/python3.12` | 5.907 | Venvs; protected |
| `/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages` | 5.907 | Venvs; protected |
| `/opt/intel/oneapi/compiler` | 5.820 | Runtime builds/toolchains; protected except proven exact closed outputs |
| `/home/steve/llm-optimizations/experiments/qwen36-27b-autoround-int4-b70` | 5.339 | Repo packet builds/evidence; protected or retained |
| `/home/steve/llm-optimizations/experiments/qwen27_graphsafe_flash_attention` | 5.320 | Repo packet builds/evidence; protected or retained |
| `/home/steve/llm-optimizations/experiments/qwen36-27b-autoround-int4-b70/diagnostics` | 5.284 | Repo packet builds/evidence; protected or retained |
| `/var/lib` | 5.109 | System packages/toolchains/caches; protected |
| `/opt/intel/oneapi/mkl` | 5.062 | Runtime builds/toolchains; protected except proven exact closed outputs |
| `/var/lib/snapd` | 4.751 | System packages/toolchains/caches; protected |
| `/usr/lib` | 4.731 | System packages/toolchains/caches; protected |
| `/var/lib/snapd/snaps` | 4.324 | System packages/toolchains/caches; protected |

### Candidate decisions recorded before movement

Whole-repository `rg -uuu -l -F` searches include hidden and ignored files, exclude only `.git`, and also scan `/home/steve/own-xpu-runtime-results`. They search full paths and parent/basename aliases. The archive search found 49 files; its 68 access errors are unrelated old Qwen cache/STOP files, with no inaccessible own-runtime/ops files. Exact matches were inspected, including historical maintenance code. No live packet, queue, service or runtime reads the selected archive groups. The old backup-selection script and staging verifier are historical replay consumers: restore original archive paths before replaying them. Current restore guidance will point to the new nested archives; historical receipts remain byte-identical.

`/proc/*/fd`, cwd/exe/root and readable maps checks found no selected-path use (initial check: 49 accessible processes; 496 inaccessible, including kernel/root processes). No sudo workaround was used. Repository plus runtime-results symlink census found no inbound links to the two selected archive directories. Each source is readable with writable parents. Hashes and open-file checks are repeated immediately before exact unlink.

| Exact candidate | Allocated bytes | Closure / reference evidence | Decision |
| --- | ---: | --- | --- |
| `/home/steve/git-archives/cache-consolidation-20261006` | 2,834,530,304 | Four already-retired compiler-cache archives; `data/maintenance/consolidation-20261006/summary.json`; only preservation/restore references and frozen backup inputs. 16 regular files. | Archive and verify, then remove exact source |
| `/home/steve/git-archives/staging-consolidation-20261007` | 2,672,640,000 | Eight explicitly inactive August staging builds, already archived October 7; `notes/2026-10-06-storage-and-recovery-followup.md` and maintenance summary. Only historical verifier/archive/backup scripts use this path. 32 regular files. | Archive and verify, then remove exact source |
| `/home/steve/git-archives/llm-optimizations-pre-main-consolidation-20260814.bundle` | 585,134,080 | Pre-main consolidation Git preservation bundle; `notes/2026-08-14-main-only-consolidation.md`; no runtime consumer. Preserve original bytes and historical refs in nested archive. | Archive and verify, then remove exact file |
| `/home/steve/qwen38-current-main-runs` | 8,915,730,432 | August run/cache history; largest caches contain root-owned unreadable files and unwritable directories. | Reject; cannot fully verify/remove without sudo |
| `/home/steve/git-archives/flash-next-rescue-20261007` | — | Explicitly protected and referenced by own-runtime/Flash-Next provenance. | Keep |
| `/home/steve/own-xpu-runtime-results` | 7,549,018,112 | Remaining outputs include shared lineage, oracle and submitted record material. | Keep |
| Closed `stage2/packet*/build` candidates | — | `ops/screen-cleanup/closed.json` read; closed does not prove unreferenced. Packet93/107 have downstream consumers; protected record/build trees remain. | No packet build selected |

Destination for all disk5 archives: `/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/`. Every candidate gets one `.tar.gz`, adjacent per-file JSON/SHA-256 manifests, archive SHA-256 and a removal receipt. Archives also embed both manifests under `.disk5/`. Every payload member is read and hash-checked, resolving hard-link entries to their verified targets; exact member sets must match. Source hashes/stat inventory and accessible open files are rechecked before removal. Only enumerated files are unlinked and their empty directories removed. Nothing is recursively deleted.

Payload names are `payload/<source-basename>/...` (or `payload/<filename>` for a file). To restore, verify archive SHA-256, extract only `payload` into a scratch directory, verify file hashes with the embedded/adjacent manifest, then put the source basename back under its original parent. For cache/staging archives this restores the original `.tar.zst` files; existing historical restore commands then apply unchanged.

### Execution receipts

### Additional candidates, recorded before their movement (09:18 UTC)

Read-only delegated audits are retained as `qwen-audit-alt-summary.md` and `extra-audit.md` in the audit archive, with full search patterns/matches/errors, ownership and process checks. All exact paths below are readable and removable without sudo, contain no model weight files, and have no accessible open-file/cwd/exe/map use. Whole-repository including ignored/hidden files plus own-runtime-results searches completed; unrelated unreadable files are recorded. No inaccessible process is claimed as inspected. Only the exact closed `build` subtree under `src` is eligible; its source parent stays.

| Exact candidate | Allocated bytes | Closure / reference evidence | Decision |
| --- | ---: | --- | --- |
| `/home/steve/.triton/cache` | 599,433,216 | Generated Triton artifacts, last write September 8; no live reference; source/compiler can regenerate. | Eligible only while below 40 GB |
| `/home/steve/.cache/ms-playwright` | 676,491,264 | September browser/ffmpeg downloads; no repo/results references or running browser; reinstallable. .links points back to installed playwright-core, which is kept. | Eligible only while below 40 GB |
| `/home/steve/.cache/intel-compute-runtime-26.18.38308.1` | 96,043,008 | Six May .deb downloads and checksum file; no reference; installed driver/runtime untouched. | Eligible only while below 40 GB |
| `/home/steve/.cache/neo_compiler_cache` | 1,011,773,440 | Generated compiler cache last written October 17 00:15 UTC; no visible process use. The lone home-cache reference is a May 5 historical note. Live packet references resolve to their separate private native-home/driver-cache trees. | Eligible only while below 40 GB |
| `/home/steve/src/laguna-xpu-kernels-dequant-mad-grf128-transposed-20260731/build` | 594,825,216 | Exact rejected component build; July 31 preregistration closes 0.999856x result below 1.03 gate. No whole-repo/results match for unique source-parent name. Source and separately frozen component evidence kept. | Eligible only while below 40 GB |
| `/home/steve/qwen36-raw-archives` | 195,354,624 | July 2 detached-worktree audit backlog. Sole reference is historical archive-retention.md recovery guidance, explicitly not a path for new work. | Eligible only while below 40 GB |

- Completed `cache-consolidation-20261006` at 2026-10-18T09:19:13.579531+00:00: `/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/cache-consolidation-20261006.tar.gz`; SHA-256 `2ea9659b57b2b9381fe312fb910b5700c202bcc9f8985c6c1c67e4398097a1fe`; 16 file paths verified (0 hard-link members); 2,834,526,208 allocated file bytes reclaimed. Root available: **33,663,635,456 bytes**. Exact original removed.

### Reserve candidate, recorded before any movement (09:19 UTC)

| Exact candidate | Allocated bytes | Closure / reference evidence | Decision |
| --- | ---: | --- | --- |
| `/home/steve/src/laguna-xpu-kernels-transposed-scale-prefetch-dist3-20260731/build` | 375,607,296 | July 31 distance-3 preregistration: 0.997847x, closed at component gate, no endpoint. Sole whole-repo/results parent-name match is the October8 historical storage inventory. Source parent remains. | Use only if earlier candidates leave root below 40 GB |

Both Laguna build candidates have no special files or symlinks. The separate inbound-link audit examined 1,309 repository/runtime-results symlinks, including relative ancestor aliases, and found zero matches and zero errors. Readable process maps also have no candidate matches. The extra source-build audit is `extra-audit.md`; it preserves search outputs, closure references and process/access limitations.

### Final reserve decision, recorded before any movement

`/home/steve/src/vllm-xpu-kernels-poison-20260822/build` is eligible only if concurrent writes leave root below the target after all earlier candidates: **553,480,192 allocated bytes**, 825 regular files, no symlinks/special files/weights. This is the completed August poison diagnostic build, explicitly excluded from the accepted overlay (`notes/2026-08-23-qwen38-absolute-current-main-overlay-preservation.md`, diagnostic exclusion; August22 longkv2 closure). Full repo/results parent-name search has zero matches, and accessible fd/maps and inbound-link checks find no use. Source and poison patch stay. Detailed read-only audit: `extra2-audit.md` with supporting searches/process/permission checks in the audit archive.

- Completed `staging-consolidation-20261007` at 2026-10-18T09:21:35.177580+00:00: `/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/staging-consolidation-20261007.tar.gz`; SHA-256 `40f6751b35e58a0959b30575f4700ceee26242587566c25c9eac009f41e9e6b2`; 32 file paths verified (0 hard-link members); 2,672,635,904 allocated file bytes reclaimed. Root available: **36,265,816,064 bytes**. Exact original removed.

- Completed `pre-main-git-bundle` at 2026-10-18T09:22:07.314210+00:00: `/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/pre-main-git-bundle.tar.gz`; SHA-256 `8e631c06e3193971d573ba5fb47ded6119bd8b40e0abdc973394c0c12b0c25f4`; 1 file paths verified (0 hard-link members); 585,134,080 allocated file bytes reclaimed. Root available: **36,792,770,560 bytes**. Exact original removed.

- Completed `triton-cache` at 2026-10-18T09:22:24.402401+00:00: `/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/triton-cache.tar.gz`; SHA-256 `b74072b7eb3f680fd065daae4f81166d4a58e79c081043f5e0bd12ed48308e17`; 11420 file paths verified (0 hard-link members); 591,806,464 allocated file bytes reclaimed. Root available: **37,391,790,080 bytes**. Exact original removed.

- Completed `playwright-cache` at 2026-10-18T09:22:48.347973+00:00: `/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/playwright-cache.tar.gz`; SHA-256 `73878299281d58a993c2e37d4fa353ed30171c15c50e928e2d6685241501fad8`; 599 file paths verified (0 hard-link members); 676,388,864 allocated file bytes reclaimed. Root available: **38,064,160,768 bytes**. Exact original removed.

- Completed `intel-runtime-download-cache` at 2026-10-18T09:22:54.261861+00:00: `/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/intel-runtime-download-cache.tar.gz`; SHA-256 `5b0ab5b6fb114f440cc34f0458bb7d2b72d1e05a925ef70439631602e41ac4c8`; 7 file paths verified (0 hard-link members); 96,038,912 allocated file bytes reclaimed. Root available: **38,153,596,928 bytes**. Exact original removed.

- Completed `laguna-dequant-mad-closed-build` at 2026-10-18T09:23:23.011630+00:00: `/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/laguna-dequant-mad-closed-build.tar.gz`; SHA-256 `4235d4a3b28efffd5443eb356c0cdf7ae2c0ffb54c5be0ad4a0f0c47391dc837`; 10532 file paths verified (0 hard-link members); 591,273,984 allocated file bytes reclaimed. Root available: **38,729,416,704 bytes**. Exact original removed.

- Completed `qwen36-raw-archives` at 2026-10-18T09:23:34.274268+00:00: `/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/qwen36-raw-archives.tar.gz`; SHA-256 `9ddf33eb83bdadd72dc29bb95ae14a356352b5c6460a75b455229795ef784bae`; 1 file paths verified (0 hard-link members); 195,350,528 allocated file bytes reclaimed. Root available: **38,924,689,408 bytes**. Exact original removed.

- Completed `neo-compiler-cache` at 2026-10-18T09:23:55.962413+00:00: `/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/neo-compiler-cache.tar.gz`; SHA-256 `fbb5796762bf7e7ee13a47d06fce01c22d8d6056cfd375313d3fe62aa3abdfa5`; 2346 file paths verified (0 hard-link members); 1,010,655,232 allocated file bytes reclaimed. Root available: **39,934,689,280 bytes**. Exact original removed.

- Completed `laguna-distance3-closed-build` at 2026-10-18T09:24:16.320368+00:00: `/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/laguna-distance3-closed-build.tar.gz`; SHA-256 `286a9c2bf37c7eba6e4e7e1cfcaadc13c9ad4d566025a0cce5415c92fa07f619`; 4944 file paths verified (0 hard-link members); 373,411,840 allocated file bytes reclaimed. Root available: **40,305,991,680 bytes**. Exact original removed.

### disk5 outcome — target reached once; removal stopped

At **2026-10-18T09:24:16.320456+00:00**, root availability reached **40,305,991,680 bytes = 40.306 GB (37.538 GiB)**, from **31,003,389,952 bytes = 31.003 GB (28.874 GiB)**. The explicit stop threshold was 40,000,000,000 bytes. No further original-data removal followed this first passing reading; the extra poison-build reserve and three other audited small builds remain intact. This is a one-time result, not a reservation against concurrent writes.

Ten exact candidates were archived and removed. All **29,898 file paths** passed full archive-content hash verification and a source rehash before unlink; **0 hard-link members** were resolved to verified content. Allocation accounting, deduplicating inodes and counting a file only when all its links were selected, gives **9,627,222,016 reclaimed file bytes** (directory blocks excluded). Concurrent writes explain why this exceeds the net change in available space. All twelve nested cache/staging archive hashes and the old Git bundle hash also match their original historical ledgers.

All archive paths are below; each has adjacent `.manifest.json`, `.manifest.sha256`, `.tar.gz.sha256` and `.receipt.json` sidecars. The same per-file manifests are embedded under `.disk5/`. The audit archive is listed separately after its verification.

| Archive (absolute path) | File paths | Archive bytes | Root available after removal |
| --- | ---: | ---: | ---: |
| `/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/cache-consolidation-20261006.tar.gz` | 16 | 2,833,624,213 | 33,663,635,456 |
| `/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/staging-consolidation-20261007.tar.gz` | 32 | 2,660,522,494 | 36,265,816,064 |
| `/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/pre-main-git-bundle.tar.gz` | 1 | 584,214,868 | 36,792,770,560 |
| `/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/triton-cache.tar.gz` | 11,420 | 108,131,988 | 37,391,790,080 |
| `/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/playwright-cache.tar.gz` | 599 | 307,704,391 | 38,064,160,768 |
| `/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/intel-runtime-download-cache.tar.gz` | 7 | 94,984,203 | 38,153,596,928 |
| `/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/laguna-dequant-mad-closed-build.tar.gz` | 10,532 | 389,951,507 | 38,729,416,704 |
| `/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/qwen36-raw-archives.tar.gz` | 1 | 195,394,424 | 38,924,689,408 |
| `/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/neo-compiler-cache.tar.gz` | 2,346 | 237,957,068 | 39,934,689,280 |
| `/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/laguna-distance3-closed-build.tar.gz` | 4,944 | 272,735,337 | 40,305,991,680 |

The two closed Laguna source roots remain; only their exact `build` subtrees moved. No packet build, screen, submitted record, model weight, venv, protected rescue archive, credential, service, GPU or host setting was changed. All initial unrelated dirty files remain outside this commit. Survey/audit temporary originals are retained, and their bytes are not counted as reclamation.

Audit archive: `/mnt/raid-models/own-xpu-runtime-archive/disk5-20261018/audit.tar.gz` — **10,034,284 bytes**, SHA-256 `10c3aa58582fdfb09220d078846f46b9d27b24b6d29268f81ada0950d2e51b34`. All **142 audit payload files** plus the embedded manifest were fully read and verified. It retains the whole-root survey, candidate searches and errors, process/link checks, initial and final source inventories, copy/verification/removal code and execution receipts. Its adjacent `audit.manifest.json` and `audit.tar.gz.sha256` provide independent inspection. Audit originals remain on disk.

Final documentation check: `git diff --check` passes for the cleanup log and `CURRENT.md`; only those two paths are committed using `git commit --only -- <paths>`. At 2026-10-18T09:25:50.214369+00:00, root still has **40,272,789,504 bytes available**. No further cleanup is scheduled.


## disk6 — verified archive pass for record-chain headroom (2026-10-18)

Started 14:07:50 UTC on `steve-b70s`. Root `/dev/nvme0n1p2` initially had **31,284,891,648 available bytes (31.285 GB)**. Stop at the first reading at or above **40,000,000,000 bytes**; concurrent chains continue writing. Destination: `/mnt/raid-models/own-xpu-runtime-archive/disk6-20261018/` on `/dev/sdb2` (`fuseblk`, initially 5,179,400,183,808 available bytes).

`git pull --rebase` refused unrelated dirty orchestration files; `git fetch origin` confirmed `main`, HEAD == origin/main == `b133d86af41dcec2ffe8400e311705777913ce8c`. Only this cleanup's explicit paths will be committed. No sudo, service, GPU launch, process kill or host setting change. Bulk work uses `nice -n 19 ionice -c3 taskset -c 8-15,24-31`, stdin `/dev/null`.

The full-depth root `du -x -B1 /` survey finished before movement (exit 1; access/disappearance errors retained). Its directory list, errors and all reference audits remain under the destination's `audit/`. Whole-repository searches include ignored/hidden files and exclude `.git`; inaccessible unrelated files are recorded, not claimed searched. Read-only audits run in parallel while the existing record chain is busy, as AGENTS requires. Live packets, pinned parents, record chains/submissions and protected system/model/agent paths stay.

### disk6 decisions before movement

Each exact selected file is listed in an adjacent plan and per-file SHA-256 manifest. Every archive member is verified, including hard-link targets and symlink text; GNU tar independently checks the member set. Sources are rehashed and accessible process descriptors/maps checked immediately before unlink. Every retained file under a selected root is hashed before and after. Externally linked inodes stay. Only enumerated paths are unlinked; directories remain. Each archive embeds `.disk6/manifest.json` and `.disk6/manifest.sha256`; adjacent archive hashes and receipts record verification and free space.

| Exact candidate root | Selected paths | Closure / decision |
| --- | ---: | --- |
| `/home/steve/src/vllm-xpu-kernels-poison-20260822/build` | 821 | Completed August poison diagnostic, explicitly excluded from accepted overlay. Source parent, JSON/JSONL and notes stay. |
| `/home/steve/src/laguna-xpu-kernels-grouped-onednn-int4-20260801/build` | 714 | Closed exact-but-slower component; no integration authorized. Source parent, JSON/JSONL and notes stay. |
| `/home/steve/src/laguna-xpu-kernels-scale-lane-dedup-20260801/build` | 40 | Closed performance-neutral component below 1.03 gate. Source parent, JSON/JSONL and notes stay. |
| `/home/steve/src/laguna-xpu-kernels-deterministic-scheduler-20260731/build` | 37 | Closed rejected deterministic scheduler, 0.916350x. Source parent, JSON/JSONL and notes stay. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p120-B-grid-0-production` | 47 | Reviewed completed packet120 screen; 1,349 live identities checked by existing cleanup planner. Only private cache/input bulk; all JSON/JSONL, notes, logs and remaining evidence stay. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence/p120-B-grid-1-25-23` | 47 | Reviewed completed packet120 screen; 1,349 live identities checked by existing cleanup planner. Only private cache/input bulk; all JSON/JSONL, notes, logs and remaining evidence stay. |
| `/home/steve/src/laguna-xpu-kernels-attention-gate-m12-20260731` | 9923 | Closed attention-gate endpoint negative (-0.238903%). Only enumerated build/private dependency/package-library files; primary sources, Git metadata, JSON/JSONL, notes and links stay. |
| `/home/steve/src/laguna-xpu-kernels-wide-prefill-qknorm-rope-20260802` | 9908 | Closed unrun wide-prefill candidate; prerequisite failed. Only enumerated build/private dependency/package-library files; primary sources, Git metadata, JSON/JSONL, notes and links stay. |
| `/home/steve/src/laguna-xpu-kernels-rank-sum-rmsnorm-20260731` | 53 | Closed rank-sum component; gain below gate, no endpoint. Only enumerated build/private dependency/package-library files; primary sources, Git metadata, JSON/JSONL, notes and links stay. |
| `/home/steve/src/deepseek-v4-xpu-kernels-m2-event-chain` | 10610 | Closed DeepSeek direct graph event-chain candidate; failed gate, no integration. Only enumerated build/private dependency/package-library files; primary sources, Git metadata, JSON/JSONL, notes and links stay. |
| `/home/steve/src/laguna-xpu-kernels-exact-specialized-20260731` | 1346 | Closed exact-specialized component; performance stop, no endpoint. Only enumerated build/private dependency/package-library files; primary sources, Git metadata, JSON/JSONL, notes and links stay. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet112-route-select` | 14 | Explicit CLOSED registry; only enumerated untracked build outputs (10,285,056 allocated bytes). Source, checked copies, JSON/JSONL, notes, chains, dirty/tracked files and external links stay. No live seal/copy-lineage consumer. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet113-gdn-row` | 19 | Explicit CLOSED registry; only enumerated untracked build outputs (39,981,056 allocated bytes). Source, checked copies, JSON/JSONL, notes, chains, dirty/tracked files and external links stay. No live seal/copy-lineage consumer. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet115-large-grf` | 186 | Explicit CLOSED registry; only enumerated untracked build outputs (107,655,168 allocated bytes). Source, checked copies, JSON/JSONL, notes, chains, dirty/tracked files and external links stay. No live seal/copy-lineage consumer. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet116-qsa-schedule` | 64 | Explicit CLOSED registry; only enumerated untracked build outputs (121,393,152 allocated bytes). Source, checked copies, JSON/JSONL, notes, chains, dirty/tracked files and external links stay. No live seal/copy-lineage consumer. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet120-placement` | 68 | Explicit CLOSED registry; only enumerated untracked build outputs (104,378,368 allocated bytes). Source, checked copies, JSON/JSONL, notes, chains, dirty/tracked files and external links stay. No live seal/copy-lineage consumer. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet121-miss-table` | 1026 | Explicit CLOSED registry; only enumerated untracked build outputs (167,231,488 allocated bytes). Source, checked copies, JSON/JSONL, notes, chains, dirty/tracked files and external links stay. No live seal/copy-lineage consumer. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet122-draft-budget` | 1 | Explicit CLOSED registry; only enumerated untracked build outputs (135,168 allocated bytes). Source, checked copies, JSON/JSONL, notes, chains, dirty/tracked files and external links stay. No live seal/copy-lineage consumer. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet122-draft-hc` | 33 | Explicit CLOSED registry; only enumerated untracked build outputs (98,996,224 allocated bytes). Source, checked copies, JSON/JSONL, notes, chains, dirty/tracked files and external links stay. No live seal/copy-lineage consumer. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet125-miss-transfer` | 66 | Explicit CLOSED registry; only enumerated untracked build outputs (12,574,720 allocated bytes). Source, checked copies, JSON/JSONL, notes, chains, dirty/tracked files and external links stay. No live seal/copy-lineage consumer. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet127-head-retune` | 50 | Explicit CLOSED registry; only enumerated untracked build outputs (88,690,688 allocated bytes). Source, checked copies, JSON/JSONL, notes, chains, dirty/tracked files and external links stay. No live seal/copy-lineage consumer. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet129-draft-acceptance` | 1557 | Explicit CLOSED registry; only enumerated untracked build outputs (95,133,696 allocated bytes). Source, checked copies, JSON/JSONL, notes, chains, dirty/tracked files and external links stay. No live seal/copy-lineage consumer. |
| `/home/steve/src/llama.cpp-q38-tp1-lane-q8prefetch-wt/build-sycl-aot-bmg-g31` | 449 | Compiled files and their internal symlinks only. Explicit negative closeout: `experiments/qwen38-27b-b70/notes/2026-08-23-qwen38-q4km-tp1-second-queue-closure.md`. Primary source, all JSON/JSONL, notes and metadata stay. |
| `/home/steve/src/llama.cpp-q38-tp1-lane-ctrl-wt/build-sycl-aot-bmg-g31` | 439 | Compiled files and their internal symlinks only. Explicit negative closeout: `experiments/qwen38-27b-b70/notes/2026-08-23-qwen38-q4km-tp1-second-queue-closure.md`. Primary source, all JSON/JSONL, notes and metadata stay. |
| `/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31-vdr4` | 411 | Compiled files and their internal symlinks only. Explicit negative closeout: `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T1021-q8-mmvq-vdr4-negative.md`. Primary source, all JSON/JSONL, notes and metadata stay. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet127-head-retune` (`packet127-head-retune-builds-revised`) | 48 | Explicit CLOSED in ops/screen-cleanup/closed.json; no protected/live packet consumes build paths or pins this packet as parent; external hits are closed screen history, audit/notes, and historical queue proposals; both active queues empty. Restore archive before any historical rebuild/replay. Every symlink ancestor excluded. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet129-draft-acceptance` (`packet129-draft-acceptance-builds-revised`) | 1557 | Explicit CLOSED in ops/screen-cleanup/closed.json; no protected/live packet consumes build paths or pins this packet as parent; external hits are closed screen history, audit/notes, and historical queue proposals; both active queues empty. Restore archive before any historical rebuild/replay. Every symlink ancestor excluded. |
| `/home/steve/src/laguna-xpu-kernels-attention-gate-m12-20260731` (`dependency-git-laguna-xpu-kernels-attention-gate-m12-20260731-private-dependency-git`) | 56 | Private downloaded build dependency Git histories under explicitly closed source roots. No external alternates/worktree/symlink/live references; primary source Git histories stay. |
| `/home/steve/src/laguna-xpu-kernels-wide-prefill-qknorm-rope-20260802` (`dependency-git-laguna-xpu-kernels-wide-prefill-qknorm-rope-20260802-private-dependency-git`) | 56 | Private downloaded build dependency Git histories under explicitly closed source roots. No external alternates/worktree/symlink/live references; primary source Git histories stay. |
| `/home/steve/src/deepseek-v4-xpu-kernels-m2-event-chain` (`dependency-git-deepseek-v4-xpu-kernels-m2-event-chain-private-dependency-git`) | 56 | Private downloaded build dependency Git histories under explicitly closed source roots. No external alternates/worktree/symlink/live references; primary source Git histories stay. |
| `/home/steve/src/laguna-xpu-kernels-paired-attn-20260731` (`small-laguna-xpu-kernels-paired-attn-20260731`) | 66 | Closed rejected component compiled outputs, detailed closure references in small-audit.md. |
| `/home/steve/src/laguna-xpu-kernels-transposed-scale-prefetch-20260731` (`small-laguna-xpu-kernels-transposed-scale-prefetch-20260731`) | 27 | Closed rejected component compiled outputs, detailed closure references in small-audit.md. |
| `/home/steve/src/laguna-xpu-kernels-m12-hybrid-nchunk-20260801` (`small-laguna-xpu-kernels-m12-hybrid-nchunk-20260801`) | 28 | Closed rejected component compiled outputs, detailed closure references in small-audit.md. |
| `/home/steve/src/laguna-xpu-kernels-m12-packed-nmajor-20260801` (`small-laguna-xpu-kernels-m12-packed-nmajor-20260801`) | 28 | Closed rejected component compiled outputs, detailed closure references in small-audit.md. |
| `/home/steve/src/laguna-xpu-kernels-m12-kloop-barrier-20260801` (`small-laguna-xpu-kernels-m12-kloop-barrier-20260801`) | 28 | Closed rejected component compiled outputs, detailed closure references in small-audit.md. |
| `/home/steve/src/laguna-xpu-kernels-scale-lane-dedup-20260801` (`small-laguna-xpu-kernels-scale-lane-dedup-20260801`) | 1 | Closed rejected component compiled outputs, detailed closure references in small-audit.md. |

The archive guard rejected the initial packet127 list before creating an archive or removing any file: two entries were reached through `oracle/build`, a symlink to retained packet49 oracle material. Those aliases stay. The revised list above contains only literal local build paths. Three proposed Gemma builds also resolve through a source-parent symlink into protected `/mnt/fast-ai`; they were rejected before any movement. This pass never removes through symlink ancestors.

### Additional disk6 candidates, recorded before movement

| Exact root / archive label | Selected paths | Closure / decision |
| --- | ---: | --- |
| `/var/tmp/qwen38-cache-recovery.2m1KYi` (`qwen38-cache-recovery.2m1KYi`) | 2010 | August23 diagnostic compiler cache closed by incident/recovery closeout or d1d2-v2b mechanism closure; only historical note/closure references; AOT model files are compiled runtime cache artifacts described by the closure, not publisher model weights. All source, JSON/JSONL and notes retained; no credentials or model weights; restore exact cache before historical diagnostic replay. |
| `/var/tmp/qwen38-chunkdiag-d1d2-v2-cache-20260823` (`qwen38-chunkdiag-d1d2-v2-cache-20260823`) | 2006 | August23 diagnostic compiler cache closed by incident/recovery closeout or d1d2-v2b mechanism closure; only historical note/closure references; AOT model files are compiled runtime cache artifacts described by the closure, not publisher model weights. All source, JSON/JSONL and notes retained; no credentials or model weights; restore exact cache before historical diagnostic replay. |
| `/home/steve/src/llama.cpp-latest-gemma/build-vulkan-b70` (`llama-extra-1`) | 2883 | Explicitly closed negative build; experiments/gemma4-26b-a4b-q8-b70/sweeps/20260624T0214-vulkan-backend-smoke.md. ELF, ar, LLVM bitcode, SPIR-V compiled files plus internal library symlinks; all source/metadata/notes/JSON remains |
| `/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31-q8hoist` (`llama-extra-2`) | 411 | Explicitly closed negative build; experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T1059-clean-repro-threshold-q8hoist.md. ELF, ar, LLVM bitcode, SPIR-V compiled files plus internal library symlinks; all source/metadata/notes/JSON remains |
| `/home/steve/src/llama.cpp-dflash-gemma4/build-sycl-b70-dflash-pr22105` (`llama-extra-3`) | 403 | Explicitly closed negative build; experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0245-crack100-runtime-sweeps.md. ELF, ar, LLVM bitcode, SPIR-V compiled files plus internal library symlinks; all source/metadata/notes/JSON remains |
| `/home/steve/src/llama.cpp-q38-tp1-lane-q8prefetch-wt/build-sycl-aot-bmg-g31` (`llama-generated-1`) | 2859 | Explicitly closed negative build; experiments/qwen38-27b-b70/notes/2026-08-23-qwen38-q4km-tp1-second-queue-closure.md. remaining untracked generated build outputs only; exclude prior compiled list, JSON/JSONL/notes/licenses and symlinks; root canonical; no external hardlinks |
| `/home/steve/src/llama.cpp-q38-tp1-lane-ctrl-wt/build-sycl-aot-bmg-g31` (`llama-generated-2`) | 2833 | Explicitly closed negative build; experiments/qwen38-27b-b70/notes/2026-08-23-qwen38-q4km-tp1-second-queue-closure.md. remaining untracked generated build outputs only; exclude prior compiled list, JSON/JSONL/notes/licenses and symlinks; root canonical; no external hardlinks |
| `/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31-vdr4` (`llama-generated-3`) | 864 | Explicitly closed negative build; experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T1021-q8-mmvq-vdr4-negative.md. remaining untracked generated build outputs only; exclude prior compiled list, JSON/JSONL/notes/licenses and symlinks; root canonical; no external hardlinks |
| `/home/steve/src/llama.cpp-latest-gemma/build-vulkan-b70` (`llama-generated-4`) | 2363 | Explicitly closed negative build; experiments/gemma4-26b-a4b-q8-b70/sweeps/20260624T0214-vulkan-backend-smoke.md. remaining untracked generated build outputs only; exclude prior compiled list, JSON/JSONL/notes/licenses and symlinks; root canonical; no external hardlinks |
| `/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31-q8hoist` (`llama-generated-5`) | 864 | Explicitly closed negative build; experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T1059-clean-repro-threshold-q8hoist.md. remaining untracked generated build outputs only; exclude prior compiled list, JSON/JSONL/notes/licenses and symlinks; root canonical; no external hardlinks |
| `/home/steve/src/llama.cpp-dflash-gemma4/build-sycl-b70-dflash-pr22105` (`llama-generated-6`) | 849 | Explicitly closed negative build; experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0245-crack100-runtime-sweeps.md. remaining untracked generated build outputs only; exclude prior compiled list, JSON/JSONL/notes/licenses and symlinks; root canonical; no external hardlinks |
| `/home/steve/.local/share/Trash/files/.source-replay.K12J09` (`trash-source-replay-K12J09`) | 6298 | Exact temporary source replay explicitly moved to Trash on 2026-08-27T20:49:20 from /mnt/fast-ai/qwen38-runtime-publication/.source-replay.K12J09, recorded by retained .trashinfo. Whole repo including ignored plus own-runtime-results finds zero exact or source-replay-prefix references. Preserve existing source clone bytes in archive, keep notes/JSON/configs. This is retired scratch source, not a working tree or active runtime. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet112-route-select` (`generated-packet112-route-select-generated`) | 2 | Generated/copied source inside exactly named closed build roots; mirrors produced by kernel_gate.mirror/build_engine or narrow micro generators. No live exact-path pins; all JSON/JSONL/notes/tracked/dirty and primary sources remain; restore before closed rebuild. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet113-gdn-row` (`generated-packet113-gdn-row-generated`) | 199 | Generated/copied source inside exactly named closed build roots; mirrors produced by kernel_gate.mirror/build_engine or narrow micro generators. No live exact-path pins; all JSON/JSONL/notes/tracked/dirty and primary sources remain; restore before closed rebuild. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet115-large-grf` (`generated-packet115-large-grf-generated`) | 80 | Generated/copied source inside exactly named closed build roots; mirrors produced by kernel_gate.mirror/build_engine or narrow micro generators. No live exact-path pins; all JSON/JSONL/notes/tracked/dirty and primary sources remain; restore before closed rebuild. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet116-qsa-schedule` (`generated-packet116-qsa-schedule-generated`) | 5 | Generated/copied source inside exactly named closed build roots; mirrors produced by kernel_gate.mirror/build_engine or narrow micro generators. No live exact-path pins; all JSON/JSONL/notes/tracked/dirty and primary sources remain; restore before closed rebuild. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet120-placement` (`generated-packet120-placement-generated`) | 214 | Generated/copied source inside exactly named closed build roots; mirrors produced by kernel_gate.mirror/build_engine or narrow micro generators. No live exact-path pins; all JSON/JSONL/notes/tracked/dirty and primary sources remain; restore before closed rebuild. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet121-miss-table` (`generated-packet121-miss-table-generated`) | 213 | Generated/copied source inside exactly named closed build roots; mirrors produced by kernel_gate.mirror/build_engine or narrow micro generators. No live exact-path pins; all JSON/JSONL/notes/tracked/dirty and primary sources remain; restore before closed rebuild. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet122-draft-hc` (`generated-packet122-draft-hc-generated`) | 216 | Generated/copied source inside exactly named closed build roots; mirrors produced by kernel_gate.mirror/build_engine or narrow micro generators. No live exact-path pins; all JSON/JSONL/notes/tracked/dirty and primary sources remain; restore before closed rebuild. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet125-miss-transfer` (`generated-packet125-miss-transfer-generated`) | 50 | Generated/copied source inside exactly named closed build roots; mirrors produced by kernel_gate.mirror/build_engine or narrow micro generators. No live exact-path pins; all JSON/JSONL/notes/tracked/dirty and primary sources remain; restore before closed rebuild. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet127-head-retune` (`generated-packet127-head-retune-generated`) | 216 | Generated/copied source inside exactly named closed build roots; mirrors produced by kernel_gate.mirror/build_engine or narrow micro generators. No live exact-path pins; all JSON/JSONL/notes/tracked/dirty and primary sources remain; restore before closed rebuild. |
| `/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet129-draft-acceptance` (`generated-packet129-draft-acceptance-generated`) | 211 | Generated/copied source inside exactly named closed build roots; mirrors produced by kernel_gate.mirror/build_engine or narrow micro generators. No live exact-path pins; all JSON/JSONL/notes/tracked/dirty and primary sources remain; restore before closed rebuild. |
| `/home/steve/src/atomic-llama-cpp-turboquant/build-sycl-l0-server` (`atomic-atomic-llama-cpp-turboquant-closed-build`) | 656 | Rejected June23 Atomic fork experiment; only untracked build outputs. See last-audit.md exact closure and current references. |
| `/home/steve/src/atomic-llama-cpp-gemma-mtp/build-sycl-b70-gemma-mtp` (`atomic-atomic-llama-cpp-gemma-mtp-closed-build`) | 483 | Rejected June23 Atomic fork experiment; only untracked build outputs. See last-audit.md exact closure and current references. |

### disk6 outcome — target reached; removals stopped

At **2026-10-18T14:26:13.477325+00:00**, root reached **40,022,736,896 available bytes = 40.023 GB (37.274 GiB)**, up from **31,284,891,648 bytes = 31.285 GB**. The first passing reading created `target-reached.json`; no original-data removal followed. This is a point-in-time threshold, not reserved space against the running record chain.

**9,581,117,440 allocated file bytes (9.581 GB) reclaimed**, with directory blocks excluded and inode accounting deduplicated. The difference from the smaller net free-space gain is concurrent filesystem activity. **58 archives**, **65,375 regular-file paths**, **12 hard-link members**, and **86 symlink members** were fully verified before exact unlink. All archive hashes, manifests and removal receipts remain beside the archives. Total compressed payload archive size: **3,137,288,630 bytes**.

Every archive below is under **`/mnt/raid-models/own-xpu-runtime-archive/disk6-20261018/`**. For each `<name>.tar.gz`, adjacent `<name>.manifest.json`, `<name>.manifest.sha256`, `<name>.tar.gz.sha256` and `<name>.receipt.json` identify the original root, exact payload paths, kept identities, closure, content hashes and verification.

| Archive filename under the absolute base above | File/link paths | Reclaimed allocated bytes | Archive bytes | Root available after exact removal | Archive SHA-256 |
| --- | ---: | ---: | ---: | ---: | --- |
| `poison-closed-build.tar.gz` | 821 | 552,607,744 | 147,743,287 | 31,581,626,368 | `ec31421fe4935c019e82336ffc8524876d76da226a53a09d4cb0a697c4ae41d0` |
| `laguna-onednn-closed-build.tar.gz` | 714 | 200,298,496 | 58,733,544 | 31,781,195,776 | `3867fc5546321cd3f2e56137b3d8d24a5724f8a3ae811292200675f261656df6` |
| `laguna-dedup-closed-build.tar.gz` | 40 | 146,550,784 | 29,658,904 | 31,927,656,448 | `f995e342b044fde39969e4e551f7d7dcd8bd134fedb8da5c886359c70ccc5325` |
| `laguna-scheduler-closed-build.tar.gz` | 37 | 95,834,112 | 19,862,777 | 32,023,478,272 | `231a20fd66df535ca45dcd8fea21c08c0e48a269ed1cc2e1527bd9886d6ac3be` |
| `screen-p120-B-grid-0-production.tar.gz` | 47 | 36,024,320 | 18,111,445 | 32,059,174,912 | `7246738881ba9d03eb85149eccedf69eec68c5572cdb9c9ee6ae840a8e51de4b` |
| `screen-p120-B-grid-1-25-23.tar.gz` | 47 | 36,024,320 | 18,111,184 | 32,095,174,656 | `c8271ff8029e693e416e051ebd0a906cddead7606323e4b5fa219ff9e67ea0d9` |
| `closed-laguna-xpu-kernels-attention-gate-m12-20260731.tar.gz` | 9,923 | 608,780,288 | 140,605,984 | 32,653,004,800 | `691bab113d731b555f7b985adf1057c296ec840466c4489abc182a3d903b19fe` |
| `closed-laguna-xpu-kernels-wide-prefill-qknorm-rope-20260802.tar.gz` | 9,908 | 343,691,264 | 75,052,485 | 32,990,851,072 | `4b69edc46091c767e75def33c11baa91eb6bc4ea20b4284dd52014fdbc6c2dbb` |
| `closed-laguna-xpu-kernels-rank-sum-rmsnorm-20260731.tar.gz` | 53 | 352,923,648 | 80,830,200 | 33,338,486,784 | `88364ed16429e2923e13fb4a0e19cec11419a90ebfb5b967670f3f4365f2dba0` |
| `closed-deepseek-v4-xpu-kernels-m2-event-chain.tar.gz` | 10,610 | 576,778,240 | 157,545,864 | 33,872,519,168 | `1d9d901d453a6abfa74cdcca0aa35b35f43783902db26281723d9950ad976550` |
| `packet112-route-select-builds.tar.gz` | 14 | 10,285,056 | 2,923,631 | 33,671,655,424 | `97b595da07fd9273d649ef1d68c69ac9745589c1cdfd2b061d0988ace40f1b05` |
| `packet113-gdn-row-builds.tar.gz` | 19 | 39,981,056 | 10,912,680 | 33,926,897,664 | `eac750971fd2cd969091062ce6db0bbcc9692c163a2518f9023c736720b4038e` |
| `closed-laguna-xpu-kernels-exact-specialized-20260731.tar.gz` | 1,346 | 380,362,752 | 88,843,220 | 34,307,047,424 | `772a6372027e2d6f21b1a51bf8900c83eae916303c321e05828d6862efcf8dea` |
| `packet115-large-grf-builds.tar.gz` | 186 | 107,655,168 | 27,008,668 | 34,286,755,840 | `2e3971dd4dbc8176cf405b43ee323f2536f91402be4fffdcf08977fd408351a7` |
| `packet116-qsa-schedule-builds.tar.gz` | 64 | 121,393,152 | 33,293,365 | 34,527,633,408 | `592943676d16be78f523d2e6310664f86d11ae4d296cd9a6e7dbe4a6e6f54ece` |
| `packet120-placement-builds.tar.gz` | 68 | 104,378,368 | 28,202,341 | 34,504,060,928 | `9b1edd91ca30b4b5f6379f62940455c6b71462f1610528bbe8dc76b49daedafe` |
| `packet121-miss-table-builds.tar.gz` | 1,026 | 167,231,488 | 47,312,551 | 34,789,486,592 | `f84ae74b29e652663964f8988b23910c668b328e1207f2d75b54cd321c764738` |
| `packet122-draft-budget-builds.tar.gz` | 1 | 135,168 | 90,514 | 34,789,105,664 | `0207418bdeb8fd44909b17e9995f7c1b165aad9f4a5ffac5505803228f782a0a` |
| `packet122-draft-hc-builds.tar.gz` | 33 | 98,996,224 | 26,782,047 | 34,869,354,496 | `23a35fdeadc5ee3337ca854e983a143c2f0c0720d723f9cc55867ee68fedafbd` |
| `packet125-miss-transfer-builds.tar.gz` | 66 | 12,574,720 | 2,521,844 | 34,858,835,968 | `b39097e56a28069a18545b4219f20710cda469d0ee53e44077cc32c90be62a3e` |
| `llama-closed-build-1.tar.gz` | 449 | 509,448,192 | 115,633,129 | 35,329,568,768 | `32823f8abd5e5b9f9bcde67c06028afe1ea0c620acf5afe99642cafc214ccaac` |
| `llama-closed-build-2.tar.gz` | 439 | 505,839,616 | 114,291,041 | 35,834,310,656 | `4a4b56bb5063cf0b992564ca1824483e74f3bf937b9cb4ef7810b9cc4decf8f2` |
| `llama-closed-build-3.tar.gz` | 411 | 313,909,248 | 76,480,251 | 36,147,699,712 | `d184f254c7d0c1744b5ae8c22cf13baed41f2b153bd8ad6683a71eaa16bf48ea` |
| `packet127-head-retune-builds-revised.tar.gz` | 48 | 87,568,384 | 24,198,703 | 36,203,114,496 | `1d36ab841f1a5d4d6f0cd6accd2e3037fae65a730de582471b211e0782b046aa` |
| `packet129-draft-acceptance-builds-revised.tar.gz` | 1,557 | 95,133,696 | 23,375,366 | 36,328,071,168 | `fbf3f99d22947837347897a40486df93e6f5fc1dc7f150dc63d0ceeb6aa6192a` |
| `dependency-git-laguna-xpu-kernels-attention-gate-m12-20260731-private-dependency-git.tar.gz` | 56 | 334,880,768 | 329,114,212 | 36,624,576,512 | `cef6e42f18a600152d91e4b2bd17ac9ef52aa97bd0cae35e85ffe9e32f1769d7` |
| `dependency-git-laguna-xpu-kernels-wide-prefill-qknorm-rope-20260802-private-dependency-git.tar.gz` | 56 | 334,426,112 | 328,655,152 | 36,954,865,664 | `dbb401ee42609123687badce611bbd349cd2e33973381c53a0dcde326995e086` |
| `dependency-git-deepseek-v4-xpu-kernels-m2-event-chain-private-dependency-git.tar.gz` | 56 | 318,554,112 | 312,797,349 | 37,270,896,640 | `e2d1417b971de8bbd0857be7a8b5aa10af6e6131545ad3b5bc5780dc0fd69039` |
| `small-laguna-xpu-kernels-paired-attn-20260731.tar.gz` | 66 | 35,196,928 | 7,450,515 | 37,306,019,840 | `9811909e1ad45ba0c878099ba1c8e3d2fa42ff7ffeb71ec23512df8eddecae50` |
| `small-laguna-xpu-kernels-transposed-scale-prefetch-20260731.tar.gz` | 27 | 34,283,520 | 8,101,106 | 37,340,180,480 | `99cbc43622770331ed3722da50462cc5680db4590696a92bc9535d95805ca6ed` |
| `small-laguna-xpu-kernels-m12-hybrid-nchunk-20260801.tar.gz` | 28 | 33,652,736 | 8,087,627 | 37,373,763,584 | `cd1f776debea81e14bd04faf07a71f9a775c2884e3fb2951a8fd5fcac587e232` |
| `small-laguna-xpu-kernels-m12-packed-nmajor-20260801.tar.gz` | 28 | 33,628,160 | 8,085,135 | 37,407,326,208 | `57196aecb773567a30df2df6d2ec019babdd838d45819b749bcdaab19d8615fc` |
| `small-laguna-xpu-kernels-m12-kloop-barrier-20260801.tar.gz` | 28 | 33,513,472 | 8,067,933 | 37,440,778,240 | `1a7aaf187b49f860a1c6ade01538a1b4a198182f520f744f8008582e8ad54cb7` |
| `small-laguna-xpu-kernels-scale-lane-dedup-20260801.tar.gz` | 1 | 51,511,296 | 9,931,731 | 37,492,187,136 | `9462b9ba9b83ffafecff50efac511e7ca6694150bef7ca292953c2331b81e96a` |
| `qwen38-cache-recovery.2m1KYi.tar.gz` | 2,010 | 421,146,624 | 72,799,814 | 37,750,816,768 | `82b5a9d17bec97d4773e6452dceeba481962af682d1d5b48e3f028d9ec9379dc` |
| `qwen38-chunkdiag-d1d2-v2-cache-20260823.tar.gz` | 2,006 | 370,397,184 | 68,289,557 | 37,860,220,928 | `8cbd6e89337ea2d44571debdc5e90ded29c8b1a24cd5a167d5fad51b2a24b8c7` |
| `llama-extra-1.tar.gz` | 2,883 | 261,865,472 | 90,116,109 | 38,194,065,408 | `119e8aa158f2c14786528729e1c21257b40a967afe705b76f569d8194f0f4661` |
| `llama-extra-2.tar.gz` | 411 | 314,077,184 | 76,512,204 | 38,617,219,072 | `2b9c1aed402dd10e3d616714f84a079fefaafddecadef8dca42b70eaae6332d1` |
| `llama-extra-3.tar.gz` | 403 | 182,005,760 | 50,794,127 | 38,514,368,512 | `4a3aef918b4a7f36d0754097f0d261d445acfe9407e7303d71f83a4bae54b159` |
| `llama-generated-1.tar.gz` | 2,859 | 80,416,768 | 21,369,931 | 38,848,864,256 | `5ea0fdcc194cc16517fc032397049c8cb248b889275307bc4868fff5b7b2ddb9` |
| `llama-generated-2.tar.gz` | 2,833 | 61,976,576 | 19,562,637 | 38,913,433,600 | `db0eb79d60c1e70329f408c7ec65f09dcbbe5fd5a201d63b10c3ad3c06d5c14d` |
| `llama-generated-3.tar.gz` | 864 | 36,691,968 | 15,331,133 | 38,937,653,248 | `b21964cc3384b23ecd246cef5ebe453e82ac2ba712335e713241354fd9d886f3` |
| `llama-generated-4.tar.gz` | 2,363 | 314,556,416 | 61,244,147 | 39,263,985,664 | `7851401b8c70f7949cb24896759bbe95d5f3bef5c2c23e777c35caed8ab00e00` |
| `llama-generated-5.tar.gz` | 864 | 36,683,776 | 15,330,399 | 39,300,587,520 | `e1bff82add8ec66a1fb43e258dfaec4688a073de8803c76e0cc4382838f96615` |
| `llama-generated-6.tar.gz` | 849 | 36,569,088 | 15,324,403 | 39,337,017,344 | `dbd5d7e1c7959408690738bcfac41d5a5be9fb0178bd64ac79a57905a18986ea` |
| `trash-source-replay-K12J09.tar.gz` | 6,298 | 166,064,128 | 91,234,644 | 39,497,449,472 | `a43a450c03dfe9ac6b1076ec877fd8f32302ff33c7ba96441454511051c4e570` |
| `generated-packet112-route-select-generated.tar.gz` | 2 | 20,480 | 10,687 | 39,449,980,928 | `736be0fb83f62151af402d704cf4567fd08c19251bbb4c5e7cdc935d44f8046b` |
| `generated-packet113-gdn-row-generated.tar.gz` | 199 | 14,479,360 | 3,232,735 | 39,463,698,432 | `9eaef5ab57beb1261a23afbfc20aa8c66259bc9de7d7cfbab88aede58d3da8bf` |
| `generated-packet115-large-grf-generated.tar.gz` | 80 | 753,664 | 209,751 | 39,463,874,560 | `875c0aa6ddd0288dd20bff9bdac26da7acba327ecf187bd1248c334696adab47` |
| `generated-packet116-qsa-schedule-generated.tar.gz` | 5 | 200,704 | 79,325 | 39,463,952,384 | `b8593231ffe09ffd2cc430eff4c6b332cc79bdd47f7d8f9dc28e0ef6c57ed712` |
| `generated-packet120-placement-generated.tar.gz` | 214 | 27,422,720 | 6,093,911 | 39,491,198,976 | `f6b79e77e868ca46344681f612a1698dd6695e5291423264ed6a72187a26a81c` |
| `generated-packet121-miss-table-generated.tar.gz` | 213 | 27,320,320 | 6,029,775 | 39,517,048,832 | `180f5cebf4deb9f0fdb24d6c88ac2a69e42f63beaf358ffae4edcebceaddf69f` |
| `generated-packet122-draft-hc-generated.tar.gz` | 216 | 27,336,704 | 6,027,930 | 39,544,287,232 | `38d15f1493da80328b26654da2091faab4bbc012185c4ad5e2165de441e9807f` |
| `generated-packet125-miss-transfer-generated.tar.gz` | 50 | 397,312 | 107,274 | 39,544,623,104 | `efe5ec106d90dc816107ce1b6cf70a4da1c489e0e2de6d29e24215f67c70c750` |
| `generated-packet127-head-retune-generated.tar.gz` | 216 | 27,443,200 | 6,096,399 | 39,570,853,888 | `95fe2a0993f7e25105e53290d37fed117ebc6ef0cfaf1ab9cfd1ecded21e1076` |
| `generated-packet129-draft-acceptance-generated.tar.gz` | 211 | 14,856,192 | 3,388,530 | 39,585,665,024 | `bee1086428b85aa9780e3219ebd9a1c01133df8cd21d661a25c5afc7d7b7ca5c` |
| `atomic-atomic-llama-cpp-turboquant-closed-build.tar.gz` | 656 | 209,821,696 | 63,421,401 | 39,793,401,856 | `9e8db8d19093e0c7da61023dd5d8dd4ebcdc7b528c0a05bdd8adeb701d0b80d8` |
| `atomic-atomic-llama-cpp-gemma-mtp-closed-build.tar.gz` | 483 | 234,561,536 | 56,266,022 | 40,022,736,896 | `c98f96d79f78b8ba028841dd9ac30aa3773660df0e38820198cf997f8693410e` |

Restore by first verifying the adjacent archive SHA-256, then extracting only `payload/` into a scratch directory using GNU tar without dereferencing links. Members are `payload/<original-root-basename>/<relative-path>`. Verify extracted regular-file hashes and symlink targets against the embedded `.disk6/manifest.json`, then restore the selected paths under the manifest's exact original root, preserving retained files. GNU tar recreates archived hard links. If a link target was already present and kept on root, preserve it; later dependency-history/generated-output supplements may contain paths listed as kept by an earlier archive. The final kept list subtracts all later completed removals. Restore all required supplements before replaying historical build or diagnostic commands. Source directories remain in place; no recursive source deletion was used.

Kept entirely: the protected live packets and their pinned parents, record chains/submissions, all model weights, system/toolchain/venv/swap/agent/credential paths. Packet107/108/117/119/58k builds remain because of downstream references or pinned ancestry; packet58m directly pins the 58k binaries. The packet127 shared oracle alias remains. Failed/unfinished packet120 trailing screen and packet127 screen bulk remain. Unreadable root-owned current-main Qwen caches stay. Promoted or unresolved old source builds stay, including Community PR14, graph-port, and sources reached through protected `/mnt/fast-ai` aliases. All JSON/JSONL and notes under selected roots remain. No queue, service, GPU, host setting or unrelated tracked file was changed by disk6.

The pre-movement full-depth survey produced 71 permission/disappearance diagnostics (exit 1), retained in `audit/root-du.errors`; this no-sudo survey does not claim unreadable paths were inspected. Whole-repository searches had 68 unrelated old Qwen cache/STOP access errors; no inaccessible own-runtime/ops reference file was reported. Each process scan records its accessible and inaccessible PIDs. The audit records limits explicitly.

Final verification at **2026-10-18T14:27:09.510440+00:00** passed: all **58 archive hashes** and embedded manifests match; all **65,461 selected paths** are absent; all **16,171 final retained files/links**, including **5,578 JSON/JSONL files**, match their saved hashes/targets. The final kept list correctly subtracts **12,206** entries archived in later supplements. Zero errors. Root then had **39,874,531,328 bytes (39.875 GB)** free: the chain had used some space since the first passing reading. Per the brief, removal was not resumed after reaching the threshold.

Audit archive: **`/mnt/raid-models/own-xpu-runtime-archive/disk6-20261018/audit.tar.gz`**, **18,565,684 bytes**, SHA-256 **`d2a7a6e9c73da2a61f26960a979ff383e38a78976bf95b72e6ff3223d0d91df5`**. All **540 audit payload files** plus the embedded manifest were fully read and hash-verified; audit originals remain on RAID. Adjacent `audit.manifest.json`, `audit.tar.gz.sha256` and `audit-receipt.json` preserve independent checks. This contains the full root survey, candidate/reference/link/process audits, exact plans, verification/removal scripts, failed-guard evidence, per-stage checks and final retained/removed lists.

Documentation validation: `git diff --check -- CURRENT.md experiments/own-xpu-runtime/stage2/DISK-CLEANUP-20261018.md` passed. Only those two files are committed using `git commit --only -- <paths>`, preserving unrelated orchestration edits. At 2026-10-18T14:29:11.266672+00:00, root has **39,968,440,320 available bytes (39.968 GB)**. No cleanup resumed after the first passing threshold.
