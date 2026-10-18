#!/usr/bin/env python3
"""CPU-only original-byte evidence snapshot. Never imports runtime code."""
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
    assert not (HERE / 'inputs.tar.gz').exists()
    files, runs = {}, []
    for lane in 'AB':
        folder = HERE.parent / 'screen/v4-lanes/evidence' / (
            f'p118-89f2d60778eb2d6e-composite-{lane}-1-candidate')
        chosen = [folder / name for name in ('summary.json', 'identity.json',
                  'suite-manifest.snapshot.json', 'run/adapter/selection.json')]
        chosen += [folder / 'run/ranks' / rank / leaf
                   for rank in ('rank0', 'rank1')
                   for leaf in ('p105-transfers.jsonl', 'sites.jsonl', 'timings.jsonl')]
        for path in chosen:
            files[str(path.relative_to(ROOT))] = path.read_bytes()
        runs.append({'lane': lane, 'folder': str(folder.relative_to(ROOT))})
    for leaf in ('native_controller.hpp', 'rank.hpp', 'mtp.hpp', 'p105_runtime.hpp',
                 'bundle-selection.json', 'README.md', 'queue_runner.py'):
        path = HERE.parent / 'packet124-record-bundle' / leaf
        files[str(path.relative_to(ROOT))] = path.read_bytes()
    # Every repository negative index is inventoried, not only matching names.
    negatives = sorted(ROOT.rglob('DO-NOT-REPEAT.md'))
    for path in negatives:
        files[str(path.relative_to(ROOT))] = path.read_bytes()
    pins = {name: {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
            for name, raw in sorted(files.items())}
    snapshot = {'runs': runs, 'files': pins, 'negative_indexes': len(negatives)}
    for name, raw in files.items():
        assert (ROOT / name).read_bytes() == raw, name
    files['snapshot.json'] = (json.dumps(snapshot, indent=2) + '\n').encode()
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        for name, raw in sorted(files.items()):
            entry = tarfile.TarInfo(name)
            entry.size, entry.mode = len(raw), 0o644
            archive.addfile(entry, io.BytesIO(raw))
    packed = gzip.compress(stream.getvalue(), mtime=0)
    with tarfile.open(fileobj=io.BytesIO(packed), mode='r:gz') as archive:
        for name, raw in files.items():
            assert archive.extractfile(name).read() == raw
    (HERE / 'inputs.tar.gz').write_bytes(packed)
    print(json.dumps({'files': len(files), 'bytes': len(packed),
                      'negative_indexes': len(negatives), 'all_members_verified': True}))


if __name__ == '__main__':
    main()
