"""Restore exactly the five reused 58ag binaries; never compile or launch."""
import json,os,resource,shutil
from pathlib import Path
from seal import sha,require
P=Path(__file__).resolve().parent
def main():
    require(os.getpriority(os.PRIO_PROCESS,0)==19,'nice19 required')
    require(set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32)),'helper cores required')
    manifest=json.loads((P/'copy-manifest.json').read_text());parent=P.parents[3]/manifest['native_source']
    items=manifest['native_artifacts'];size=sum((parent/n).stat().st_size for n in items)
    require(size<=300_000_000 and shutil.disk_usage('/').free-size>=25_000_000_000,'build/storage limit')
    for leaf,digest in items.items():
        src=parent/leaf;dst=P/leaf;require(sha(src)==digest,'parent binary changed')
        if dst.exists():require(sha(dst)==digest,'local binary changed')
        else:dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    print(json.dumps(dict(passed=True,device_executed=False,build_bytes=size)))
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
