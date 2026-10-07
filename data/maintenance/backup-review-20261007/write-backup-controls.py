"""Add self-contained restore instructions and checksums; no existing files overwritten."""
from pathlib import Path
import hashlib
import json
import os
import shutil

OUT = Path(__file__).resolve().parent
DEST = Path('/mnt/usb-models/lab-backups/steve-b70s-20261007')
assert os.path.ismount('/mnt/usb-models')
assert not os.statvfs(DEST).f_flag & os.ST_RDONLY
created = json.loads((OUT/'backup-created.json').read_text())
assert len(created['files']) == 3
controls = []


def finish(path):
    with path.open('rb') as stream:
        os.fsync(stream.fileno())
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    row = {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest,
           'post_remount_readback_verified': False}
    controls.append(row)
    return row


for source, name in ((Path('/home/steve/git-archives/backup-selection-20261007.nul'), 'research-selection.nul'),
                     (OUT/'selection-summary.json', 'research-selection-summary.json')):
    with source.open('rb') as source_stream, (DEST/name).open('xb') as destination:
        shutil.copyfileobj(source_stream, destination, 8*1024*1024)
    row = finish(DEST/name)
    with source.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == row['sha256']
instructions = '''Four-card lab additional preservation copy, 2026-10-07 UTC.

All internal originals were retained. This set is not a complete machine/model
backup, and a verified copy does not certify long-term USB/NTFS reliability.
Do not run firmware reinitialization on this drive: the vendor's documented
ULFM91.0 recovery procedure erases data. It was not performed for this backup.

From this directory, verify file integrity with:
  sha256sum -c SHA256SUMS

Restore Git into a NEW, empty location:
  git clone lab-history.bundle /path/to/new/lab
  git -C /path/to/new/lab fsck --full

Alternatively extract the tracked snapshot into an EMPTY directory:
  tar -xf tracked-worktree.tar -C /path/to/empty/worktree

Research archive names preserve the original home/steve/... and mnt/fast-ai/...
layout, without leading slashes. Extract into an EMPTY staging directory first:
  tar --zstd --acls --xattrs -xf research-preservation.tar.zst -C /path/to/empty/staging
Review its contents before restoring anything to its original absolute path.
Some sources have read-only modes, root ownership or absolute symlink targets.
Tar preserves symlinks without copying their external targets. Running as an
ordinary user does not restore ownership; privileged restoration needs review.
Never extract blindly over an active runtime or newer research.

research-selection-summary.json explains selected and omitted evidence.
research-selection.nul is the complete NUL-separated list of archived paths.
The standalone qwen38-nightly-strict-cache archive is the small write pilot;
the full research archive also contains its preserved original copy.

The final post-remount readback and restore-test receipt is retained in the lab
repository at data/maintenance/backup-review-20261007/verification.json, with
the explanation in notes/2026-10-06-ex400u-backup-review.md. The Git snapshot
here precedes that final receipt; later receipts are committed separately.
'''
with (DEST/'RESTORE.txt').open('x') as stream:
    stream.write(instructions)
finish(DEST/'RESTORE.txt')
pilot = json.loads((OUT/'write-pilot.json').read_text())
controls.append({'path': pilot['destination'], 'bytes': pilot['bytes'], 'sha256': pilot['sha256'],
                 'post_remount_readback_verified': False})
items = created['files'] + controls
index = {'source_commit': created['source_commit'], 'all_internal_sources_retained': True,
         'files': [{'name': Path(row['path']).name, 'bytes': row['bytes'], 'sha256': row['sha256']} for row in items]}
with (DEST/'BACKUP-INDEX.json').open('x') as stream:
    json.dump(index, stream, indent=2)
    stream.write('\n')
finish(DEST/'BACKUP-INDEX.json')
with (DEST/'SHA256SUMS').open('x') as stream:
    for row in created['files'] + controls:
        stream.write(row['sha256']+'  '+Path(row['path']).name+'\n')
finish(DEST/'SHA256SUMS')
fd = os.open(DEST, os.O_RDONLY | os.O_DIRECTORY)
try:
    os.fsync(fd)
finally:
    os.close(fd)
(OUT/'backup-control-files.json').write_text(json.dumps({'files': controls}, indent=2)+'\n')
print('Restore instructions, complete selection and checksums written and flushed.')
