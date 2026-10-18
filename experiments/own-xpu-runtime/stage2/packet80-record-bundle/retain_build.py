"""Retain exact CPU source/receipt/log bytes; no cleanup or external writes."""
import gzip,hashlib,io,json,tarfile
from build_engine import P,ROOT,B,sha,save,limits

def main():
    limits();members={};paths=set()
    for f in [P/'build-device-receipt.json',*(P/'evidence').glob('*.json')]:
        row=json.loads(f.read_text())
        for rel in row.get('sources',{}):
            source=ROOT/rel
            if source.is_relative_to(B) and source.is_file() and not source.is_symlink():paths.add(source)
    for f in B.rglob('*'):
        if f.is_file() and not f.is_symlink() and f.suffix in ('.cpp','.hpp','.json','.jsonl','.log','.txt','.tsv','.d'):
            paths.add(f)
    dest=P/'evidence/build-sources.tar.gz'
    with dest.open('wb') as raw:
        with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as stream:
            with tarfile.open(fileobj=stream,mode='w|') as archive:
                for f in sorted(paths):
                    data=f.read_bytes();name=str(f.relative_to(B));info=tarfile.TarInfo(name);info.size=len(data);info.mtime=0;info.mode=0o644
                    archive.addfile(info,io.BytesIO(data));members[name]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    with tarfile.open(dest,'r:gz') as archive:
        assert set(archive.getnames())==set(members)
        for item in archive:
            data=archive.extractfile(item).read();expected=members[item.name]
            assert len(data)==expected['bytes'] and hashlib.sha256(data).hexdigest()==expected['sha256']
    save(P/'evidence/build-retention.json',dict(passed=True,device_executed=False,archive=str(dest.relative_to(ROOT)),sha256=sha(dest),bytes=dest.stat().st_size,members=members,
        reason='Exact production-shape allocation receipts, generated test sources, checked compiler mirror, commands and logs needed to replay seals; native binaries remain local and reproducible from pinned parent objects. No originals removed.',restore='python3 -B <packet>/restore_links.py; reads only this archive and pinned parents; no device execution'))
    print(len(members),'members verified',dest.stat().st_size,'compressed bytes')
if __name__=='__main__':main()
