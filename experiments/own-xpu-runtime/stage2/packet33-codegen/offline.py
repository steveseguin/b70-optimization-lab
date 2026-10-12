#!/usr/bin/env python3
"""CPU-only extraction of byte-identical shipped images and offline IGC rebuild."""
import hashlib,json,os,resource,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent

def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 records=json.loads((P/'modules.json').read_text()); receipts=[]
 binary=P.parent/'packet29-merged/build/device/k2-fixtures'
 for r in records:
  if not any(s in ' '.join(r['kernels']) for s in ('3p296Kernel','3p286Kernel','p25bridge6Kernel','p25bridge16ScalePreparation','p25bridge16InputPreparation','5kopt4','8expanded12_GLOBAL__N_18Multiply','11specialised6Kernel','6round26Kernel','8packet18','packet275small','2ng6Kernel')):continue
  tag=Path(r['path']).stem.rsplit('-',1)[-1];spv=P/'build'/Path(r['path']).name
  spv.parent.mkdir(exist_ok=True)
  with binary.open('rb') as f:f.seek(r['shipped_offset']);b=f.read(r['bytes'])
  if hashlib.sha256(b).hexdigest()!=r['sha256']:raise ValueError('Shipped module changed; regenerate exact link record')
  spv.write_bytes(b)
  dump=P/'build'/('igc-'+tag);out=P/'build'/('aot-'+tag)
  env={k:v for k,v in os.environ.items() if not k.startswith(('IGC_','NEO_','SYCL_','UR_','ZE_'))}
  env.update(IGC_ShaderDumpEnable='1',IGC_DumpToCustomDir=str(dump),IGC_ShowFullVectorsInShaderDumps='1')
  argv=['/usr/bin/ocloc','compile','-spirv_input','-file',str(spv),'-device','0xe223','-revision_id','0','-options','-ze-opt-level=O2 -cl-fp32-correctly-rounded-divide-sqrt','-out_dir',str(out)]
  t=time.monotonic()
  with (P/'build'/('ocloc-'+tag+'.log')).open('w') as f:q=subprocess.run(argv,env=env,stdout=f,stderr=subprocess.STDOUT)
  receipts.append(dict(tag=tag,argv=argv,returncode=q.returncode,seconds=time.monotonic()-t,dump=str(dump.relative_to(P)),environment={k:v for k,v in env.items() if k.startswith('IGC_')}))
  (P/'offline-commands.json').write_text(json.dumps(receipts,indent=2)+'\n')
  if q.returncode:raise RuntimeError(tag+' offline compile failed; see retained build log')
  print(tag,q.returncode,flush=True)
if __name__=='__main__':main()
