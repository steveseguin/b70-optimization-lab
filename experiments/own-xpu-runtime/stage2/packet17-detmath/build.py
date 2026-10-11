"""Reproduce host gates and compile device windows; never execute device code.
The v1 fixture binary only writes under this packet's build tree.
"""
import argparse,gzip,hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args,timeout=1800):
 print(' '.join(map(str,args)),flush=True)
 subprocess.run(list(map(str,args)),check=True,timeout=timeout)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--hashes',action='store_true',help='compute all2^32 exp/log CPU hashes');ap.add_argument('--jobs',type=int,default=2);a=ap.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 assert 1<=a.jobs<=2 and not B.is_symlink()
 assert not (B/'device-fault-latch.json').exists() and not list(B.glob('card*-W-*')),'preserve admitted device evidence'
 B.mkdir(exist_ok=True)
 run([sys.executable,'-B',P/'generate_rope.py'])
 if not (B/'fixtures').exists():
  run([sys.executable,'-B',P.parent/'packet15-nongemv/fixtures.py','--output',B/'fixtures'])
 # Recreate the frozen v1 GNU bytes independently in this packet, without writes
 # to packet15 or its build. Keep native fixtures immutable for v2 comparisons.
 v1=B/'v1fixtures';v1.mkdir(exist_ok=True)
 for src in (B/'fixtures').glob('*.fixture'):
  dest=v1/src.name
  if not dest.exists():dest.symlink_to(src.resolve())
 shutil.copyfile(B/'fixtures/cases.txt',v1/'cases.txt')
 run(['g++','-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DHOST_ONLY',P.parent/'packet15-nongemv/runner.cpp','-o',B/'v1-host'])
 run([B/'v1-host',v1,B/'v1-host.json','--generate-core'])
 for compiler,folder in [('g++','gnu'),('/opt/intel/oneapi/compiler/2026.0/bin/icpx','native')]:
  run(['cmake','-S',P,'-B',B/folder,'-DCMAKE_CXX_COMPILER='+compiler]+(['-DNATIVE=ON'] if folder=='native' else []))
  run(['cmake','--build',B/folder,'-j'+str(a.jobs)])
  tag='gnu' if folder=='gnu' else 'icpx'
  run([B/folder/'host-test',B/'fixtures',P/(tag+'-host.json'),'--generate-core'])
  run([B/folder/'host-test',B/'fixtures',P/(tag+'-fresh.json')])
 run([sys.executable,'-B',P/'capture_fixtures.py'])
 run([sys.executable,'-B',P/'test_window.py'])
 if a.hashes:
  started=time.monotonic()
  run([B/'gnu/census-host','host-hashes','32','262144',B/'host-hashes.txt','2'],timeout=3600)
  r=dict(schema='packet17.host-hashes.v2',complete=True,device_executed=False,inputs_per_function=1<<32,chunk=262144,threads=2,elapsed_seconds=time.monotonic()-started,source_sha256=sha(P/'census.cpp'),detmath_sha256=sha(P/'detmath.hpp'),binary_sha256=sha(B/'gnu/census-host'),hashes_sha256=sha(B/'host-hashes.txt'))
  shutil.copyfile(B/'gnu/census-host',B/'host-hashes-generator')
  r['sanity']=json.loads((B/'host-hashes.txt.sanity.json').read_text())
  (P/'host-hashes-receipt.json').write_text(json.dumps(r,indent=2)+'\n')
 run([sys.executable,'-B',P/'build_oracle.py'])
 run([sys.executable,'-B',P/'seal.py'])
if __name__=='__main__':main()
