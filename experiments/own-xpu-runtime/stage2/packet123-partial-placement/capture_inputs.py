#!/usr/bin/env python3
"""Preserve selected existing receipts byte-for-byte, without changing sources."""
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import shutil
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def main():
    resource.setrlimit(resource.RLIMIT_AS, (8 * 1024**3, 8 * 1024**3))
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    assert shutil.disk_usage(ROOT).free >= 25_000_000_000
    target = HERE / 'inputs.tar.gz'
    assert not target.exists(), 'preserved evidence must not be overwritten'
    files = {}
    runs = []
    for name in ('B-0-control', 'B-1-candidate'):
        folder = HERE.parent / 'screen/v4-lanes/evidence' / ('p118-89f2d60778eb2d6e-composite-' + name)
        receipts = sorted(p for p in (folder / 'run').glob('*/receipt.json')
                          if p.parent.name != 'incident64')
        assert len(receipts) == 12
        rank_files = [folder / 'run/ranks' / rank / leaf for rank in ('rank0', 'rank1')
                      for leaf in ('sites.jsonl', 'timings.jsonl', 'p105-transfers.jsonl')
                      if (folder / 'run/ranks' / rank / leaf).exists()]
        selected = [*receipts, *rank_files, folder / 'identity.json',
                    folder / 'suite-manifest.snapshot.json', folder / 'run/adapter/selection.json']
        for p in selected:
            files[str(p.relative_to(ROOT))] = p.read_bytes()
        runs.append({'source': str(folder.relative_to(ROOT)),
                     'summary_present': (folder / 'summary.json').exists(),
                     'receipts': [str(p.relative_to(ROOT)) for p in receipts],
                     'rank_files': [str(p.relative_to(ROOT)) for p in rank_files]})
    for leaf in ('native_controller.hpp', 'rank.hpp', 'p105_runtime.hpp'):
        p = HERE.parent / 'packet118-record-bundle' / leaf
        files[str(p.relative_to(ROOT))] = p.read_bytes()
    snapshot = {'runs': runs, 'files': {n: {'sha256': hashlib.sha256(b).hexdigest(),
                                          'bytes': len(b)} for n, b in files.items()}}
    # Refuse a changed source during the capture, rather than mixing epochs.
    for relative, raw in files.items():
        assert (ROOT / relative).read_bytes() == raw, relative
    files['snapshot.json'] = (json.dumps(snapshot, indent=2) + '\n').encode()
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        for relative, raw in sorted(files.items()):
            entry = tarfile.TarInfo(relative)
            entry.size = len(raw)
            entry.mode = 0o644
            archive.addfile(entry, io.BytesIO(raw))
    packed = gzip.compress(stream.getvalue(), mtime=0)
    with tarfile.open(fileobj=io.BytesIO(packed), mode='r:gz') as archive:
        for relative, raw in files.items():
            assert archive.extractfile(relative).read() == raw
    target.write_bytes(packed)
    print(json.dumps({'files': len(files), 'bytes': len(packed),
                      'all_members_verified': True, 'device_executed': False}))


if __name__ == '__main__':
    main()
