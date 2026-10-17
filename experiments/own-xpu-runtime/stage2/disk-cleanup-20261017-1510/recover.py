"""Find byte-identical retained copies; never fabricate historical receipts."""
import collections
import hashlib
import json
from pathlib import Path
import shutil
from cleanup import HERE, digest

targets = {}
old = json.loads((HERE.parent / 'sanitizer-archive-manifest-20261017.json').read_text())
for packet, archive in old['archives'].items():
    for name, (sha, size) in archive['members'].items():
        targets[packet + '/build/' + name] = dict(sha256=sha, size=size)
for row in json.loads((HERE / 'overbroad-sanitizer-removals.json').read_text()):
    targets[row['path']] = dict(sha256=row['sha256'], size=row['size'])
need = collections.defaultdict(set)
for t in targets.values():
    need[t['size']].add(t['sha256'])
blobs = HERE / 'recovered-blobs'
blobs.mkdir(exist_ok=True)
found = {p.name: str(p) for p in blobs.iterdir()}
inventory = json.loads((HERE / 'inventory.json').read_text())
seen = set()
for row in inventory:
    if row['size'] not in need or not (need[row['size']] - found.keys()):
        continue
    p = Path(row['path'])
    if not p.exists() or p.is_symlink():
        continue
    s = p.stat()
    key = (s.st_dev, s.st_ino)
    if key in seen:
        continue
    seen.add(key)
    sha = digest(p)
    if sha in need[row['size']] and sha not in found:
        destination = blobs / sha
        shutil.copyfile(p, destination)
        assert digest(destination) == sha
        found[sha] = str(p)
results = []
for path, target in targets.items():
    results.append(dict(path=path, **target, recovered=target['sha256'] in found,
                        source=found.get(target['sha256'])))
(HERE / 'recovery-manifest.json').write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps(dict(targets=len(results), recovered=sum(r['recovered'] for r in results),
                      unique_blobs=len(found), unresolved=sum(not r['recovered'] for r in results))), flush=True)
