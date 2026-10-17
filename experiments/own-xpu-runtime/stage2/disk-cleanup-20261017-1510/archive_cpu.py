"""Archive only the reviewed CPU scratch candidates, verifying every byte first."""
import collections
import hashlib
import json
import os
from pathlib import Path
import tarfile
import time
import sys
from cleanup import HERE, digest, identity, protections

tracked, refs = protections()
groups = collections.defaultdict(list)
selection = (json.loads((HERE / 'cpu-binary-candidates.json').read_text()) if '--binaries' in sys.argv
             else json.loads((HERE / 'candidates.json').read_text())['archive-cpu'])
for row in selection:
    p = Path(row['path'])
    if not p.exists():
        continue
    parts = p.parts
    root = Path(*parts[:parts.index('build') + 2])
    groups[root].append(row)
archives = HERE / 'archives'
archives.mkdir(exist_ok=True)
manifests = HERE / 'archive-manifests'
manifests.mkdir(exist_ok=True)
for root, rows in sorted(groups.items()):
    key = root.parent.parent.name + '--' + root.name
    manifest = manifests / (key + '.json')
    if manifest.exists():
        continue
    # Refuse a whole group if any path is tracked, pinned, changed or shared.
    if any(str(Path(r['path']).resolve()) in tracked | refs or
           identity(Path(r['path']))[4] != 1 or
           identity(Path(r['path']))[2:4] != (r['size'], r['mtime_ns']) for r in rows):
        print('SKIP', key, flush=True)
        continue
    archive = archives / (key + '.tar.gz')
    before = {r['path']: identity(Path(r['path'])) for r in rows}
    with tarfile.open(archive, 'w:gz', compresslevel=1) as tar:
        for row in rows:
            p = Path(row['path'])
            row['sha256'] = digest(p)
            row['member'] = str(p.relative_to(root))
            tar.add(p, arcname=row['member'], recursive=False)
    with tarfile.open(archive, 'r:gz') as tar:
        expected = {r['member']: r for r in rows}
        seen = set()
        for member in tar:
            assert member.isfile()
            row = expected[member.name]
            h = hashlib.sha256()
            stream = tar.extractfile(member)
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                h.update(chunk)
            assert h.hexdigest() == row['sha256'] and member.size == row['size']
            seen.add(member.name)
        assert seen == set(expected)
    assert all(identity(Path(path)) == old for path, old in before.items())
    result = dict(root=str(root), archive=str(archive), archive_sha256=digest(archive),
                  archive_bytes=archive.stat().st_size, archive_allocated_bytes=archive.stat().st_blocks * 512,
                  original_allocated_bytes=sum(r['blocks'] for r in rows),
                  verified_all_members=True, files=rows, time=time.time())
    manifest.write_text(json.dumps(result, indent=2) + '\n')
    with manifest.open() as f:
        os.fsync(f.fileno())
    for row in rows:
        p = Path(row['path'])
        assert identity(p) == before[str(p)]
        p.unlink()
    print('ARCHIVED', key, result['original_allocated_bytes'] - result['archive_allocated_bytes'], flush=True)
