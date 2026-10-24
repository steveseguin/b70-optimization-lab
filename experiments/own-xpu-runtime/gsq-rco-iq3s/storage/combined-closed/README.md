# Closed combined-run state archive

This fixed adapter covers only the independently audited
`gsq-attention-qkv-p33-a` run: initial capture, two warmups and 24 measured
arms. It requires the exact independent review, compressed raw-file index and
positive terminal record. No other run or caller-supplied source path is accepted.

There are 27 groups of 2,113 `.bin` files and 231,442,500 bytes each:
57,051 files / 6,248,947,500 bytes total. Each complete group includes its
target-state buffers and five draft-state files. All JSON, source, logs,
directories, failure metadata and unindexed files remain at their original
paths. No model files, profile inputs or older retained fixtures are eligible.

The adapter uses the unchanged, hash-pinned
[filesystem Job](../closed_baseline_bins.py). Only its explicit quota argument
changes to 256 MiB, as in the reviewed
[finish policy](../attention-closed/finish_256.py). Raw payload plus the same
conservative container allowance is 249,800,772 bytes, below 268,435,456 bytes.
Admission requires the full quota above the unchanged 27 GB + 64 MiB floor:
27,335,544,320 free bytes. This remains a live per-write check, not a promise
that current free space will remain sufficient. USB reserve stays 2 GiB.

`closed_combined_bins.py --plan` reads only the small closed review/index and
terminal metadata. It does not read state payloads or create archives. Root
reviews and invokes each phase explicitly under nice19/helper cores:

1. `--archive --batch N`: copy indexed files to an exclusive NVMe archive,
   hashing unchanged held source files; verify every tar member and the complete
   archive SHA before recording success.
2. `--prune-verified --batch N`: reverify the held archive and each unchanged
   source immediately before unlinking. Durable restore metadata precedes unlink.
3. `--offload-verified --batch N`: publish one exclusive USB archive, requiring
   the original source filesystem and a different device from NVMe; fsync and
   complete readback verification precede success.
4. `--release-local-verified --batch N`: reverify the USB archive and filesystem
   identity before removing the local archive. Metadata remains on NVMe.

The next batch requires the preceding batch's verified local-release record.
Any failure stops progression; there is no automatic retry or phase loop.
Archive anchors are `/home/steve/own-xpu-runtime-results/gsq-attention-qkv-bin-archive-a/chunk-NN`;
remote archives are `/mnt/usb-models/own-xpu-runtime-results/gsq-attention-qkv-state-bins-NN.tar.gz`.

To restore, map tar member names back under the exact combined-run source root
and verify lengths/hashes against the original audited index. The inherited
receipt's historical word “baseline” means this explicitly bound source root;
it does not authorize restoring into the older baseline run. Do not overwrite
existing files without separate review. Retain archive hashes, all phase
receipts, source-stat inventory and restore metadata permanently.

Preparation tests exercise only metadata, mocked quota checks and tiny temporary
directory sequencing. No real state archive, prune, offload or payload read is
performed during preparation.
