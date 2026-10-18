#!/usr/bin/env python3
"""Copy the two sealed frozen binaries after rebuilding 58j if they are absent."""
from pathlib import Path
import hashlib
import json
import os
import shutil
P=Path(__file__).resolve().parent

def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    parent=json.loads((P/'parent-build-receipt.json').read_text())
    names=('build/device/own-rt-iq3','build/device/p58-cache-fixtures')
    def sha(p):
        with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
    for name in names:
        source=P.parent/'packet58j-onecard-port'/name
        assert sha(source)==parent['artifacts'][name], 'frozen source binary differs'
    size=sum((P.parent/'packet58j-onecard-port'/name).stat().st_size for name in names)
    assert size<=150_000_000 and shutil.disk_usage(P).free-size>=8_000_000_000
    for name in names:
        source=P.parent/'packet58j-onecard-port'/name; target=P/name
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert sha(target)==parent['artifacts'][name]
        else:shutil.copy2(source,target)
    print(json.dumps(dict(passed=True,device_executed=False,build_bytes=size)))
if __name__=='__main__':main()
