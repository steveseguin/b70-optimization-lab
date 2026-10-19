"""Retain the exact executables so no mutable parent is a restoration dependency."""
import gzip,hashlib,tarfile
from prepare import P,sha,save
def main():
    files={str(f.relative_to(P)):sha(f) for f in (P/'build').rglob('*') if f.is_file()}
    dest=P/'lineage/native-artifacts.tar.gz';assert not dest.exists()
    with dest.open('wb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',mtime=0,compresslevel=6) as gz,tarfile.open(fileobj=gz,mode='w') as tar:
        for name in sorted(files):
            info=tar.gettarinfo(str(P/name),arcname=name);info.uid=info.gid=0;info.uname=info.gname='';info.mtime=0
            with (P/name).open('rb') as source:tar.addfile(info,source)
    with tarfile.open(dest,'r:gz') as tar:
        for name,digest in files.items():
            with tar.extractfile(name) as member:assert hashlib.file_digest(member,'sha256').hexdigest()==digest
    save(P/'native-artifacts.json',dict(archive=str(dest.relative_to(P)),archive_sha256=sha(dest),archive_bytes=dest.stat().st_size,files=files,all_members_rehashed=True,retention='Exact vendored candidate, K1 adapter/core and CPU proof binaries. Required for hash-bound launch without mutable parent or a runtime rebuild. Restore with python3 -B restore_build.py; originals retained.'))
    print(dest.stat().st_size,'archive bytes; all members verified')
if __name__=='__main__':main()
