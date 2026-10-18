"""Restore only hash-bound frozen K1 executables, preserving executable mode."""
import json,os,shutil,stat
from pathlib import Path
from build_engine import P,ROOT,sha,limits

def main():
    limits();manifest=json.loads((P/'copy-manifest.json').read_text())
    for mode in ('gnu-host','device'):
        name=f'build/{mode}/p58-cache-fixtures'
        src=P.parent/'packet58p-onecard-record'/name;dest=P/name
        assert sha(src)==manifest[str(src.relative_to(ROOT))]
        if dest.exists():assert sha(dest)==sha(src)
        else:dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
        os.chmod(dest,stat.S_IMODE(src.stat().st_mode));assert os.access(dest,os.X_OK)
    limits()
if __name__=='__main__':main()
