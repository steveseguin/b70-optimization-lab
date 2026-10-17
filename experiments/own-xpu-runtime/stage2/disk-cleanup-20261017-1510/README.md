# Closed-packet disk cleanup, 2026-10-17 15:10 UTC

The 10 GB target was **not met**. The file accounting records **8,790,441,984 bytes** reclaimed before the new audit/recovery records and concurrent jobs' writes. Root started with 11,925,147,648 available bytes. See `final-df.txt` for the final filesystem reading; filesystem change is not attributable solely to this job.

## Cleanup error and partial recovery

The original `cleanup.py` sanitizer-prefix selector was too broad. It deleted the previously retained `sanitizer-archive-20261017.tar.gz` files in packet18-decode-v2, packet22-replay and packet23-fast, and packet26-specialised's `sanitizer-mini-1791754628508647534` run outputs plus a few sanitizer logs. Those are evidence, not just compiler scratch. This was a mistake. The script is now disabled, and the owner was told during the work.

The original archive member manifest remains tracked at `../sanitizer-archive-manifest-20261017.json`. A search of this repository, the runtime result tree and `/mnt/fast-ai/bench-results` found no duplicate archives. Matching file sizes and SHA-256 values recovered 14,285 entries: 13,836 original archive members plus 449 directly removed files. The latter were restored to their original paths. **5,067 original member/output files (115,231,465 logical bytes) remain unrecovered**, mostly run-specific receipts and timing logs; the three original archive byte streams are also missing. No replacement measurements or reconstructed historical receipts were invented.

`overbroad-sanitizer-removals.json` lists the exact direct mistakes. `recovery-manifest.json.gz` lists every original archive member and direct removal, its expected SHA-256, matched source when available, and recovery/restoration status. `recovered-bytes.tar.gz` contains the 293 distinct recovered byte blobs, addressed by SHA-256. Every member was verified against its name. This **4,912,508-byte tracked artifact** is intentionally retained as a durable recovery copy; restore it with Python's tarfile or `tar -xzf` into an empty directory and use the recovery manifest to map hashes to original paths. Its SHA-256 is `6cdfa42515a0a17fca3a251e43aeb3e3294d65f3842534a44b6d5ce953a96397`. The original three archives cannot be restored completely from this partial recovery.

## Scope and decisions

CPU-only operations ran with `nice -n 19 taskset -c 8-15,24-31`; Python ran with `-B`. No GPU work, service changes, sudo, host setting changes, process kills, branches or worktrees were used. Main was pulled before work. Other agents' tracked edits and commits were left alone.

The inventory covered the requested closed builds and external result directories. Packet17's `wa-reference`, packet49's oracle, packet49c/49d/56 record chains, all active packet56 variants/57/58/58b/59c/60/screen trees, and device run trees were excluded from mutations. The old packet45 device record trees were also retained. Active and submitted packet path references were scanned; directly pinned files, tracked files, changed files and multiply linked files were excluded. This was a path-reference check, not execution of active seals. Closed CPU build artifacts and fixture scratch were the additional archival targets; no device binaries were run.

Apart from the error above, removals were compiler object files and closed sanitizer compiler output. CPU fixtures, CPU run scratch, compiler cache output and unreferenced CPU ELF binaries were losslessly archived in this folder's local `archives/` directory. Each member's original SHA-256 and size was verified by reading the completed archive before unlinking the original. Fifty-one top-level logs, receipts, source snapshots and lock files caught by the broad archival candidate names were restored byte-for-byte, so they remain at their original paths. Duplicate archives created by this job were consolidated only after every member name, size and SHA-256 matched; manifests now point to the retained archive.

The 10 GB target did not justify touching the protected reference, device evidence or record dependencies. No further candidate outside that boundary was removed.

## Accounting and exact manifests

`summary.json` records allocated-byte totals. After the 449 exact restorations, direct removals account for **4,033,552,384 bytes**; archived originals account for **5,770,936,320 bytes**; the retained local archives occupy **1,014,046,720 bytes**, including archives of the restored top-level files. Reclamation is their difference, **8,790,441,984 bytes**. This includes the mistaken evidence deletions; it is not a claim that all reclaimed bytes were safe compiler scratch. New tracking/recovery metadata and concurrent writes reduce the visible `df` gain.

`removed.jsonl.gz` records every direct removal with exact path, original size, allocated bytes, inode, timestamp and SHA-256. Subtract `restored-originals.json` to get the remaining direct removals. `archive-manifests.json.gz` records every archived file, original and compressed sizes, archive hashes, shared archive mappings and restored originals. `inventory-summary.json` records per-root unique-inode file allocation before cleanup; directory metadata is excluded. The more granular `directory-summary.json` deliberately counts links independently and must not be used to claim reclaimed bytes. The full exploratory inventory remains locally as ignored `inventory.json.gz`.

The local compressed scratch archives are not committed; they are preserved at the absolute paths in the tracked manifests. To restore one safely into a new directory (without running any binary):

```sh
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/stage2/disk-cleanup-20261017-1510/restore.py packet21-fused--fusion-fixtures /path/to/new-empty-destination
```

The restoration tool validates the archive and every original file hash. For deleted compiler output, use the closed packet's retained build.py/CMakeLists.txt and pinned build receipt to rebuild on CPU; never launch a rebuilt device binary or replace an active seal. Historical measurement evidence is not regenerable by rebuilding.

The table below lists exact per-packet source allocations; shared compressed archive sizes are accounted globally above, avoiding double counting.

| Closed packet | Removed files | Removed allocated bytes | Archived files | Original allocated bytes archived |
|---|---:|---:|---:|---:|
| packet10-kopt5 | 11 | 1,310,720 | 27 | 348,160 |
| packet11-kopt6 | 10 | 1,384,448 | 27 | 348,160 |
| packet12-peer | 4 | 331,776 | 0 | 0 |
| packet13-integrate | 22 | 3,416,064 | 4 | 892,928 |
| packet14-tp2 | 46 | 6,533,120 | 8 | 2,306,048 |
| packet15-nongemv | 9 | 913,408 | 221 | 371,507,200 |
| packet16-decode | 0 | 0 | 1 | 782,336 |
| packet17-detmath | 18 | 5,677,056 | 219 | 239,370,240 |
| packet18-decode-v2 | 50 | 21,725,184 | 8 | 2,154,496 |
| packet19-depcheck | 28 | 5,877,760 | 0 | 0 |
| packet20-launch | 8 | 3,371,008 | 0 | 0 |
| packet21-fused | 85 | 16,969,728 | 86 | 216,928,256 |
| packet22-replay | 52 | 19,836,928 | 631 | 13,758,464 |
| packet23-fast | 153 | 50,913,280 | 918 | 365,887,488 |
| packet24-kernels | 92 | 24,227,840 | 89 | 221,065,216 |
| packet26-specialised | 305 | 44,257,280 | 2637 | 382,840,832 |
| packet27-round2 | 102 | 36,765,696 | 94 | 249,495,552 |
| packet28-dense | 0 | 0 | 2 | 3,133,440 |
| packet29-merged | 108 | 41,259,008 | 94 | 252,846,080 |
| packet30-leftovers | 52 | 14,303,232 | 2 | 4,497,408 |
| packet32-pipeline | 108 | 41,406,464 | 94 | 253,095,936 |
| packet33-codegen | 5 | 2,121,728 | 2132 | 432,791,552 |
| packet34-replay-bench | 52 | 19,267,584 | 4 | 6,160,384 |
| packet35-hostpath | 0 | 0 | 97 | 267,485,184 |
| packet36-draft | 0 | 0 | 1896 | 337,563,648 |
| packet37-merged2 | 0 | 0 | 98 | 279,150,592 |
| packet38-integrated | 0 | 0 | 1884 | 367,185,920 |
| packet39-epilogues | 2 | 958,464 | 754 | 242,364,416 |
| packet40-suite | 0 | 0 | 25 | 78,970,880 |
| packet42-codegen2 | 50 | 16,576,512 | 7 | 12,791,808 |
| packet44-context | 0 | 0 | 98 | 328,286,208 |
| packet45-merged3 | 72 | 47,869,952 | 182 | 412,004,352 |
| packet46-specialized | 3 | 3,690,496 | 4 | 16,900,096 |
| packet47-qsa-attn | 0 | 0 | 2 | 303,104 |
| packet48-gemv | 0 | 0 | 3 | 32,768 |
| packet48b-production | 2 | 3,506,176 | 3 | 16,797,696 |
| packet49-integrate | 376 | 1,687,261,184 | 38 | 123,215,872 |
| packet49b-gemv | 394 | 1,903,407,104 | 52 | 136,822,784 |
| packet5-h2d | 10 | 712,704 | 0 | 0 |
| packet51-round2 | 0 | 0 | 4 | 22,298,624 |
| packet52-freeorder | 0 | 0 | 5 | 23,556,096 |
| packet53-expert-order | 1 | 1,572,864 | 7 | 23,875,584 |
| packet53b-virtual | 1 | 2,437,120 | 7 | 24,502,272 |
| packet54-compute | 0 | 0 | 7 | 24,076,288 |
| packet59-fast-draft | 0 | 0 | 2 | 11,149,312 |
| packet6-kopt | 7 | 643,072 | 27 | 348,160 |
| packet7-kopt2 | 9 | 880,640 | 27 | 348,160 |
| packet8-kopt3 | 9 | 1,015,808 | 27 | 348,160 |
| packet9-kopt4 | 10 | 1,150,976 | 27 | 348,160 |
