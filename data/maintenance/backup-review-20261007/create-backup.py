"""One-shot additive external backup. Never removes or modifies source trees."""
from pathlib import Path
import hashlib
import json
import os
import re
import signal
import subprocess
import time

REPO = Path('/home/steve/llm-optimizations')
OUT = Path(__file__).resolve().parent
DEST = Path('/mnt/usb-models/lab-backups/steve-b70s-20261007')
SELECTION = Path('/home/steve/git-archives/backup-selection-20261007.nul')
FAULT = re.compile(r'I/O error|uas_eh|USB disconnect|reset .*USB|ntfs.*error|Fault response|GPU HANG|timed.out job', re.I)
CURSOR = (OUT / 'kernel-start-cursor.txt').read_text().strip().split('-- cursor: ')[1]


def guard():
    assert os.path.ismount('/mnt/usb-models')
    mount = json.loads(subprocess.check_output(
        ['findmnt', '-J', '-o', 'SOURCE,FSTYPE,OPTIONS', '/mnt/usb-models'], text=True, timeout=10))['filesystems'][0]
    assert mount['source'] == '/dev/sda2' and mount['fstype'] == 'fuseblk'
    assert 'rw' in mount['options'].split(',')
    assert Path('/dev/disk/by-uuid/4E0E66ED0E66CD91').resolve() == Path('/dev/sda2')
    stats = os.statvfs(DEST)
    assert stats.f_bavail * stats.f_frsize > 50 * 1024**3, 'External free-space floor reached'
    log = subprocess.check_output(
        ['journalctl', '-k', '-b', '--after-cursor', CURSOR, '--no-pager'], text=True, timeout=10)
    (OUT / 'kernel-during-backup.txt').write_text(log)
    assert not FAULT.search(log), 'New kernel fault; stop all backup I/O'


def run(args, name):
    guard()
    started = time.monotonic()
    with (OUT / (name + '.log')).open('xb') as log:
        process = subprocess.Popen(args, cwd=REPO, stdout=log, stderr=subprocess.STDOUT,
                                   stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            while process.poll() is None:
                time.sleep(3)
                guard()
                assert time.monotonic() - started < 1800, 'Stage exceeded 30-minute bound'
            assert process.returncode == 0, f'{name} failed: {process.returncode}'
        except BaseException:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                # No kill/retry loop. A stuck kernel operation needs separate review.
                process.wait(timeout=15)
            raise
    guard()


def seal(partial, final, role):
    name = final.name + '-seal'
    run(['python3', str(OUT/'seal-file.py'), str(partial), str(final)], name)
    row = json.loads((OUT/(name+'.log')).read_text())
    row['role'] = role
    rows.append(row)
    (OUT / 'backup-created.json').write_text(json.dumps(
        {'source_commit': head, 'sources_retained': True, 'files': rows}, indent=2)+'\n')
    print(json.dumps(row), flush=True)


assert DEST.is_dir() and SELECTION.is_file()
selection_receipt = json.loads((OUT/'selection-summary.json').read_text())
assert selection_receipt['admitted']
assert hashlib.sha256(SELECTION.read_bytes()).hexdigest() == selection_receipt['nul_list_sha256']
subprocess.run(['python3', str(REPO/'scripts/check-storage-headroom.py'), str(DEST),
                '--require-mount', '/mnt/usb-models', '--planned-write-bytes', '100GiB'],
               check=True, stdout=subprocess.DEVNULL)
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
rows = []
for name in ('lab-history.bundle', 'tracked-worktree.tar', 'research-preservation.tar.zst'):
    assert not (DEST/name).exists() and not (DEST/(name+'.incomplete')).exists()
partial = DEST/'lab-history.bundle.incomplete'
run(['git', 'bundle', 'create', str(partial), '--all'], 'git-bundle-create')
run(['git', 'bundle', 'verify', str(partial)], 'git-bundle-verify')
seal(partial, DEST/'lab-history.bundle', 'All current local Git refs; full restore validation follows')
partial = DEST/'tracked-worktree.tar.incomplete'
run(['git', 'archive', '--format=tar', '--output='+str(partial), head], 'git-archive-create')
run(['python3', str(OUT/'verify-git-archive.py'), str(partial), head], 'git-archive-compare')
seal(partial, DEST/'tracked-worktree.tar', 'Tracked worktree at source_commit')
partial = DEST/'research-preservation.tar.zst.incomplete'
run(['tar', '--sparse', '--acls', '--xattrs', '--no-recursion', '--null', '--verbatim-files-from',
     '-I', 'zstd -T2 -3', '-cf', str(partial), '-C', '/', '-T', str(SELECTION)], 'research-archive-create')
run(['tar', '--zstd', '--acls', '--xattrs', '--compare', '-f', str(partial), '-C', '/'], 'research-archive-compare')
run(['python3', str(OUT/'verify-members.py'), str(partial), str(SELECTION)], 'research-archive-members')
seal(partial, DEST/'research-preservation.tar.zst', 'Frozen explicit research selection; full tar comparison passed')
print('Creation and source comparisons complete; clean remount/readback still required.', flush=True)
