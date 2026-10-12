#!/usr/bin/env python3
"""CPU-only compile/link; no produced executable is ever invoked here."""
import argparse, hashlib, json, os, resource, subprocess, time, shutil
from pathlib import Path
P=Path(__file__).resolve().parent
B=P/'build'
IC='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
FLAGS=['-std=c++20','-O2','-Werror=return-type','-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt','-fsycl']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',required=True);ap.add_argument('--output',required=True);ap.add_argument('--define',action='append',default=[]);a=ap.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
 B.mkdir(exist_ok=True)
 if a.output=='p39-k0':
  if a.source!='k0.cpp':raise ValueError('K0 source shim expected')
  timing=json.loads((P/'p39-timing-build.json').read_text())
  if timing['returncode'] or sha(B/'p39-timing')!=timing['binary_sha256']:raise ValueError('timing build identity mismatch')
  shutil.copy2(B/'p39-timing',B/'p39-k0')
  receipt=dict(device_executed=False,returncode=0,binary_sha256=sha(B/'p39-k0'),identical_to='p39-timing',runtime_argument='--compile-smoke',compile_and_link_precision=FLAGS,copy_not_separate_compile=True)
  (P/'p39-k0-build.json').write_text(json.dumps(receipt,indent=2)+'\n');print('p39-k0',receipt['binary_sha256']);return
 (B/'tmp-native').mkdir(exist_ok=True);(B/'spv').mkdir(exist_ok=True)
 os.environ['TMPDIR']=str(B/'tmp-native')
 includes=[P,P.parent/'packet29-merged',P.parent/'packet2/kernels',P.parent/'packet2/loader',P.parents[1]/'stage1/packet3-prep/src']
 source=P/a.source;output=B/a.output
 argv=[IC,*FLAGS,*['-D'+v for v in a.define],*['-I'+str(v) for v in includes],str(source),'-o',str(output),'-fsycl-dump-device-code='+str(B/'spv')]
 t=time.monotonic()
 with (B/(a.output+'-build.log')).open('w') as log:r=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT)
 receipt=dict(device_executed=False,argv=argv,returncode=r.returncode,seconds=time.monotonic()-t,source_sha256=sha(source),compile_and_link_precision=FLAGS)
 if r.returncode==0:receipt['binary_sha256']=sha(output)
 (P/(a.output+'-build.json')).write_text(json.dumps(receipt,indent=2)+'\n')
 if r.returncode:raise RuntimeError(str(B/(a.output+'-build.log')))
 print(a.output,receipt['binary_sha256'],flush=True)
if __name__=='__main__':main()
