# Closed baseline state archival preparation

The candidate failed while writing state and failure receipts to the external
NTFS filesystem. Root's subsequent journal investigation reported exhausted MFT
records despite available byte capacity. The [bounded incident review](../attention-q8-p33/operating/evidence/storage-incident-a/review.json)
retains NVMe logs and does not claim clean native success or a completed candidate
qualification. This preparation performs no real archival, pruning or recovery.
Root must review and explicitly execute each phase after storage disposition.

The [helper](closed_baseline_bins.py) accepts no source/output paths. Its only
source is the independently audited, closed `gsq-baseline-a` external run. The
immutable [audit index](../baseline/evidence/independent-a/artifact-index.jsonl.gz)
and [review](../baseline/evidence/independent-a/review.json) identify exactly
57,051 regular `.bin` files, 6,248,947,500 bytes. All JSON, logs, source, directories,
and the active/failed candidate stay outside deletion scope. No model weights,
RAID data, caches, devices, services or host settings are accessed.

There are 27 fixed batches, each with 2,113 files and 231,442,500 raw bytes:
initial rank0/rank1 state together, two warmups, then the original ordered 24
measured arms. Batch selection partitions the audited list exactly. Six files in
prompt00 target-only remain at their original paths even after archival:

- rank0 `blk.0.gdn.gated.bin`, `blk.0.attention.bin`, `blk.23.qsa.y.bin`, and `blk.23.attention.bin`;
- rank1 `blk.47.qsa.y.bin` and `blk.47.attention.bin`.

These total 52,224 bytes and are the requested micro inputs and corresponding
outputs. They have not been copied elsewhere by this helper's preparation.

Each batch requires four explicit phases; there is no automatic chain or retry:

1. `--archive --batch N` creates an exclusive NVMe chunk directory under
   `/home/steve/own-xpu-runtime-results/gsq-baseline-bin-archive-a`. Streaming
   gzip level 3/tar and source-stat metadata share a 384 MiB compressed-write
   quota. Admission reserves that whole quota above a 27 GB + 64 MiB free-space
   floor. Copying verifies each file's audited SHA, extent, regular/no-hardlink
   status, and stable fstat. Every tar member is then read back and checked
   against the complete selected index, followed by the full archive SHA.
   Files and directories are fsynced before the copy receipt succeeds.
2. `--prune-verified --batch N` independently re-verifies the full held archive,
   its inode/stat/SHA, the source root and metadata inventory. All parent write
   access is checked before deletion. A durable `prune-start.json` records the
   incomplete phase and restore mapping before any unlink. Every selected
   source is then rehashed immediately before unlink, with held-parent and
   identity checks and directory fsync. The six preserved files are rechecked.
   A failure retains the archive, marker and partial progress; no retry occurs.
3. `--offload-verified --batch N` requires successful pruning, re-verifies the
   NVMe archive, writes one exclusive USB file
   `gsq-baseline-a-state-bins-NN.tar.gz`, fsyncs it and its parent, then checks its
   complete SHA. It reserves 2 GiB of USB free bytes. File creation may still
   fail for filesystem reasons; in that case the local archive remains.
4. `--release-local-verified --batch N` re-verifies all USB tar members and the
   full SHA and identities again before removing only the NVMe tar.gz file.
   All small receipts, source-stat metadata and restore mapping remain on NVMe.
   The next batch cannot begin until this phase has succeeded for the prior one.

The CLI's non-mutating `--plan` reads only the compact audited index/review and
prints the fixed batch list. Real phases require nice19, helper cores
8–15,24–31 and a 4 GiB address-space limit. Example **after explicit root review**:

```sh
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  taskset -c 8-15,24-31 nice -n19 \
  /home/steve/.venvs/vllm-xpu/bin/python -B closed_baseline_bins.py --archive --batch 0
```

The small phase results are also saved exclusively under `storage/evidence/`.
Those tracked receipts bind the external archive name/hash and original authority;
the archives and all source-stat details remain outside Git. A successful copy
receipt is required for pruning; a successful USB readback is required for local
archive removal. Raw state is a retained research artifact, not disposable cache.
The original baseline audit remains evidence about the original files; after
pruning, those file paths need restoration before any new raw-state audit.

Restore instructions: select the exact batch and archive named in its verified
receipt, verify its full SHA and every member against the immutable baseline
index, then restore **missing** files under the original fixed baseline root.
Tar member names are the original relative paths. Do not overwrite the six
preserved files or any existing file without a separate comparison/review. This
helper has no automatic restoration or deletion of failed attempts. The threat
model excludes hostile concurrent mutation by the same user; it detects ordinary
file replacement, mutation, symlinks, aliases, incomplete copies and checksum drift.

The [15 CPU tests](test_closed_baseline_bins.py) use temporary files plus the small
frozen index. They cover complete readback/prune/offload, digest corruption,
symlinks/hardlinks/traversal, quota/reserve, changed originals/archive replacement,
marker failure and partial unlink failure, USB mutation before local release,
and the exact 27-way index partition. They are not a filesystem durability proof
for the actual NTFS mount. The earlier 12-test source is retained under
`lineage/before-per-request-batches/`.
