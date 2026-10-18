"""Offline compiler report for the checked production and candidate TU."""
import gzip,json,os,re,resource,subprocess
from pathlib import Path
import hashlib
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))

def main():
 limits();import sys
 tu=sys.argv[1];out=B/('offline-'+tu);out.mkdir(exist_ok=True)
 evidence=P/'evidence'/('registers-'+tu);evidence.mkdir(parents=True,exist_ok=True)
 compiler=Path('/opt/intel/oneapi/compiler/2026.0/bin/icpx');translator=compiler.parent/'compiler/llvm-spirv'
 source=B/(tu+'.cpp');source.write_bytes((P/(tu+'.cpp')).read_bytes())
 parent=B/'checked'/P.relative_to(ROOT)
 flags=['-I'+str(parent),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),'-fsycl','-fsycl-device-only','-O2','-std=c++20','-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt']
 libraries=[compiler.parent.parent/'lib'/('libsycl-'+n+'.bc') for n in ('crt','complex','complex-fp64','cmath','cmath-fp64','imf','imf-fp64','imf-bf16','fallback-cstring','fallback-complex','fallback-complex-fp64','fallback-cmath','fallback-cmath-fp64','fallback-imf','fallback-imf-fp64','fallback-imf-bf16','itt-user-wrappers','itt-compiler-wrappers','itt-stubs','native-bfloat16')]
 commands=[[str(compiler),*flags,'-MMD','-MF',str(out/'dependencies.d'),'-c',str(source),'-o',str(out/'kernels.bc')],
 [str(compiler.parent/'compiler/llvm-link'),'-only-needed',str(out/'kernels.bc'),*map(str,libraries),'--suppress-warnings','-o',str(out/'linked.bc')],
 [str(compiler.parent/'compiler/sycl-post-link'),'-O2','-spec-const=emulation','-emit-only-kernels-as-entry-points','-ir-output-only',str(out/'linked.bc'),'-o',str(out/'image.bc')],
 [str(translator),'--spirv-ext=+all,-SPV_INTEL_runtime_aligned,-SPV_KHR_untyped_pointers,-SPV_KHR_fma',str(out/'image.bc'),'-o',str(out/'kernels.spv')],
 ['/usr/bin/ocloc','compile','-spirv_input','-file',str(out/'kernels.spv'),'-device','bmg-g31','-options','-ze-fp32-correctly-rounded-divide-sqrt','-out_dir',str(out/'aot')]]
 env={**os.environ,'OMP_NUM_THREADS':'1','OMP_THREAD_LIMIT':'1','IGC_ShaderDumpEnable':'1','IGC_DumpToCustomDir':str(out/'igc'),'IGC_ShowFullVectorsInShaderDumps':'1'}
 for i,cmd in enumerate(commands):
  with (evidence/f'compile-{i}.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,env=env,check=True,timeout=600)
  print('offline stage',i,'PASS',flush=True)
 kernels=[]
 for i,p in enumerate(sorted((out/'igc').glob('*entry_*.asm'))):
  data=p.read_text();name=data.splitlines()[0]
  if not any(n in name for n in ('p49drec','p82rec','p82brec')):continue
  artifact=evidence/f'kernel-{i}.asm.gz';artifact.write_bytes(gzip.compress(p.read_bytes(),mtime=0))
  grf=re.search(r'numGRF=(\d+)',data)
  instructions=re.search(r'//.instCount (\d+)',data)
  kernels.append(dict(name=name,configured_grf=int(grf[1]) if grf else None,spill_metadata=[l for l in data.splitlines()[:50] if l.startswith('//.spill')],scratch_messages=[l for l in data.splitlines() if any(x in l.lower() for x in ('scratch','spill to','fill from')) and not l.lstrip().startswith('//')],static_instructions=int(instructions[1]) if instructions else None,static_load_lines=[l.strip() for l in data.splitlines() if 'load.' in l and not l.lstrip().startswith('//')],assembly=str(artifact.relative_to(ROOT)),sha256=sha(artifact)))
 assert kernels
 import shlex
 dependencies={str(Path(n).resolve().relative_to(ROOT)):sha(n) for n in shlex.split((out/'dependencies.d').read_text().replace('\\\n',' ').split(':',1)[1])}
 save(P/('register-report-'+tu+'.json'),dict(schema='packet82.offline-registers.v1',passed=True,device_executed=False,kernels=kernels,commands=commands,source_sha256=sha(source),sources=dependencies,device_libraries={str(f):sha(f) for f in libraries},max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,scope='Offline BMG-G31; no installed-driver occupancy or physical DRAM counters'))
 print([(r['name'],r['configured_grf'],len(r['static_load_lines'])) for r in kernels],flush=True)
if __name__=='__main__':main()
