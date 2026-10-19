"""Restore hash-bound inherited objects, then use build_engine.py to rebuild."""
import json,shutil
from build_engine import P,ROOT,limits,sha

def main():
    limits()
    manifest=json.loads((P/'restore-inputs.json').read_text())
    for r in manifest['files']:
        source=ROOT/r['source'];dest=P/r['destination']
        assert sha(source)==r['sha256']
        if dest.exists():assert sha(dest)==r['sha256']
        else:
            assert shutil.disk_usage('/').free-source.stat().st_size>=27_000_000_000
            dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
    for r in manifest.get('symlinks',[]):
        link=P/r['link']
        if not link.is_symlink():
            assert not link.exists();link.parent.mkdir(parents=True,exist_ok=True);link.symlink_to(r['owned_target'])
        assert link.readlink()==__import__('pathlib').Path(r['owned_target'])
        assert link.resolve().is_relative_to(P) and sha(link)==r['digest']
    print('Inherited binary inputs verified/restored. Run build_engine.py for the changed entry; reseal only an unstarted packet.')
if __name__=='__main__':main()
