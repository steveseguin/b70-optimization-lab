# Storage inventory and owner cleanup proposal — 2026-10-10

**Proposed recovery: 42,018,201,600 allocated bytes (42.02 GB / 39.13 GiB), conditional on the owner's decision and fresh verification. Nothing was cleaned up.** Archive the rejected transformer, prove that the internal good model plus the saved 79-byte reverse patch reproduces every rejected byte, then remove only that redundant rejected copy. Keep every preview, anchor, receipt, log, latch, qualification verdict and oracle tensor. The existing duplicate-retirement rules admit **zero** further captures; old October 8 reclaim totals are not current.

Snapshot: **2026-10-10T05:50:53.168115Z to 2026-10-10T05:51:04.026795Z**, `steve-b70s`. One single-thread `ionice -c3` recursive metadata walk of `/mnt/fast-ai/bench-results/ltx25-baseline-20260913`, followed by small receipt/source reads and the retirement helper's metadata-only `census()` with `WORKERS=1`. No bulk payload hashing, parallel du, GPU/device access, server/port access, unit operation, mount, signal, model import or change to either protected tree. The two deliverables are the only repository edits. Temporary metadata files were written under `/tmp`.

[Machine-readable inventory](../data/resume-20261008/storage-inventory-20261010.json) includes all 3,672 packet/run/family groups, content counts, bytes, exact mtimes, hash examples, exclusions and headroom arithmetic. No symlinks, special files, read errors or hardlinked regular files were encountered. Logical bytes are `st_size`; allocated bytes are `st_blocks × 512`, including directory blocks in the table. Sparse captures explain logical/allocated differences. Dates are file modification ranges, not session start/end times. The results root's own directory blocks are excluded.

The scan contains **480,424 files**, 90,371 directories, **180,234,556,436 logical bytes / 181,079,801,856 allocated bytes**. `output/` is 80,437,854,208 allocated bytes (74.91 GiB), with 9,197 immediate entries. Its bulk is validation tensors, including qualification tensors inside archives. All videos in the results root together occupy only **720,445,440 allocated bytes**, including two MKVs. Removing previews cannot meet a 30 GB target.

The filesystem had **95,285,288,960 available bytes** (88.74 GiB), giving **41,598,197,760 bytes** (38.74 GiB) above the 53,687,091,200-byte (50 GiB) reserve. `f_bfree` includes privileged reserved space and is not the admission budget. `/`, `/home`, `/tmp` and `/mnt/fast-ai` share this capacity.

## Inventory by class, packet and session

Counts distinguish immediate entries from recursively contained regular files. `encoder-server-*` includes adjacent `.log` files as well as run directories; `others` includes root logs, repair blocks, boot-health records, screens, unlaunched snapshots and other evidence. For validation, requests, quarantine and fault/latch archives, entries counts the containing top-level directory. JSON provides every run/family separately.

| Class | Entries | Files | Logical bytes | Allocated bytes + dirs | File dates UTC |
|---|---|---|---|---|---|
| `encoder-server-*` | 329 | 166924 | 4,926,299,335 | 5,372,063,744 | 2026-09-14 to 2026-10-10 |
| `fault-archive` | 1 | 3 | 2,025 | 16,384 | 2026-10-08 to 2026-10-09 |
| `latch-archive` | 1 | 1 | 604 | 8,192 | 2026-10-09 to 2026-10-09 |
| `others` | 285 | 13862 | 592,014,136 | 629,952,512 | 2026-09-14 to 2026-10-07 |
| `output/archive-*` | 18 | 1751 | 12,057,703,303 | 12,068,265,984 | 2026-10-08 to 2026-10-10 |
| `output/f100b-*` | 133 | 133 | 7,652,514 | 8,437,760 | 2026-10-07 to 2026-10-07 |
| `output/f58-*` | 36 | 36 | 1,738,954 | 1,970,176 | 2026-09-16 to 2026-09-16 |
| `output/f61-*` | 12 | 12 | 584,913 | 659,456 | 2026-09-17 to 2026-09-17 |
| `output/f62-*` | 41 | 41 | 1,547,360 | 1,789,952 | 2026-09-17 to 2026-09-17 |
| `output/f64-*` | 32 | 32 | 1,551,700 | 1,753,088 | 2026-09-17 to 2026-09-17 |
| `output/f65-*` | 64 | 64 | 2,995,509 | 3,403,776 | 2026-09-17 to 2026-09-17 |
| `output/f66-*` | 15 | 15 | 674,920 | 770,048 | 2026-09-17 to 2026-09-17 |
| `output/f67-*` | 2 | 2 | 114,357 | 122,880 | 2026-09-17 to 2026-09-17 |
| `output/f70-*` | 2 | 2 | 114,357 | 122,880 | 2026-09-17 to 2026-09-17 |
| `output/f71-*` | 2 | 2 | 114,357 | 122,880 | 2026-09-17 to 2026-09-17 |
| `output/f72-*` | 2 | 2 | 114,357 | 122,880 | 2026-09-17 to 2026-09-17 |
| `output/f73-*` | 24 | 24 | 1,038,342 | 1,196,032 | 2026-09-17 to 2026-09-17 |
| `output/f74-*` | 34 | 34 | 1,467,532 | 1,691,648 | 2026-09-17 to 2026-09-17 |
| `output/f77-*` | 168 | 168 | 7,174,043 | 8,290,304 | 2026-09-18 to 2026-09-18 |
| `output/f78b-*` | 1 | 1 | 52,853 | 57,344 | 2026-09-19 to 2026-09-19 |
| `output/f79b-*` | 5 | 5 | 181,453 | 208,896 | 2026-09-19 to 2026-09-19 |
| `output/f80-*` | 1 | 1 | 52,853 | 57,344 | 2026-09-19 to 2026-09-19 |
| `output/f81-*` | 54 | 54 | 10,007,233 | 10,231,808 | 2026-09-19 to 2026-09-19 |
| `output/f82b-*` | 29 | 29 | 1,231,449 | 1,421,312 | 2026-09-19 to 2026-09-19 |
| `output/f83c-*` | 32 | 32 | 1,234,339 | 1,437,696 | 2026-09-19 to 2026-09-19 |
| `output/f83e-*` | 119 | 119 | 5,094,159 | 5,881,856 | 2026-09-20 to 2026-09-20 |
| `output/f83f-*` | 125 | 125 | 5,335,734 | 6,164,480 | 2026-09-20 to 2026-09-20 |
| `output/f84-*` | 147 | 147 | 6,278,535 | 7,254,016 | 2026-09-20 to 2026-09-20 |
| `output/f86-*` | 29 | 29 | 1,231,699 | 1,421,312 | 2026-09-20 to 2026-09-20 |
| `output/f87-*` | 82 | 83 | 3,592,079 | 4,132,864 | 2026-09-20 to 2026-09-20 |
| `output/f88-*` | 2 | 2 | 105,706 | 114,688 | 2026-09-20 to 2026-09-20 |
| `output/f89-*` | 122 | 122 | 5,540,369 | 6,344,704 | 2026-09-21 to 2026-09-21 |
| `output/f90-*` | 116 | 116 | 4,434,734 | 5,169,152 | 2026-09-21 to 2026-09-21 |
| `output/f90c-*` | 238 | 238 | 10,194,098 | 11,771,904 | 2026-10-03 to 2026-10-03 |
| `output/f91b-*` | 147 | 147 | 6,278,535 | 7,254,016 | 2026-10-03 to 2026-10-03 |
| `output/f91c-*` | 197 | 197 | 8,424,485 | 9,732,096 | 2026-10-03 to 2026-10-04 |
| `output/f92a-*` | 77 | 77 | 3,274,205 | 3,784,704 | 2026-10-03 to 2026-10-03 |
| `output/f92b-*` | 12 | 12 | 534,896 | 610,304 | 2026-10-04 to 2026-10-04 |
| `output/f92p-*` | 159 | 159 | 6,813,809 | 7,868,416 | 2026-10-03 to 2026-10-03 |
| `output/f93b-*` | 77 | 77 | 3,274,205 | 3,784,704 | 2026-10-04 to 2026-10-04 |
| `output/f93c-*` | 217 | 217 | 9,101,357 | 10,506,240 | 2026-10-04 to 2026-10-04 |
| `output/f94f-*` | 239 | 239 | 9,929,667 | 11,476,992 | 2026-10-04 to 2026-10-04 |
| `output/f95-*` | 266 | 266 | 11,055,522 | 12,763,136 | 2026-10-04 to 2026-10-04 |
| `output/f95b-*` | 397 | 397 | 16,480,123 | 19,030,016 | 2026-10-04 to 2026-10-04 |
| `output/f96-*` | 1807 | 1807 | 75,820,924 | 87,248,896 | 2026-10-04 to 2026-10-06 |
| `output/f97-*` | 2446 | 2446 | 103,126,809 | 118,292,480 | 2026-10-06 to 2026-10-06 |
| `output/f98-*` | 133 | 133 | 5,527,761 | 6,381,568 | 2026-10-07 to 2026-10-07 |
| `output/f99-*` | 4 | 4 | 246,111 | 274,432 | 2026-10-07 to 2026-10-07 |
| `output/f99b-*` | 133 | 133 | 7,652,514 | 8,437,760 | 2026-10-07 to 2026-10-07 |
| `output/others` | 709 | 713 | 83,328,054 | 87,367,680 | 2026-09-14 to 2026-10-07 |
| `output/root` | 1 | 0 | 0 | 864,256 | — to — |
| `output/s97-*` | 28 | 28 | 1,179,908 | 1,355,776 | 2026-10-08 to 2026-10-08 |
| `output/stream112-*` | 166 | 166 | 15,092,341 | 16,097,280 | 2026-10-08 to 2026-10-08 |
| `output/stream114-*` | 76 | 76 | 13,710,729 | 14,168,064 | 2026-10-08 to 2026-10-08 |
| `output/stream116-*` | 77 | 77 | 13,851,064 | 14,315,520 | 2026-10-08 to 2026-10-08 |
| `output/stream116b-*` | 81 | 81 | 14,347,505 | 14,831,616 | 2026-10-08 to 2026-10-08 |
| `output/stream117-*` | 61 | 61 | 11,617,225 | 12,001,280 | 2026-10-10 to 2026-10-10 |
| `output/validation` | 1 | 24274 | 68,357,691,819 | 67,809,017,856 | 2026-09-14 to 2026-10-10 |
| `prepared-*` | 142 | 209948 | 9,692,722,751 | 10,315,362,304 | 2026-09-14 to 2026-10-10 |
| `quarantine` | 1 | 4 | 83,683,533,054 | 83,683,561,472 | 2026-09-14 to 2026-09-14 |
| `requests` | 1 | 54474 | 422,471,152 | 640,983,040 | 2026-09-14 to 2026-10-08 |

No immediate `output/stream113-*`, `stream115-*`, `stream118*`, `stream119-*`, `stream120-*` or `stream121-*` files remained at this snapshot: saved sessions are inside archives below. Packets 122, 123 and 123b have prepared trees; no new 123b live output was observed during this scan. CURRENT.md contains coordinator plans/timestamps later than the scan. This inventory does not assert which server is presently running.

| Archive/session under output | Files | Allocated bytes + dirs | File dates UTC |
|---|---|---|---|
| `archive-encoder-server-continuation-stream-117-f121-dg0-20261009T0158Z` | 201 | 916,000,768 | 2026-10-09 to 2026-10-09 |
| `archive-encoder-server-continuation-stream-117-f121-dg1-refused-20261009T0144Z` | 13 | 391,790,592 | 2026-10-09 to 2026-10-09 |
| `archive-encoder-server-continuation-stream-117-f97-20261009T0108Z` | 162 | 729,120,768 | 2026-10-09 to 2026-10-09 |
| `archive-stream112-run01` | 80 | 361,914,368 | 2026-10-08 to 2026-10-08 |
| `archive-stream113-run01` | 78 | 361,320,448 | 2026-10-08 to 2026-10-08 |
| `archive-stream114-run01-f49` | 182 | 369,053,696 | 2026-10-08 to 2026-10-08 |
| `archive-stream114-run02-f97` | 59 | 713,658,368 | 2026-10-08 to 2026-10-08 |
| `archive-stream115-run01-mixed49` | 168 | 368,553,984 | 2026-10-08 to 2026-10-08 |
| `archive-stream115-run02-guide49` | 181 | 372,375,552 | 2026-10-08 to 2026-10-08 |
| `archive-stream116-run01-refused` | 0 | 12,288 | — to — |
| `archive-stream118b-f121-dg0-live-20261010T0156Z` | 79 | 892,051,456 | 2026-10-10 to 2026-10-10 |
| `archive-stream118b-f121-dg0-live02-20261010T025118Z` | 79 | 891,686,912 | 2026-10-10 to 2026-10-10 |
| `archive-stream118b-f121-dg0-live03-20261010T033817Z` | 78 | 890,875,904 | 2026-10-10 to 2026-10-10 |
| `archive-stream118b-f121-dg1cap1-live-20261010T021306Z` | 64 | 888,647,680 | 2026-10-10 to 2026-10-10 |
| `archive-stream119-f121-eagerdisplay-live01-20261010T030951Z` | 79 | 891,162,624 | 2026-10-10 to 2026-10-10 |
| `archive-stream120-f121-live01-20261010T040357Z` | 79 | 890,896,384 | 2026-10-10 to 2026-10-10 |
| `archive-stream121-f145-live01-20261010T050411Z` | 85 | 1,069,490,176 | 2026-10-10 to 2026-10-10 |
| `archive-stream121-f145-live02-20261010T054956Z` | 84 | 1,069,654,016 | 2026-10-10 to 2026-10-10 |

Archives contain previews **and** qualification tensors/summaries; older archive layouts also contain requests. They are not compressed backups and the word archive grants no deletion authority. Session/run identities and content counts are in JSON `sessions`. Preview names are reused across sessions: match an archive to its `.completed-*` run receipt, not just a basename.

## Evidence classes and hash locations

- **(a), preserve:** validation and archived oracle/qualification tensors; all summary JSON; server identities, verdicts, requests, receipts and logs; all prepared seals/source/runtime snapshots; requests, latch/fault archives and unclassified others. The 3,777 tensor captures consume 79,500,566,528 allocated bytes. Their adjacent `summary.json` records `tensors.<images|video_latent|audio_latent|waveform>.sha256`, shapes and dtypes. These are **raw tensor hashes, not whole safetensors file hashes**. Failed and unmatched captures remain evidence. The retirement census reported 4,659 receipt-named paths, zero eligible deletions, 125 skipped rows lacking passing parity, five families with `all_exact=false`, and 15 lacking a tracked throughput record.
- **(b), identity recorded, keep here:** MP4s with matching `receipts/preview-<run>.json` (`sha256`, `bytes`, original path); anchors with `receipts/receipt-<run>.json` (`anchor_out.sha256`, bytes, dtype, shape). These are generated outputs with recorded hashes. Deterministic model output does not establish byte-identical MP4 re-encoding; replay and whole-file verification remain necessary before claiming exact regeneration. Older MP4s without a located whole-file receipt stay protected/unclassified.
- **(c), transient scratch:** **zero bytes certified disposable**. Compiled/cache-like suffixes total 16,048,128 allocated bytes and often belong to sealed snapshots. Partial, failed, rejected and archive names do not establish disposability.
- **Quarantine is (a) until proved reversible**, not download scratch. The transformer has an in-Git reconstruction description and original hash. The proposal preserves every evidence byte through this representation plus a full external copy. Partial downloads need exact prefix comparison before similar treatment.

Concrete example, relative to the results root:

```
encoder-server-continuation-stream-121-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145.completed-20261010T054956Z/receipts/preview-stream121-s00000315.json
  sha256 = 5972d22497bd3b76f127bdf0eb2cdb2de210d93d0d913d2a83c394774ace9de8
  bytes = 199362
output/archive-stream121-f145-live02-20261010T054956Z/stream121-s00000315/preview_00001_.mp4

encoder-server-continuation-stream-121-frame-dg0-adcone-bo1-pa1-smfp-two-way20-28-w1-b1-p1-dxpu2-s256x256-f145.completed-20261010T054956Z/receipts/receipt-stream121-s00000315.json
  anchor_out.sha256 = 123c30ff8729492e56b200672a154096f87452def3d51b37028f30ea144ca057
  anchor_out.bytes = 786432
```

The coordinator's `archive-stream121-live02-20261010T054956Z.json` records the rename; its contents are embedded in this inventory's JSON under `hash_examples.preview.archive_map_record` because that coordinator file was untracked during the audit. Embedded receipt paths remain historical. The inventory read these records but did not rehash their MP4 or anchor payloads. Keep the relocation map with the receipts.

## What the owner could reclaim

| Candidate | Allocated bytes recoverable | GiB | Condition |
|---|---|---|---|
| encoder-publisher-download-prefix.partial | 11,165,241,344 | 10.40 | Optional: separate verification |
| gemma4-encoder-24ab21fc.rejected | 26,263,863,296 | 24.46 | Optional: separate verification |
| ltx-2.5-distilled-transformer-ad9eb77d.rejected | 42,018,201,600 | 39.13 | Primary: proof + archive |
| transformer-publisher-download-prefix.partial | 4,236,251,136 | 3.95 | Optional: separate verification |
| Existing duplicate-retirement census | 0 | 0 | No eligible files |
| All previews, anchors, receipts, tensors, prepared packets | 0 | 0 | Keep all |

The **primary selection is the transformer alone**. Optional rows are not summed into its 42.02 GB claim and are not selected by the commands below. No compression saving is assumed. Available capacity after primary recovery would be about 127.87 GiB before other writers and small receipts.

The [corruption account](../experiments/ltx25-b70/README.md#input-integrity-failure-before-first-generation), [79-byte delta](../experiments/ltx25-b70/data/transformer-corruption-byte-delta.json) and [repair receipt](../experiments/ltx25-b70/data/localized-repair-promotion.json) bind the original transformer, promoted replacement and offsets. The encoder has its own [112-byte repair record](../experiments/ltx25-b70/data/encoder-repair-promotion.json); it is a separate decision.

The [storage follow-up](2026-10-06-storage-and-recovery-followup.md) and [EX400U review](2026-10-06-ex400u-backup-review.md) establish an additional backup, not reliable sole-copy storage. October 7's selection included packet-97 validation and selected references but **excluded quarantine**. Its existing archive does not cover this candidate. The [completion receipt](../data/maintenance/backup-review-20261007/summary.json) says the drive was cleanly unmounted; the mount-table check here found no mount at `/mnt/usb-models`. No mount was attempted. External UUID: `4E0E66ED0E66CD91`. No SMART passthrough or firmware/repair operation is proposed.

The owner must decide whether exact reversible preservation of the corrupted file is acceptable. If the raw rejected file must stay on NVMe, primary recovery is **0**, not 42 GB. Otherwise retain the promoted internal model, Git delta, repair receipts and new verification/restore record indefinitely, plus a freshly verified external archive. EX400U must not become the only way to reconstruct evidence. Keep **all existing previews**, including adjacent chunks for seam review; no preview bytes enter the recovery total. This cannot restore previews pruned before the audit.

## Growth and headroom

Latest complete saved 145-frame line: packet 121 session 2, **316 preview receipts, 315 intervals over 1,860.099 seconds**, or **609.645 chunks/hour** (5.91 seconds/chunk). This is a saved-session estimate, not a new performance measurement or concurrent disk-usage delta. The coordinator was moving to 123b; its growth rate remains unmeasured here.

| Growing item | Gross bytes/hour | Retained growth |
|---|---:|---|
| Preview MP4s, mean 234,743 bytes/chunk | 143,109,920 | Bounded if consumed-preview disposal keeps pace; otherwise accumulates |
| F32 anchors, 786,432 bytes/chunk | 479,444,215 | Two newest stream anchors; no steady linear growth |
| Server receipts/logs and related evidence | 25,342,458 | Accumulates; includes startup averaged over 316 chunks |
| Client manifest/log/state files in s121-live02 | 2,947,533 | Manifest/logs accumulate; state overwrites |
| Qualification tensor captures | About 1.05 GB per 145-frame session | Per qualification, not per streamed chunk |

Core three receipts/chunk alone total 9,056,256 allocated bytes (28,660/chunk). The larger server allowance includes other run evidence. [session.py](../experiments/ltx25-b70/recovery/20261010-continuation123b-stream/session.py) retains two anchors; [integration.py](../experiments/ltx25-b70/recovery/20261010-continuation123b-stream/integration.py) also prunes obsolete frame anchors. The [existing client](../experiments/ltx25-b70/stream/ltx_continuation_client.py) disposes consumed previews only when enabled. Session 2's saved state has 57 undisposed chunks (259–315), matching its remaining 57 stream previews. No retention setting was changed.

| Conditional continuing rate | Bytes/hour | Days until 50 GiB reserve |
|---|---:|---:|
| Existing rolling previews/anchors; evidence estimate | 28,289,990 | 61.3 |
| Keep every preview at 240 KB + 4 KiB directory; anchors roll | 177,101,859 | 9.8 |
| Keep every preview and anchor | 656,546,074 | 2.64 |

Formula: `(available_bytes - 50 * 2^30) / bytes_per_hour / 24`. These are **line-only projections**, not a promise of 61 days of machine capacity. They exclude other writers, new packet builds, qualifications, run-directory block growth and nested client sinkwork. Each qualification/archive session retains roughly another GB; a model/image can consume the margin immediately. Prepared 123/123b added about 280 MB of allocated file data in the preceding hour. The run-write allowance can stop a run before the whole-filesystem floor. No allowance change is proposed.

## Exact commands — text only, not executed

Only after the owner's decision and a coordinator-approved quiet I/O window: the following reads tens of GB, deliberately deferred from the light inventory. The owner supplies a verified read/write mount of EX400U, then a fresh read-only remount for read-back. Commands operate no server, port or unit. Errors stop; never retry automatically. The first block proves reconstructibility and creates an external archive. The second, after remount and a clean storage-error check by the owner, verifies the archive, records restoration/intent evidence, and unlinks one exact rejected path. Preserve and commit the future receipts and update CURRENT.md in that cleanup commit. The current inventory does not authorize these commands.

```bash
# PROPOSAL ONLY — owner-approved quiet I/O window, external drive already mounted rw.
ionice -c3 python3 -B - <<'PY'
import hashlib, json, os, shutil, stat, subprocess, tarfile
from pathlib import Path
repo = Path('/home/steve/llm-optimizations')
invpath = repo / 'data/resume-20261008/storage-inventory-20261010.json'
inv = json.loads(invpath.read_text())
root = Path(inv['root'])
src = root / inv['proposal']['candidate']['path']
base = Path(inv['proposal']['reconstruction_base'])
delta_path = repo / inv['proposal']['delta']
delta = json.loads(delta_path.read_text())
mount = Path('/mnt/usb-models')
assert subprocess.check_output(['findmnt','-n','-o','UUID','-T',str(mount)], text=True).strip() == '4E0E66ED0E66CD91'
opts = subprocess.check_output(['findmnt','-n','-o','OPTIONS','-T',str(mount)], text=True).strip().split(',')
assert 'rw' in opts
assert shutil.disk_usage(mount).free > src.stat().st_size + 2**30
assert os.statvfs(root).f_bavail * os.statvfs(root).f_frsize >= 50 * 2**30

def stamp(p):
    assert not p.is_symlink() and p.resolve() == p
    s = p.stat()
    assert stat.S_ISREG(s.st_mode) and s.st_nlink == 1
    return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]

def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*2**20), b''): h.update(b)
    return h.hexdigest()

def durable(p, obj):
    with p.open('x') as f:
        json.dump(obj,f,indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
    fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY); os.fsync(fd); os.close(fd)

before = stamp(src); base_before = stamp(base)
expected = inv['proposal']['candidate']
assert before[:4] == [expected['dev'],expected['ino'],expected['logical_bytes'],expected['mtime_ns']]
assert base_before[2] == before[2]
# Hash the base and its reverse-patched byte stream; no reconstructed file is written.
good = hashlib.sha256(); rebuilt = hashlib.sha256(); offset = 0; applied = 0
with base.open('rb') as f:
    for raw in iter(lambda:f.read(4*2**20), b''):
        good.update(raw); b = bytearray(raw)
        for change in delta['changes']:
            i = change['offset'] - offset
            if 0 <= i < len(b):
                assert b[i] == change['after']
                b[i] = change['before']; applied += 1
        rebuilt.update(b); offset += len(b)
assert applied == len(delta['changes']) == 79
assert good.hexdigest() == delta['repaired_file_sha256']
assert rebuilt.hexdigest() == delta['rejected_file_sha256']
assert digest(src) == delta['rejected_file_sha256']
assert stamp(src) == before and stamp(base) == base_before
# Exclusive destination: an existing directory makes the command stop.
external = mount / 'lab-backups/steve-b70s-20261010-transformer'
external.mkdir()
archive = external / 'rejected-transformer.tar'
with tarfile.open(archive, 'x') as tf:
    tf.add(src, arcname=str(src.relative_to(root)), recursive=False)
with archive.open('rb') as f: os.fsync(f.fileno())
fd=os.open(external,os.O_RDONLY|os.O_DIRECTORY); os.fsync(fd); os.close(fd)
assert stamp(src) == before
record = {'source':str(src),'source_stat':before,'base':str(base),'base_stat':base_before,
          'base_sha256':good.hexdigest(),'source_sha256':rebuilt.hexdigest(),
          'delta':str(delta_path),'delta_sha256':digest(delta_path),
          'inventory_sha256':digest(invpath),'archive':str(archive),
          'archive_sha256':digest(archive),'member':str(src.relative_to(root)),
          'restore':'Restore the single tar member to the original results root; alternatively copy the pinned base and replace every delta offset with its before byte, then check source_sha256.',
          'internal_base_and_delta_must_be_retained':True,'reconstruction_proved':True,
          'readback_pending':True,'source_removed':False}
durable(repo/'data/resume-20261008/transformer-preservation-20261010.json',record)
durable(external/'preservation.json',record)
print('Archive and internal reconstruction proved; source retained. Fresh read-only remount/read-back required.')
PY
```

The owner now checks for new storage errors and supplies a fresh read-only mount of the same UUID. A current mount merely having `ro` does not prove it was freshly remounted. If any check fails, keep the source. No archive already on the EX400U is overwritten.

```bash
# PROPOSAL ONLY — owner has confirmed fresh ro remount and clean storage log.
ionice -c3 python3 -B - <<'PY'
import hashlib, json, os, subprocess, tarfile
from pathlib import Path
repo=Path('/home/steve/llm-optimizations')
r=json.loads((repo/'data/resume-20261008/transformer-preservation-20261010.json').read_text())
mount='/mnt/usb-models'
assert subprocess.check_output(['findmnt','-n','-o','UUID','-T',mount],text=True).strip()=='4E0E66ED0E66CD91'
assert 'ro' in subprocess.check_output(['findmnt','-n','-o','OPTIONS','-T',mount],text=True).strip().split(',')
def digest(f):
    h=hashlib.sha256()
    for b in iter(lambda:f.read(4*2**20),b''): h.update(b)
    return h.hexdigest()
def filehash(p):
    with p.open('rb') as f: return digest(f)
def stamp(p):
    assert p.resolve()==p and not p.is_symlink()
    s=p.stat(); assert s.st_nlink==1
    return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def durable(p,obj):
    with p.open('x') as f:
        json.dump(obj,f,indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
    fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY); os.fsync(fd); os.close(fd)
src=Path(r['source']); base=Path(r['base']); archive=Path(r['archive'])
assert stamp(src)==r['source_stat'] and stamp(base)==r['base_stat']
assert filehash(Path(r['delta']))==r['delta_sha256']
assert filehash(base)==r['base_sha256']
assert filehash(archive)==r['archive_sha256']
with tarfile.open(archive,'r:') as tf:
    members=tf.getmembers()
    assert len(members)==1 and members[0].name==r['member']
    assert members[0].isfile() and members[0].size==r['source_stat'][2]
    with tf.extractfile(members[0]) as f: assert digest(f)==r['source_sha256']
assert filehash(src)==r['source_sha256']
assert stamp(src)==r['source_stat'] and stamp(base)==r['base_stat']
# Durable exact source -> archive + local reconstruction map BEFORE any unlink.
intent=repo/'data/resume-20261008/transformer-retirement-20261010.intent.json'
durable(intent,{**r,'readback_pending':False,'readback_verified':True,'source_removed':False})
assert src==Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/quarantine/ltx-2.5-distilled-transformer-ad9eb77d.rejected')
assert stamp(src)==r['source_stat']
src.unlink()  # ONLY removal in this proposal: one explicitly verified ordinary file.
fd=os.open(src.parent,os.O_RDONLY|os.O_DIRECTORY); os.fsync(fd); os.close(fd)
durable(repo/'data/resume-20261008/transformer-retirement-20261010.json',
        {**r,'readback_pending':False,'readback_verified':True,'source_removed':True})
PY
```

Exact external restore command, also **not run**; requires enough space to restore 42,018,190,584 bytes while retaining the 50 GiB reserve. The destination must not already exist. This is an offline restore task, never a live-model swap:

```bash
ionice -c3 tar --extract --keep-old-files \
  --file=/mnt/usb-models/lab-backups/steve-b70s-20261010-transformer/rejected-transformer.tar \
  --directory=/mnt/fast-ai/bench-results/ltx25-baseline-20260913 \
  quarantine/ltx-2.5-distilled-transformer-ad9eb77d.rejected
ionice -c3 sha256sum /mnt/fast-ai/bench-results/ltx25-baseline-20260913/quarantine/ltx-2.5-distilled-transformer-ad9eb77d.rejected
# Required hash: ad9eb77d12e611917f91cc71df924c6383a30cbf306b4d4afdf990912af0ebe9
```

If EX400U fails, the first block specifies the full internal reconstruction algorithm: ordinary-copy the promoted model, replace each of the 79 absolute offsets with `before`, then require the same rejected SHA-256 before accepting it. Do not patch the promoted base in place. Preserve the exact base identity as a restore dependency; a model upgrade must not discard it.
