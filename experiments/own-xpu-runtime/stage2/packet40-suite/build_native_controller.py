#!/usr/bin/env python3
"""Serial CPU-only controller sanitizer builds; all compiler scratch is packet-local."""
import argparse, hashlib, json, os, subprocess
from pathlib import Path
P=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--llvm',type=Path,default=Path('/opt/intel/oneapi/compiler/2026.0/bin/compiler/clang++'));a=parser.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
    tmp=P/'build/tmp';tmp.mkdir(parents=True,exist_ok=True);env=dict(os.environ,TMPDIR=str(tmp))
    rows=[]
    for source,stem in [('native_controller_test.cpp','native-controller'),('native_mailbox_fault_test.cpp','native-mailbox-fault')]:
        for suffix,compiler,flags in [('test','g++',['-O2']),('asan','g++',['-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer']),('tsan-llvm22',str(a.llvm),['-O1','-g','-fsanitize=thread','-fno-omit-frame-pointer'])]:
            from storage import admit
            admit(100_000_000)
            name=stem+'-'+suffix;binary=P/'build'/name
            cmd=['nice','-n','19','ionice','-c','3',compiler,'-std=c++20',*flags,'-fno-fast-math','-ffp-contract=off','-pthread',str(P/source),'-o',str(binary)]
            subprocess.run(cmd,check=True,timeout=300,env=env)
            rows.append(dict(binary=str(binary.relative_to(P)),sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),command=cmd,environment={'OMP_NUM_THREADS':'2','TMPDIR':str(tmp)},compile_and_link_same_invocation=True,source_sha256={s:hashlib.sha256((P/s).read_bytes()).hexdigest() for s in ([source,'native_controller.hpp']+(['native_controller_test.cpp'] if source=='native_mailbox_fault_test.cpp' else []))}))
    receipt=dict(device_executed=False,binaries=rows,precision_flags_on_compile_and_link=True,serial_compile_jobs=1)
    (P/'native-build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':main()
