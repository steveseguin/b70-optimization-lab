#!/usr/bin/env python3
"""Restore exact parent fixture bytes, locally; never run or change a binary."""
import argparse
import json
import os
from pathlib import Path
import tarfile

from storage import digest, REGISTERED_CHAIN, B as OUTPUT_BUILD, precheck

P = Path(__file__).resolve().parent


def restore(source=None, *, cpu_only=False):
    if (OUTPUT_BUILD / REGISTERED_CHAIN).exists():
        raise ValueError('registered chain already started; do not change inputs')
    manifest = json.loads((P / 'input-fixtures.json').read_text())
    target = P / 'build/fusion-fixtures'
    if target.is_symlink():
        raise ValueError('fixture destination must be packet-owned')
    files = manifest['files']
    candidates = [source] if source else [P.parent / 'packet56-draft-prefix/build/fusion-fixtures',
                                         P.parent / 'packet61-spin-hcfusion/build/fusion-fixtures']
    source = next((p for p in candidates if p and p.resolve() != target.resolve()
                   and all((p / name).is_file() for name in files)), None)
    archive = None
    if source is None and not all((target / name).is_file() for name in files):
        archive = Path(manifest['archive'])
        if digest(archive) != manifest['archive_sha256']:
            raise ValueError('fixture archive identity changed')
    # No replacement, even for partial restores. Existing bytes must match.
    for name, item in files.items():
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('unsafe fixture member')
        path = target / name
        if path.exists() and (path.stat().st_size != item['bytes'] or digest(path) != item['sha256']):
            raise ValueError('existing fixture differs: ' + str(path))
        if source and (digest(source / name) != item['sha256'] or (source / name).stat().st_size != item['bytes']):
            raise ValueError('parent fixture differs: ' + name)
    if cpu_only:
        from storage import cpu_build_admit
        # This step restores CPU fixtures only; it neither creates nor admits a chain.
        cpu_build_admit(sum(item['bytes'] for name,item in files.items() if not (target/name).exists()))
    else:
        admission = precheck()
        if not admission['passed']:
            raise ValueError('storage admission refused: ' + str(admission))
    target.mkdir(parents=True, exist_ok=True)
    if archive:
        with tarfile.open(archive, 'r:gz') as tar:
            for name, item in files.items():
                path = target / name
                if path.exists():
                    continue
                data = tar.extractfile(name).read()
                import hashlib
                if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
                    raise ValueError('archive member differs: ' + name)
                with path.open('xb') as output:
                    output.write(data)
    elif source:
        for name in files:
            if not (target / name).exists():
                os.link(source / name, target / name)
    for name, item in files.items():
        if digest(target / name) != item['sha256']:
            raise ValueError('restored fixture differs: ' + name)
    cases = (target / 'cases.txt').read_text().split()
    if len(cases) != 72 or len(set(cases)) != 72 or not set(cases) <= set(files):
        raise ValueError('fixture list must cover 72 distinct pinned cases')
    return dict(passed=True, device_executed=False, cases=len(cases), files=len(files),
                bytes=sum(x['bytes'] for x in files.values()),
                source=str(source or archive or target), destination=str(target.resolve()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    if os.getpriority(os.PRIO_PROCESS, 0) != 19 or not set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32)):
        raise ValueError('nice19 and helper cores required')
    print(json.dumps(restore(args.source)))
