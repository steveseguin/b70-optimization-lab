"""Offline compiler report for the checked production and candidate TU."""
import gzip,json,os,re,resource,subprocess
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
def main():
 limits();import sys
 tu=sys.argv[1];out=B/('offline-'+tu);out.mkdir(exist_ok=False)
 evidence=P/'evidence'/('registers-'+tu);evidence.mkdir(parents=True,exist_ok=True)
 compiler=Path('/opt/intel/oneapi/compiler/2026.0/bin/icpx');translator=compiler.parent/'compiler/llvm-spirv'
 source=B/'checked'/P.relative_to(ROOT)/(tu+'.cpp')
 flags=['-fsycl','-fsycl-device-only','-O2','-std=c++20','-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt']
 commands=[[str(compiler),*flags,'-c',str(source),'-o',str(out/'kernels.bc')],
 [str(translator),'--spirv-ext=+all,-SPV_INTEL_runtime_aligned,-SPV_KHR_untyped_pointers',str(out/'kernels.bc'),'-o',str(out/'kernels.spv')],
 ['/usr/bin/ocloc','compile','-spirv_input','-file',str(out/'kernels.spv'),'-device','bmg-g31','-out_dir',str(out/'aot')]]
 env={**os.environ,'OMP_NUM_THREADS':'1','OMP_THREAD_LIMIT':'1','IGC_ShaderDumpEnable':'1','IGC_DumpToCustomDir':str(out/'igc'),'IGC_ShowFullVectorsInShaderDumps':'1'}
 for i,cmd in enumerate(commands):
  with (evidence/f'compile-{i}.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,env=env,check=True,timeout=600)
  print('offline stage',i,'PASS',flush=True)
 kernels=[]
 for i,p in enumerate(sorted((out/'igc').glob('*entry_*.asm'))):
  data=p.read_text();name=data.splitlines()[0]
  if not any(n in name for n in ('p73','p65','p60','p49dvirtual')):continue
  artifact=evidence/f'kernel-{i}.asm.gz';artifact.write_bytes(gzip.compress(p.read_bytes(),mtime=0))
  grf=re.search(r'numGRF=(\d+)',data)
  instructions=[l for l in data.splitlines() if re.match(r'^\s*\([A-Za-z0-9]',l)]
  kernels.append(dict(name=name,configured_grf=int(grf[1]) if grf else None,spill_metadata=[l for l in data.splitlines()[:50] if l.startswith('//.spill')],scratch_messages=[l for l in data.splitlines() if 'scratch' in l.lower() and not l.lstrip().startswith('//')],static_instructions=len(instructions),static_load_lines=[l.strip() for l in data.splitlines() if 'load.' in l and not l.lstrip().startswith('//')],assembly=str(artifact.relative_to(ROOT)),sha256=sha(artifact)))
 assert kernels
 save(P/('register-report-'+tu+'.json'),dict(schema='packet73.offline-registers.v1',passed=True,device_executed=False,kernels=kernels,commands=commands,source_sha256=sha(source),max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,scope='Offline BMG-G31; no installed-driver occupancy or physical DRAM counters'))
 print([(r['name'],r['configured_grf'],len(r['static_load_lines'])) for r in kernels],flush=True)
if __name__=='__main__':main()
