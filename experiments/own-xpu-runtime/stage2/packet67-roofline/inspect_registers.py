#!/usr/bin/env python3
"""Offline actual-TU Xe2 compilation; no native device or model execution."""
import gzip,json,os,re,resource,subprocess,shutil
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
def main():
 limits();resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 compiler=Path('/opt/intel/oneapi/compiler/2026.0/bin/icpx');translator=compiler.parent/'compiler/llvm-spirv'
 flags=['-fsycl','-fsycl-device-only','-O2','-std=c++20','-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt']
 kernels=[];commands=[];sources={}
 for stem in ('p60_submit','p49d_submit'):
  require_free=shutil.disk_usage(P).free;assert require_free>=10*1024**3
  out=B/('offline-'+stem);out.mkdir(exist_ok=False);evidence=P/'evidence/registers'/stem;evidence.mkdir(parents=True,exist_ok=True)
  source=B/'checked'/P.relative_to(ROOT)/(stem+'.cpp');sources[str(source.relative_to(ROOT))]=sha(source)
  cmds=[[str(compiler),*flags,'-c',str(source),'-o',str(out/'kernels.bc')],
   [str(translator),'--spirv-ext=+all,-SPV_INTEL_runtime_aligned,-SPV_KHR_untyped_pointers',str(out/'kernels.bc'),'-o',str(out/'kernels.spv')],
   ['/usr/bin/ocloc','compile','-spirv_input','-file',str(out/'kernels.spv'),'-device','bmg-g31','-out_dir',str(out/'aot')]]
  env={**os.environ,'OMP_NUM_THREADS':'1','OMP_THREAD_LIMIT':'1','IGC_ShaderDumpEnable':'1','IGC_DumpToCustomDir':str(out/'igc'),'IGC_ShowFullVectorsInShaderDumps':'1'}
  for i,cmd in enumerate(cmds):
   with (evidence/f'compile-{i}.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,env=env,check=True,timeout=600)
   commands.append(cmd);print(stem,'offline stage',i,'PASS',flush=True)
  for i,p in enumerate(sorted((out/'igc').glob('*entry_*.asm'))):
   data=p.read_text();name=data.splitlines()[0]
   if not any(x in name for x in ('p67','p60','RecurrenceKernel')):continue
   artifact=evidence/f'kernel-{i}.asm.gz';artifact.write_bytes(gzip.compress(p.read_bytes(),mtime=0));grf=re.search(r'numGRF=(\d+)',data)
   kernels.append(dict(name=name,configured_grf=int(grf[1]) if grf else None,spill_metadata=[l for l in data.splitlines()[:40] if l.startswith('//.spill')],scratch_messages=[l for l in data.splitlines() if 'scratch' in l.lower() and not l.lstrip().startswith('//')],assembly=str(artifact.relative_to(ROOT)),sha256=sha(artifact)))
  # Only generated offline scratch; retained assemblies and exact commands rebuild it.
  shutil.rmtree(out)
 assert any('p67hc' in k['name'] for k in kernels) and sum('p67rec' in k['name'] for k in kernels)==2
 save(P/'register-report.json',dict(schema='packet67.offline-registers.v1',passed=True,device_executed=False,scope='actual prepared TUs, offline BMG-G31; not measured occupancy or installed-driver JIT',commands=commands,kernels=kernels,source_sha256=sources,tools={str(p):sha(p) for p in (compiler,translator,Path('/usr/bin/ocloc'))},max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
 print(len(kernels),'offline kernels retained')
if __name__=='__main__':main()
