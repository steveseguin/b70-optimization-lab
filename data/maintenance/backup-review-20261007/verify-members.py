"""Compare every archived member name to the frozen NUL selection."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tarfile

archive, selection = sys.argv[1:]
data = Path(selection).read_bytes()
names = [p.decode() for p in data.split(b'\0') if p]
expected = set(names)
assert len(names) == len(expected)
seen = set()
process = subprocess.Popen(['zstd', '-dc', archive], stdout=subprocess.PIPE)
with tarfile.open(fileobj=process.stdout, mode='r|') as stream:
    for member in stream:
        name = member.name.rstrip('/')
        assert name in expected and name not in seen, name
        assert member.isfile() or member.isdir() or member.issym(), name
        seen.add(name)
process.stdout.close()
assert process.wait() == 0
assert seen == expected, f'Missing {len(expected-seen)} selected members'
print(json.dumps({'complete_members_match': True, 'members': len(seen),
                  'selection_sha256': hashlib.sha256(data).hexdigest()}))
