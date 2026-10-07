"""One-shot research preservation: archive and compare; never delete sources."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

BASE = Path('/home/steve/git-archives/staging-consolidation-20261007')
PARENT = Path('/home/steve')
NAMES = [
    'staged-xpu-commitfix-20260820',
    'staged-xpu-commitfix-graphfa-composite-20260820',
    'qwen38-gdn-poison-stage-20260822',
    'qwen38-m6-head256-q8k64-attn-override-20260820-r3',
    'qwen38-m6-head256-q8k64-attn-override-20260820-r4',
    'qwen38-m6-head256-q64k32-attn-override-20260821-r2',
    'qwen38-m6-head256-q64k32-attn-override-20260821-r3',
    'qwen38-m6-head256-q64k32-attn-override-20260821-r1',
]


def run(args, output, errors):
    process = subprocess.Popen(args, stdin=subprocess.DEVNULL,
                               stdout=output, stderr=errors, start_new_session=True)
    while process.poll() is None:
        if shutil.disk_usage(BASE).free < 10 * 1024**3:
            import signal
            os.killpg(process.pid, signal.SIGTERM)
            process.wait()
            raise RuntimeError('10 GiB free-space floor reached; sources retained')
        time.sleep(2)
    if process.returncode:
        raise RuntimeError(f'Archive/compare failed: {process.returncode}; sources retained')


for name in NAMES:
    source = PARENT / name
    assert source.is_dir() and not source.is_symlink(), source
    allocated = int(subprocess.check_output(['du', '-s', '-B1', str(source)], text=True).split()[0])
    archive = BASE / (name + '.tar.zst')
    with archive.open('xb') as output, (BASE / (name + '-create.log')).open('x') as errors:
        run(['tar', '--sparse', '--acls', '--xattrs', '-I', 'zstd -T2 -3',
             '-cf', '-', '-C', str(PARENT), name], output, errors)
        output.flush()
        os.fsync(output.fileno())
    with (BASE / (name + '-compare.log')).open('x') as output:
        run(['tar', '--zstd', '--acls', '--xattrs', '--compare', '-f', str(archive),
             '-C', str(PARENT)], output, subprocess.STDOUT)
    with archive.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    receipt = {
        'source': str(source), 'source_allocated_bytes': allocated,
        'archive': str(archive), 'archive_bytes': archive.stat().st_size,
        'archive_sha256': digest, 'tar_compare_returncode': 0,
        'source_deleted': False, 'archive_fsynced': True,
        'restore_command': f'tar --zstd --acls --xattrs -xf {archive} -C {PARENT}',
        'warning': 'Same-disk preservation archive, not an independent backup. Restore before using historical launchers.'
    }
    with (BASE / (name + '-verified.json')).open('x') as stream:
        stream.write(json.dumps(receipt, indent=2) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    directory_fd = os.open(BASE, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    print(json.dumps(receipt), flush=True)
