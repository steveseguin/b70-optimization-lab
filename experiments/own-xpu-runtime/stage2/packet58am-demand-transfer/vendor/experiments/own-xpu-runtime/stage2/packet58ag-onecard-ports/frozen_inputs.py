"""Restore historical build/analysis inputs locally, never follow mutable siblings.

The archive is original provenance. Runtime windows do not restore it or read
these historical sources. Frozen parent executable/object binaries remain
hash-bound external inputs; no model payload is opened here.
"""
import hashlib
import json
from pathlib import Path
import tarfile

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
FROZEN = P / 'frozen-inputs/repo'


def relocate(data):
    # Only source/build text is passed here. Keep references to this packet
    # live; every sibling source reference becomes a private snapshot path.
    old = (str(ROOT)+'/experiments/').encode()
    new = (str(FROZEN)+'/experiments/').encode()
    data=data.replace(b'packet58ag-cache-capacity',b'packet58ag-onecard-hcfusion')
    return data.replace(old,new).replace(str(FROZEN/P.relative_to(ROOT)).encode(),str(P).encode())


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def restore():
    manifest = json.loads((P/'lineage/58xb-source-snapshot.json').read_text())
    archive = P/'lineage/58xb-source-snapshot.tar.gz'
    assert sha(archive) == manifest['archive_sha256']
    with tarfile.open(archive, 'r:gz') as tar:
        for member in tar:
            assert member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
            if member.name.startswith('history/'):
                continue
            dest = FROZEN/member.name
            data = tar.extractfile(member).read()
            assert hashlib.sha256(data).hexdigest() == manifest['members'][member.name]
            if dest.suffix in ('.hpp','.h','.cpp','.cc','.py','.make') or dest.name == 'link.txt':
                data = relocate(data)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                dest.write_bytes(data)
            assert sha(dest) == hashlib.sha256(data).hexdigest()
    from input_scope import allowed_inputs
    for name, digest in allowed_inputs().items():
        if '/packet58j-onecard-port/build/' not in name:
            continue
        original = ROOT/name
        assert sha(original) == digest
        dest = FROZEN/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            dest.symlink_to(original)
        assert sha(dest) == digest
    return FROZEN


if __name__ == '__main__':
    restore()
