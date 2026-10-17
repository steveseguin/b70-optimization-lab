#!/usr/bin/env python3
"""CPU compilation only; never enumerate or execute a device program."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
COMPILER = '/opt/intel/oneapi/compiler/2026.0/bin/icpx'
def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()
def main():
    argparse.ArgumentParser().parse_args()
    allowed=set(range(4,16)) | set(range(20,32))
    if os.getpriority(os.PRIO_PROCESS,0)<19 or not os.sched_getaffinity(0)<=allowed:
        raise SystemExit('run nice -n 19 taskset -c 4-15,20-31 python3 -B build.py')
    out=HERE/'build/device';out.mkdir(parents=True,exist_ok=True)
    base=HERE.parent/'packet45-merged3'
    flags=['-std=c++20','-O2','-fsycl','-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt','-Werror=return-type']
    includes=[base,HERE.parent/'packet2/kernels',HERE.parent/'packet2/loader',HERE.parents[1]/'stage1/packet3-prep/src']
    flags += ['-I'+str(p) for p in includes]
    sources=[HERE/'qsa_bench.cpp',base/'p30_attention.cpp']
    commands=[];dependencies=set()
    for src in sources:
        command=[COMPILER,*flags,'-MM',str(src)]
        result=subprocess.run(command,capture_output=True,text=True)
        if result.returncode: raise RuntimeError(result.stderr)
        import shlex
        for line in result.stdout.replace('\\\n',' ').splitlines():
            if not line.strip() or line.lstrip().startswith('#'): continue
            if ':' not in line: raise ValueError('malformed dependency line')
            dependencies.update(Path(p).resolve() for p in shlex.split(line.split(':',1)[1]))
    closure={str(p.relative_to(ROOT)):sha(p) for p in sorted(dependencies)}
    closure[str((HERE/'build.py').relative_to(ROOT))]=sha(HERE/'build.py')
    command=[COMPILER,*flags,*map(str,sources),'-lcrypto','-lze_loader','-Wl,-rpath,/opt/intel/oneapi/compiler/2026.0/lib','-o',str(out/'qsa-bench')]
    commands.append(command)
    with (out/'build.log').open('w') as f:subprocess.run(command,check=True,stdout=f,stderr=subprocess.STDOUT)
    for path,digest in closure.items():
        if sha(ROOT/path)!=digest: raise ValueError('source changed during build: '+path)
    record=dict(schema='ownrt.packet47.build.v1',passed=True,device_executed=False,completed_utc=datetime.now(timezone.utc).isoformat(),source_hashes=closure,artifacts={'build/device/qsa-bench':sha(out/'qsa-bench')},compiler=COMPILER,flags=flags,commands=commands,compiler_version=subprocess.run([COMPILER,'--version'],capture_output=True,text=True,check=True).stdout)
    (HERE/'build-device.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'passed':True,'device_executed':False,'binary_sha256':record['artifacts']['build/device/qsa-bench']}))
if __name__=='__main__': main()
