"""Check archived tracked files against immutable Git blob IDs, ignoring tar times."""
import hashlib
import subprocess
import sys
import tarfile

archive, commit = sys.argv[1:]
expected = {}
for row in subprocess.check_output(['git', 'ls-tree', '-rz', commit]).split(b'\0'):
    if not row:
        continue
    info, path = row.split(b'\t', 1)
    mode, kind, identity = info.decode().split()
    assert kind == 'blob', 'Submodules require separate preservation: ' + repr(path)
    expected[path.decode()] = (mode, identity)
seen = set()
with tarfile.open(archive, 'r|') as stream:
    for member in stream:
        if member.isdir():
            continue
        assert member.name not in seen and member.name in expected, member.name
        mode, identity = expected[member.name]
        if mode == '120000':
            assert member.issym(), member.name
            content = member.linkname.encode()
            digest = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
        else:
            assert member.isfile(), member.name
            assert bool(member.mode & 0o111) == (mode == '100755'), member.name
            digest = hashlib.sha1(b'blob ' + str(member.size).encode() + b'\0')
            with stream.extractfile(member) as content:
                for chunk in iter(lambda: content.read(8*1024*1024), b''):
                    digest.update(chunk)
            digest = digest.hexdigest()
        assert digest == identity, member.name
        seen.add(member.name)
assert seen == set(expected), 'Archive omits tracked paths'
print(f'{len(seen)} archived files match Git blob identities at {commit}')
