#!/usr/bin/env python3
"""Restore only byte-identical copied native artifacts; never compile or launch."""
import json
import os
from pathlib import Path
import shutil
from seal import sha, require

P=Path(__file__).resolve().parent


def main():
    require(os.getpriority(os.PRIO_PROCESS,0)==19, 'nice19 required')
    require(set(os.sched_getaffinity(0)) <= set(range(8,16)) | set(range(24,32)), 'helper cores required')
    manifest=json.loads((P/'copy-manifest.json').read_text())
    items={n:h for n,h in manifest.items() if '/build/' in n}
    size=sum((P.parents[3]/n).stat().st_size for n in items)
    require(size<=150_000_000 and shutil.disk_usage(P).free-size>=8_000_000_000, 'build/storage bound')
    for n,h in items.items():
        src=P.parents[3]/n; dst=P/'build'/n.split('/build/',1)[1]
        require(sha(src)==h, 'original binary changed: '+n)
        if dst.exists(): require(sha(dst)==h, 'local binary changed')
        else: dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
    print(json.dumps(dict(passed=True,device_executed=False,build_bytes=size)))


if __name__=='__main__': main()
