"""Archive closed-run private driver caches; release only after full readback.

Root-operated. No model, device, service, or setting operations.
"""
from pathlib import Path
import argparse, hashlib, json, os, stat, tarfile

HERE = Path(__file__).resolve().parent
ROOT = Path('/home/steve/own-xpu-runtime-results')
ARCHIVE = Path('/mnt/usb-models/own-xpu-runtime-evidence/closed-driver-caches-20261024.tar.gz')
MANIFEST = HERE / 'manifest.json'

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()

def identity(p):
    s = p.stat(follow_symlinks=False)
    assert stat.S_ISREG(s.st_mode), p
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns]

def save(p, data):
    with p.open('x') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    sync_dir(p.parent)

def sync_dir(p):
    fd = os.open(p, os.O_DIRECTORY)
    os.fsync(fd)
    os.close(fd)

def held_identity(f):
    s = os.fstat(f.fileno())
    assert stat.S_ISREG(s.st_mode)
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns]

def open_archive():
    assert ARCHIVE.resolve() == ARCHIVE
    assert ARCHIVE.parent.stat().st_dev == 2050
    return os.fdopen(os.open(ARCHIVE, os.O_RDONLY | os.O_NOFOLLOW), 'rb')

def verify(m, retained):
    stamp = held_identity(retained)
    assert identity(ARCHIVE) == stamp
    h = hashlib.sha256()
    retained.seek(0)
    for block in iter(lambda: retained.read(1 << 20), b''):
        h.update(block)
    assert h.hexdigest() == m['archive_sha256']
    retained.seek(0)
    expected = {r['member']: r for r in m['files']}
    with tarfile.open(fileobj=retained, mode='r:gz') as archive:
        members = archive.getmembers()
        assert len(members) == len(expected)
        assert {x.name for x in members} == set(expected)
        for entry in members:
            row = expected[entry.name]
            assert entry.isfile() and entry.size == row['identity'][2]
            assert hashlib.sha256(archive.extractfile(entry).read()).hexdigest() == row['sha256']
    for row in m['files']:
        assert Path(row['path']).resolve() == Path(row['path'])
        assert identity(Path(row['path'])) == row['identity']
        assert sha(row['path']) == row['sha256']
    assert held_identity(retained) == identity(ARCHIVE) == stamp
    return stamp

def archive_closed():
    assert not MANIFEST.exists() and not ARCHIVE.exists()
    assert Path('/mnt/usb-models').stat().st_dev == 2050
    rows, terminals = [], {}
    for control in sorted(ROOT.glob('gsq-*.control')):
        # The latest failed precision run remains untouched for its audit.
        if control.name == 'gsq-recurrent-f32-a.control':
            continue
        cache, terminal = control / 'ranks/cache', control / 'terminal.json'
        if not cache.is_dir() or not terminal.is_file():
            continue
        assert control.resolve() == control and cache.resolve() == cache
        assert terminal.resolve() == terminal
        closed = json.loads(terminal.read_text())
        if not (closed.get('children_exited') and closed.get('target_descriptors_empty')):
            continue
        terminals[str(terminal)] = sha(terminal)
        for path in sorted(cache.rglob('*')):
            assert not path.is_symlink(), path
            if path.is_file():
                rows.append(dict(path=str(path), member=str(path.relative_to(ROOT)),
                                 identity=identity(path), sha256=sha(path)))
    total = sum(r['identity'][2] for r in rows)
    assert rows and total < 512 << 20
    fs = os.statvfs('/mnt/usb-models')
    assert fs.f_bavail * fs.f_frsize >= (2 << 30) + total + (128 << 20)
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    assert ARCHIVE.resolve() == ARCHIVE and ARCHIVE.parent.stat().st_dev == 2050
    with ARCHIVE.open('xb') as out:
        with tarfile.open(fileobj=out, mode='w:gz') as archive:
            for row in rows:
                assert identity(Path(row['path'])) == row['identity']
                archive.add(row['path'], arcname=row['member'], recursive=False)
        out.flush()
        os.fsync(out.fileno())
    sync_dir(ARCHIVE.parent)
    m = dict(archive=str(ARCHIVE), archive_sha256=sha(ARCHIVE), files=rows,
             terminal_sha256=terminals, raw_bytes=total,
             source_sha256=sha(__file__), released=False,
             restore='Restore archive members beneath /home/steve/own-xpu-runtime-results; original bytes and tar metadata retained, not inode/ctime identities.')
    save(MANIFEST, m)
    with open_archive() as retained:
        verify(m, retained)
    save(HERE / 'verified.json', dict(passed=True, manifest_sha256=sha(MANIFEST),
         archive_sha256=m['archive_sha256'], files=len(rows), raw_bytes=total,
         archive_bytes=ARCHIVE.stat().st_size))

def release():
    m = json.loads(MANIFEST.read_text())
    assert m['source_sha256'] == sha(__file__)
    v = json.loads((HERE / 'verified.json').read_text())
    assert v['passed'] and v['manifest_sha256'] == sha(MANIFEST)
    assert not (HERE / 'released.json').exists()
    assert Path('/mnt/usb-models').stat().st_dev == 2050
    for path, digest in m['terminal_sha256'].items():
        assert sha(path) == digest
    released = []
    with open_archive() as retained:
        # One held FD binds the verified archive through the entire release.
        archive_stamp = verify(m, retained)
        save(HERE / 'release-before.json', dict(manifest_sha256=sha(MANIFEST),
             archive_identity=archive_stamp, files=len(m['files'])))
        for row in m['files']:
            assert identity(ARCHIVE) == held_identity(retained) == archive_stamp
            path = Path(row['path'])
            assert path.resolve() == path
            assert identity(path) == row['identity'] and sha(path) == row['sha256']
            path.unlink()
            fd = os.open(path.parent, os.O_DIRECTORY)
            os.fsync(fd)
            os.close(fd)
            released.append(row['path'])
    save(HERE / 'released.json', dict(passed=True, files=released,
         raw_bytes=m['raw_bytes'], archive_sha256=m['archive_sha256']))

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=['archive', 'release'])
    args = ap.parse_args()
    archive_closed() if args.phase == 'archive' else release()
