"""Restore the two unchanged K1 executables from the frozen parent receipt."""
import json,resource,shutil
from build_engine import P,BASE,sha,limits

def main():
    from frozen_inputs import restore
    restore()
    limits()
    parent=json.loads((BASE/'build-receipt.json').read_text())
    for mode in ('gnu-host','device'):
        name=f'build/{mode}/p58-cache-fixtures'
        source=BASE/name;destination=P/name
        assert sha(source)==parent['artifacts'][name],'parent K1 binary changed'
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,destination)
        assert sha(destination)==parent['artifacts'][name]
    limits();print('Both frozen K1 executables restored; none executed')

if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    main()
