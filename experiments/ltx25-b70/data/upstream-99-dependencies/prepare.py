#!/usr/bin/env python3
"""Extract only frozen verified wheels; never invoke pip or package setup code."""
import base64
import csv
import hashlib
import importlib.metadata as md
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import urllib.request
import zipfile
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parent
OVERLAY = ROOT / 'site-packages'
LIMIT = 600 * 1024**2

def sha(data):
    return hashlib.sha256(data).hexdigest()

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o644)

def usage():
    return sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())

def main():
    assert shutil.disk_usage(ROOT).free >= 55 * 1024**3, '55 GiB disk admission'
    assert not OVERLAY.exists() and not (ROOT / 'receipt.json').exists(), 'new output only'
    plan = json.loads((ROOT / 'dependency-plan.json').read_text())
    assert len(plan['wheels']) == 12
    assert plan['download_bytes'] + plan['expanded_bytes'] < LIMIT
    baseline = [Path(sys.executable).resolve()]
    torch = md.distribution('torch').locate_file('torch')
    baseline += [torch / '__init__.py', torch / '_inductor/config.py']
    before = {str(p): sha(p.read_bytes()) for p in baseline}
    wheels, files = {}, {}
    for row in plan['wheels']:
        assert shutil.disk_usage(ROOT).free >= 50 * 1024**3 + LIMIT
        p = ROOT / row['filename']
        if not p.exists():
            assert row['url'].startswith('https://files.pythonhosted.org/packages/')
            with urllib.request.urlopen(row['url'], timeout=120) as stream:
                data = stream.read(row['download_bytes'] + 1)
            assert len(data) == row['download_bytes'] and sha(data) == row['sha256'], row['filename']
            write(p, data)
        raw = p.read_bytes()
        assert len(raw) == row['download_bytes'] and sha(raw) == row['sha256']
        wheels[p.name] = dict(sha256=sha(raw), bytes=len(raw), url=row['url'])
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = z.namelist()
            assert len(names) == len(set(names)), 'duplicate ZIP member'
            records = [x for x in names if x.endswith('.dist-info/RECORD')]
            assert len(records) == 1
            record = {r[0]: r[1:] for r in csv.reader(io.StringIO(z.read(records[0]).decode()))}
            assert sum(i.file_size for i in z.infolist()) == row['expanded_bytes']
            for item in z.infolist():
                rel = PurePosixPath(item.filename)
                assert rel.parts and not rel.is_absolute() and '..' not in rel.parts and '\\' not in item.filename
                assert str(rel) == item.filename.rstrip('/')
                assert not stat.S_ISLNK(item.external_attr >> 16), 'symlink ZIP member'
                assert not any(p.endswith('.data') for p in rel.parts), 'wheel relocation unsupported'
                assert not any(p in ('sitecustomize.py', 'usercustomize.py', '__pycache__') for p in rel.parts)
                assert not item.filename.endswith(('.pth', '.pyc'))
                if item.is_dir():
                    continue
                data = z.read(item)
                sig, size = record[item.filename]
                if item.filename != records[0]:
                    assert sig == 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('=')
                    assert int(size) == len(data)
                assert item.filename not in files, 'cross-wheel file collision'
                files[item.filename] = sha(data)
                write(OVERLAY / item.filename, data)
        assert usage() < LIMIT
    # Metadata only: no package imports, target code or entrypoints executed.
    overlay_dists = list(md.distributions(path=[str(OVERLAY)]))
    packages = {canonicalize_name(d.metadata['Name']): d.version for d in overlay_dists}
    expected = {canonicalize_name(r['name']): r['version'] for r in plan['wheels']}
    assert packages == expected and len(overlay_dists) == 12
    baseline_dists = {canonicalize_name(d.metadata['Name']): d for d in md.distributions()}
    active = dict(baseline_dists)
    active.update({canonicalize_name(d.metadata['Name']): d for d in overlay_dists})
    closure = []
    for d in overlay_dists:
        for text in d.requires or []:
            req = Requirement(text)
            if req.marker and not req.marker.evaluate({'extra': ''}):
                continue
            dep = active[canonicalize_name(req.name)]
            assert dep.version in req.specifier, text
            closure.append(dict(parent=d.metadata['Name'], requirement=text, version=dep.version,
                                metadata_path=str(dep._path), metadata_sha256=sha(dep.read_text('METADATA').encode())))
    assert before == {str(p): sha(p.read_bytes()) for p in baseline}, 'baseline changed'
    receipt = dict(schema='ltx.upstream99.dependencies.v1', status='ready',
                   upstream_commit=plan['upstream_commit'], overlay_root=str(OVERLAY), files=files,
                   packages=packages, requirements_sha256=plan['requirements_sha256'],
                   baseline_python=str(Path(sys.executable).absolute()), baseline_runtime_sha256=before,
                   wheels=wheels, dependency_closure=closure, download_bytes=plan['download_bytes'],
                   expanded_bytes=plan['expanded_bytes'], actual_artifact_bytes=usage(),
                   plan_sha256=sha((ROOT / 'dependency-plan.json').read_bytes()),
                   preparer_sha256=sha(Path(__file__).read_bytes()), package_imports_executed=False,
                   runtime_qualified=False)
    write(ROOT / 'receipt.json', (json.dumps(receipt, indent=2, sort_keys=True) + '\n').encode())
    for p in [*sorted((p for p in OVERLAY.rglob('*') if p.is_dir()), reverse=True), OVERLAY, ROOT]:
        fd = os.open(p, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
    print(json.dumps({k: receipt[k] for k in ('status', 'packages', 'download_bytes', 'expanded_bytes', 'actual_artifact_bytes')}))

if __name__ == '__main__':
    main()
