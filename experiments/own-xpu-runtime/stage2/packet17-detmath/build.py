"""Reproduce host gates and compile device windows; never execute device code.
The v1 fixture binary only writes under this packet's build tree.
"""
import argparse,gzip,hashlib,json,os,shutil,subprocess,sys,time,shlex
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args,timeout=1800):
 print(' '.join(map(str,args)),flush=True)
 subprocess.run(list(map(str,args)),check=True,timeout=timeout)
def assert_device_link_options(native):
 required={'-fsycl','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt'}
 commands={}
 for path in sorted((native/'CMakeFiles').glob('*/link.txt')):
  tokens=shlex.split(path.read_text())
  target=path.parent.name.removesuffix('.dir')
  compile_flags=path.parent/'flags.make'
  device_compile=compile_flags.is_file() and '-fsycl' in shlex.split(compile_flags.read_text())
  if device_compile or '-fsycl' in tokens or target in ('device-test','census-device'):
   missing=required-set(tokens)
   if missing:raise ValueError(f'{target} link command missing {sorted(missing)}')
   commands[target]=tokens
 expected={'device-test','census-device'}
 for flags in (native/'CMakeFiles').glob('*/flags.make'):
  if '-fsycl' in shlex.split(flags.read_text()):expected.add(flags.parent.name.removesuffix('.dir'))
 if not expected <= commands.keys():
  raise ValueError('missing device target link commands')
 return commands

def verify_reusable_host_hashes():
 r=json.loads((P/'host-hashes-receipt.json').read_text())
 for path,key in [(B/'host-hashes.txt','hashes_sha256'),(P/'detmath.hpp','detmath_sha256'),(B/'host-hashes-generator','binary_sha256')]:
  if sha(path)!=r[key]:raise ValueError(f'host hash input changed: {path}')
 snapshot=P/r.get('source_snapshot','census.cpp')
 if sha(snapshot)!=r['source_sha256']:raise ValueError('host hash source snapshot changed')

def reusable_oracle():
 path=P/'oracle-build-receipt.json'
 if not path.exists() or not (B/'oracle/oracle').exists():return False
 r=json.loads(path.read_text())
 return sha(B/'oracle/oracle')==r['binaries']['oracle'] and all(sha(ROOT/name)==digest for name,digest in r['sources'].items())

def link_precision_control():
 # Deliberate negative control, not a CMake device target or runtime candidate.
 # Re-link the EXACT census-device object with only -fsycl; no recompilation.
 native=B/'native'
 command=assert_device_link_options(native)['census-device'].copy()
 command=[v for v in command if v not in ('-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt')]
 command[command.index('-o')+1]=str(B/'census-plain-link-control')
 subprocess.run(command,cwd=native,check=True,timeout=180)
 (B/'precision-link-control.json').write_text(json.dumps(dict(
  diagnostic_only=True,device_executed=False,command=command,
  object_sha256=sha(native/'CMakeFiles/census-device.dir/census.cpp.o'),
  precise_link=assert_device_link_options(native)['census-device'],
  plain_binary_sha256=sha(B/'census-plain-link-control'),
  precise_binary_sha256=sha(native/'census-device')),indent=2)+'\n')

def prepare_wa_references(jobs):
 fresh=not (B/'wa-reference').exists()
 # Native build includes a HOST_ONLY Intel generator with the original W-A
 # host flags. GNU native libm differs at finite inputs; it is not this twin.
 run([sys.executable,'-B',P/'prepare_wa.py']+(['--precompute'] if fresh else []),timeout=None)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--hashes',action='store_true',help='compute all2^32 exp/log CPU hashes');ap.add_argument('--wa-references',action='store_true',help='precompute W-A CPU references if absent, then seal');ap.add_argument('--native-only',action='store_true',help='rebuild native targets, reuse sealed host gates and oracle');ap.add_argument('--jobs',type=int,default=2);a=ap.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 assert 1<=a.jobs<=2 and not B.is_symlink()
 assert not (B/'device-fault-latch.json').exists() and not list(B.glob('card*-W-*')),'preserve admitted device evidence'
 B.mkdir(exist_ok=True)
 if a.native_only:
  previous=json.loads((P/'build-receipt.json').read_text())
  # Link repair may change the builder/CMake/tests, but not qualified host code.
  for name,digest in previous['hashes'].items():
   if Path(name).suffix in ('.cpp','.hpp') and Path(name).name not in ('census.cpp','wa_storage.hpp','wa_precompute.cpp','wa_verify.cpp') and sha(ROOT/name)!=digest:
    raise ValueError('native-only requires unchanged host sources: '+name)
  verify_reusable_host_hashes()
  if not reusable_oracle():raise ValueError('CPU oracle changed')
  run(['cmake','-S',P,'-B',B/'native','-DCMAKE_CXX_COMPILER=/opt/intel/oneapi/compiler/2026.0/bin/icpx','-DNATIVE=ON'])
  assert_device_link_options(B/'native')
  run(['cmake','--build',B/'native','-j'+str(a.jobs)])
  link_precision_control()
  if a.wa_references:prepare_wa_references(a.jobs)
  run([sys.executable,'-B',P/'seal.py'])
  return
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
  run(['cmake','-S',P,'-B',B/folder,'-DCMAKE_CXX_COMPILER='+shutil.which(compiler)]+(['-DNATIVE=ON'] if folder=='native' else []))
  if folder=='native':assert_device_link_options(B/folder)
  run(['cmake','--build',B/folder,'-j'+str(a.jobs)])
  tag='gnu' if folder=='gnu' else 'icpx'
  run([B/folder/'host-test',B/'fixtures',P/(tag+'-host.json'),'--generate-core'])
  run([B/folder/'host-test',B/'fixtures',P/(tag+'-fresh.json')])
 link_precision_control()
 run([sys.executable,'-B',P/'capture_fixtures.py'])
 run([sys.executable,'-B',P/'test_window.py'])
 if a.hashes:
  started=time.monotonic()
  run([B/'gnu/census-host','host-hashes','32','262144',B/'host-hashes.txt','2'],timeout=3600)
  r=dict(schema='packet17.host-hashes.v2',complete=True,device_executed=False,inputs_per_function=1<<32,chunk=262144,threads=2,elapsed_seconds=time.monotonic()-started,source_sha256=sha(P/'census.cpp'),detmath_sha256=sha(P/'detmath.hpp'),binary_sha256=sha(B/'gnu/census-host'),hashes_sha256=sha(B/'host-hashes.txt'))
  shutil.copyfile(B/'gnu/census-host',B/'host-hashes-generator')
  r['sanity']=json.loads((B/'host-hashes.txt.sanity.json').read_text())
  (P/'host-hashes-receipt.json').write_text(json.dumps(r,indent=2)+'\n')
 if not a.hashes:verify_reusable_host_hashes()
 if not reusable_oracle():run([sys.executable,'-B',P/'build_oracle.py'])
 else:print('Reusing hash-verified CPU oracle; no oracle execution',flush=True)
 if a.wa_references:prepare_wa_references(a.jobs)
 run([sys.executable,'-B',P/'seal.py'])
if __name__=='__main__':main()
