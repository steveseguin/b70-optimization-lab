"""Check full member inventory and compare every archive against its source."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tarfile

base = Path('/home/steve/git-archives/staging-consolidation-20261007')
audit = json.loads(Path(__file__).with_name('audit.json').read_text())
records = []
for item in audit['paths']:
    source = Path(item['path'])
    receipt = json.loads((base / (source.name + '-verified.json')).read_text())
    archive = Path(receipt['archive'])
    with archive.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == receipt['archive_sha256']
    archived = {}
    process = subprocess.Popen(['zstd', '-dc', str(archive)], stdout=subprocess.PIPE)
    with tarfile.open(fileobj=process.stdout, mode='r|') as tree:
        for member in tree:
            assert member.isfile() or member.isdir(), member.name
            assert member.name not in archived, member.name
            archived[member.name.rstrip('/')] = ('file', member.size) if member.isfile() else ('dir', 0)
    process.stdout.close()
    assert process.wait() == 0
    actual = {}
    def add(path):
        info = path.lstat()
        assert stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode), str(path)
        if stat.S_ISREG(info.st_mode):
            assert info.st_nlink == 1, str(path)
        actual[str(path.relative_to(source.parent))] = (
            ('file', info.st_size) if stat.S_ISREG(info.st_mode) else ('dir', 0))
    add(source)
    for parent, directories, files in os.walk(source):
        for name in directories + files:
            add(Path(parent) / name)
    assert actual == archived, {'source': str(source),
                                'extra': sorted(set(actual) - set(archived)),
                                'missing': sorted(set(archived) - set(actual))}
    compared = subprocess.run(['tar', '--zstd', '--acls', '--xattrs', '--compare',
                               '-f', str(archive), '-C', str(source.parent)],
                              capture_output=True, text=True)
    assert compared.returncode == 0, compared.stdout + compared.stderr
    files = sum(kind == 'file' for kind, _ in actual.values())
    assert files == item['regular_files']
    records.append({'source': str(source), 'members': len(actual), 'regular_files': files,
                    'complete_inventory_match': True, 'repeated_tar_compare_returncode': 0,
                    'archive_sha256_rechecked': True})
print(json.dumps({'all_verified': True, 'records': records}, indent=2))
