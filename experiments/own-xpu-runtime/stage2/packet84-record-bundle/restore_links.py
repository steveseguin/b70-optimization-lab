"""Restore packet84 CPU evidence and pinned parent fixtures; never run a model."""
import hashlib,json,os,tarfile
from pathlib import Path
from build_engine import P,ROOT,B,sha,limits

def main():
    limits()
    from stopped_archive import require_fresh_chain
    require_fresh_chain(B)
    from prepare_chain import main as restore_parent
    restore_parent()
    manifest=P/'evidence/build-retention.json'
    if manifest.exists():
        row=json.loads(manifest.read_text());archive=ROOT/row['archive'];assert sha(archive)==row['sha256']
        with tarfile.open(archive,'r:gz') as tar:
            assert set(tar.getnames())==set(row['members'])
            for item in tar:
                assert item.isfile() and not Path(item.name).is_absolute() and '..' not in Path(item.name).parts
                data=tar.extractfile(item).read();expected=row['members'][item.name]
                assert len(data)==expected['bytes'] and hashlib.sha256(data).hexdigest()==expected['sha256']
                target=B/item.name
                if target.exists():assert sha(target)==expected['sha256']
                else:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    fixtures={sha(f):f for f in (P/'evidence').glob('composition-*.bin.gz')}
    for view in (P/'selections').iterdir():
        seal=json.loads((view/'screen-seal.json').read_text())
        for leaf,digest in seal['fixture_files'].items():
            target=view/leaf
            if not target.exists():os.link(fixtures[digest],target)
            assert sha(target)==digest
        for leaf,digest in seal['artifacts'].items():
            source=P/leaf;target=view/leaf
            assert sha(source)==digest,'rebuild pinned local binaries first: '+str(source)
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():os.link(source,target)
            assert sha(target)==digest
if __name__=='__main__':main()
