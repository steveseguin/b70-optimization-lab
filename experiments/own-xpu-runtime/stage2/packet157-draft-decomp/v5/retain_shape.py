"""Retain and rehash every generated full-shape output before dropping scratch."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
from p157_v5_build_engine import P, B, ROOT, sha, save, limits

def retain(directory):
    directory=Path(directory).resolve()
    assert directory.parent==B/'full-shape' and (directory/'result.json').is_file()
    assert json.loads((directory/'result.json').read_text())['passed'] is True
    files={str(p.relative_to(directory)):sha(p) for p in directory.rglob('*') if p.is_file()}
    temporary=P/'evidence/full-shape-scratch.tar.gz'
    with tarfile.open(temporary,'w:gz') as archive:
        for name in sorted(files):archive.add(directory/name,arcname=name,recursive=False)
    with tarfile.open(temporary,'r:gz') as archive:
        assert set(archive.getnames())==set(files)
        for name,digest in files.items():
            assert hashlib.sha256(archive.extractfile(name).read()).hexdigest()==digest
    digest=sha(temporary);dest=P/'evidence'/('shape-'+digest+'.tar.gz')
    temporary.replace(dest)
    result=dict(path=str(dest.relative_to(ROOT)),sha256=digest,members=len(files),
                original_bytes=sum((directory/name).stat().st_size for name in files),
                archive_bytes=dest.stat().st_size,all_original_bytes_verified=True)
    shutil.rmtree(directory)
    return result

if __name__=='__main__':
    limits()
    rows=[]
    for directory in sorted((B/'full-shape').iterdir()):
        if directory.is_dir() and (directory/'result.json').exists():rows.append(retain(directory))
    save(P/'evidence/preparation-scratch-retention.json',dict(passed=True,archives=rows))
