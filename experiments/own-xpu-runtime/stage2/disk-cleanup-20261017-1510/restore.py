"""Restore a verified scratch archive into a NEW destination, without running it."""
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tarfile

here = Path(__file__).resolve().parent
key, destination = sys.argv[1:]
destination = Path(destination)
assert not destination.exists(), 'Choose a new destination; never overwrite active work.'
with gzip.open(here / 'archive-manifests.json.gz', 'rt') as f:
    record = json.load(f)[key]
archive = Path(record['archive'])
assert hashlib.sha256(archive.read_bytes()).hexdigest() == record['archive_sha256']
destination.mkdir(parents=True)
with tarfile.open(archive, 'r:gz') as tar:
    for row in record['files']:
        member = row['member']
        relative = Path(Path(row['path']).name if member == '.' else member)
        assert not relative.is_absolute() and '..' not in relative.parts
        data = tar.extractfile(member).read()
        assert len(data) == row['size']
        assert hashlib.sha256(data).hexdigest() == row['sha256']
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as f:
            f.write(data)
        target.chmod(tar.getmember(member).mode)
print('Verified and restored', len(record['files']), 'files into', destination)
