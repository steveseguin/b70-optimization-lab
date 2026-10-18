"""Archive packet86's own superseded seals byte-for-byte, then create fresh ones."""
import hashlib,json,shutil,tarfile
from build_engine import P,sha,save,limits

def main():
    limits();root=P/'compat';files=sorted(f for f in root.rglob('*') if f.is_file())
    inventory={str(f.relative_to(P)):sha(f) for f in files}
    digest=hashlib.sha256(json.dumps(inventory,sort_keys=True).encode()).hexdigest()
    archive=P/'evidence'/('superseded-seals-'+digest[:16]+'.tar.gz')
    if not archive.exists():
        with tarfile.open(archive,'w:gz') as t:t.add(root,arcname='compat')
    with tarfile.open(archive,'r:gz') as t:
        for name,h in inventory.items():
            with t.extractfile(name) as f:
                assert hashlib.file_digest(f,'sha256').hexdigest()==h,name
    save(archive.with_suffix('.manifest.json'),dict(archive_sha256=sha(archive),verified_members=inventory,reason='retain original diagnostic seals before collector/report fixes'))
    # Only our generated views; all unique bytes verified recoverable above.
    shutil.rmtree(root)
    import seal
    seal.main()
if __name__=='__main__':main()
