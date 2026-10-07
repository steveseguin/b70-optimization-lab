"""Full hashes and bounded restore checks, invoked by monitored readback driver."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2]
created = json.loads((OUT/'backup-created.json').read_text())
assert os.path.ismount('/mnt/usb-models')
assert os.statvfs('/mnt/usb-models').f_flag & os.ST_RDONLY
rows = created['files'] + json.loads((OUT/'backup-control-files.json').read_text())['files']
for row in rows:
    path = Path(row['path'])
    assert path.stat().st_size == row['bytes'], str(path)
    with path.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    assert actual == row['sha256'], str(path)
    row['post_remount_readback_verified'] = True
    (OUT/'readback-progress.json').write_text(json.dumps(rows, indent=2)+'\n')
    print('Read-back SHA256 matches:', path.name, flush=True)
base = Path(rows[0]['path']).parent
subprocess.run(['python3', str(REPO/'scripts/check-storage-headroom.py'), '/tmp',
                '--planned-write-bytes', '2GiB'], check=True, stdout=subprocess.DEVNULL)
with tempfile.TemporaryDirectory(prefix='lab-backup-restore-') as temporary:
    target = Path(temporary)/'lab.git'
    cloned = subprocess.run(['git', 'clone', '--mirror', '--no-hardlinks',
                              str(base/'lab-history.bundle'), str(target)],
                             capture_output=True, text=True, timeout=180)
    (OUT/'bundle-restore.log').write_text(cloned.stdout+cloned.stderr)
    assert cloned.returncode == 0, cloned.stderr
    checked = subprocess.run(['git', '--git-dir='+str(target), 'fsck', '--full'],
                              capture_output=True, text=True, timeout=180)
    (OUT/'bundle-fsck.log').write_text(checked.stdout+checked.stderr)
    assert checked.returncode == 0, checked.stderr
    head = subprocess.check_output(['git', '--git-dir='+str(target), 'rev-parse', 'HEAD'], text=True).strip()
    assert head == created['source_commit']
    # Restore two pinned packet-98 files without extracting unrelated archive paths.
    prefix = 'mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-size-98/'
    pins = {
        prefix+'manifest.json': '918b47a5530b4dc97fe8fc8f4ec77fd64521ec6846217c54f5fba589e0e8377f',
        prefix+'source/scripts/ltx_output_size_98.py': '895b1c02ac764838b5d69446b0e5cf054884b191dd8b9446c5ce641ec40f2e52',
    }
    extracted = Path(temporary)/'packet98'
    extracted.mkdir()
    restored = subprocess.run(['tar', '--zstd', '-xf', str(base/'research-preservation.tar.zst'),
                                '-C', str(extracted), '--no-same-owner', '--', *pins],
                               capture_output=True, text=True, timeout=900)
    (OUT/'packet98-restore.log').write_text(restored.stdout+restored.stderr)
    assert restored.returncode == 0, restored.stderr
    for name, expected in pins.items():
        assert hashlib.sha256((extracted/name).read_bytes()).hexdigest() == expected, name
result = {'status': 'content-and-restore-checks-passed-awaiting-postflight',
          'source_commit': created['source_commit'], 'files': rows,
          'bundle_restored_to_temporary_bare_repository': True, 'git_fsck_full_passed': True,
          'packet98_restored_files': pins, 'all_sources_retained': True,
          'long_term_drive_reliability_certified': False}
(OUT/'verification.json').write_text(json.dumps(result, indent=2)+'\n')
print('Git restore/fsck and pinned packet-98 file restore passed.', flush=True)
