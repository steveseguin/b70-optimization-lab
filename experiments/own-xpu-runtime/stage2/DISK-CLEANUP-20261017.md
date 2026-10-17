# Disk cleanup, 2026-10-17 about 04:20 UTC

Packet 49's K2 window refused at storage admission. Root had 21.37 GB free; the packet keeps an 8 GB floor plus a full-chain reserve, which capped the build budget at 3.85 GB. K2 needs 2.5 GB on top of 1.96 GB already used.

Following the 2026-10-12 cleanup rules (ignored, regenerable build output in finished packets only; nothing tracked; no receipts), the coordinator removed:

- `packet45-merged3/build/asan/` (1.35 GB): the sanitizer build. Packet 45 is closed at the 39.422 record, and its receipts are tracked under `data/own-xpu-runtime-packet45-device-rounds-20261014/`.
- `packet44-context/build/asan/` (0.72 GB): the sanitizer build of the closed packet 44.

No packet-49 seal or source references either directory, checked with grep. Window result trees, sealed reference tables and the only copies of untracked trees were not touched.

## 07:05 UTC: packet 49c model-phase admission

Packet 49c's both-chain pre-check missed by 22.8 MB: it still reserves 5.8 GB for the stopped 49b model phase.

`packet24-kernels/build/k1{a,b}-c0/run/nongemv/kernel-output.bin` (239 MB each) has no hash in its receipt, so it may be the only copy. Each file was therefore **gzip-compressed in place, not deleted**: 239 → 82 MB each. A round-trip SHA256 check passed, and the originals' SHA256 values and sizes are recorded in `packet24-kernels/build/kernel-output-gzip-manifest-20261017.json`. 314 MB freed.

## 08:58 UTC: packet 49c model-phase requeue

Packet 49c's model queue was paused with its STOP file so packet 52 could use card 0 while the CPU oracle finished. When the queue was requeued, its both-chain pre-check missed by 40.7 MB. The cause was packet 52's evidence and the Codex job writes; the 5.8 GB reserve for the stopped 49b model phase still applies.

Sanitizer **run** outputs of the closed packets 18, 22 and 23 (25 `build/sanitizer-*` directories; untracked, and not referenced by packets 45/49/49b/49c/52) were **archived, not discarded**. Each packet's directories went into one `build/sanitizer-archive-20261017.tar.gz`. Every member's SHA256 and size was verified to round-trip before the directories were removed.

| Packet | Files | Before | After |
|---|---:|---:|---:|
| 18 | 2,739 | 57.9 MB | 11.5 MB |
| 22 | 1,970 | 45.6 MB | 11.1 MB |
| 23 | 13,998 | 205.6 MB | 15.6 MB |

The per-file manifest is `sanitizer-archive-manifest-20261017.json`. Afterwards the pre-check passed with a 287 MB margin, and the queue was requeued as unit `p49c-model-cards01-d`.
