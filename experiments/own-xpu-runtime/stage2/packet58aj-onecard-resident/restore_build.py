"""Restore hash-bound inherited objects, then use build_engine.py to rebuild."""
import json,shutil
from build_engine import P,ROOT,limits,sha

def main():
    limits()
    for r in json.loads((P/'restore-inputs.json').read_text())['files']:
        source=ROOT/r['source'];dest=P/r['destination']
        assert sha(source)==r['sha256']
        if dest.exists():assert sha(dest)==r['sha256']
        else:
            assert shutil.disk_usage('/').free-source.stat().st_size>=27_000_000_000
            dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
    print('Inherited binary inputs verified/restored. Run build_engine.py for the changed entry; reseal only an unstarted packet.')
if __name__=='__main__':main()
