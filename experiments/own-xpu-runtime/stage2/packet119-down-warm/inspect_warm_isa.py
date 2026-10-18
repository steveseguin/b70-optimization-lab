"""Audit the exact micro's existing AOT image; no compiler or device execution."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil

P=Path(__file__).resolve().parent
ROOT=P.parents[3]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert shutil.disk_usage('/').free>=25_000_000_000
 evidence=P/'evidence';dump=P/'build/igc-micro'
 receipt=json.loads((evidence/'micro-compile.json').read_text())
 for path,digest in receipt['sources'].items():assert sha(ROOT/path)==digest,path
 binary=(P/'build/microbench').read_bytes()
 assert hashlib.sha256(binary).hexdigest()==receipt['artifact_sha256']
 candidates=[p for p in dump.glob('*.asm') if 'p11910WarmKernel' in p.read_text().splitlines()[0]]
 assert len(candidates)==1,candidates
 candidate=candidates[0];prefix=candidate.name.split('_simd')[0]
 production=next(p for p in dump.glob(prefix+'*.asm') if 'p90exp6Kernel' in p.read_text().splitlines()[0])
 image=dump/(prefix+'.progbin');offset=binary.find(image.read_bytes())
 assert offset>=0,'audited native image is not embedded verbatim in sealed micro'
 llvm=dump/(prefix+'_optimized.ll');ir=llvm.read_text()
 kernel_ir=next(s for s in re.findall(r'^define spir_kernel.*?^}',ir,re.M|re.S) if 'p11910WarmKernel' in s.splitlines()[0])
 production_ir=next(s for s in re.findall(r'^define spir_kernel.*?^}',ir,re.M|re.S) if 'p90exp6Kernel' in s.splitlines()[0])
 # These concrete SSA witnesses are deliberately strict. A compiler/source
 # change requires reinspection rather than accepting any unrelated load.
 witnesses=['ptr addrspace(1) align 1 %2','%60 = mul nuw nsw i64 %48, 921600',
  '%61 = getelementptr inbounds i8, ptr addrspace(1) %2, i64 %60',
  '%86 = icmp ugt i32 %85, 6','%88 = mul nuw nsw i32 %85, 5120',
  '%90 = add i32 %89, -35840','%91 = icmp ult i32 %90, %3',
  '%94 = shl nuw nsw i64 %93, 4','%95 = getelementptr inbounds i32, ptr addrspace(1) %61, i64 %94',
  '%96 = load volatile i32, ptr addrspace(1) %95, align 4']
 for text in witnesses:assert text in kernel_ir,text
 assert 'load volatile' not in production_ir
 asm=candidate.read_text();control_asm=production.read_text()
 visa=candidate.with_suffix('.visaasm').read_text()
 warm_send=next(l for l in asm.splitlines() if 'load.ugm.d32.a64' in l and re.search(r'// \$181$',l))
 warm_visa=next(l for l in visa.splitlines() if 'lsc_load.ugm ' in l and 'V0232:d32' in l)
 assert '.uc.' not in warm_send and '.uc.' not in warm_visa
 assert len(re.findall(r'\bV0232\b',visa))==2,'warm value acquired an arithmetic consumer'
 assert 'alias=<V0035, 0>' in next(l for l in visa.splitlines() if '.decl V0191 ' in l)
 assert 'alias=<V0230, 0>' in next(l for l in visa.splitlines() if '.decl V0231 ' in l)
 assert 'V0192(0,0)<1> V0186' in visa and 'V0191(0,0)' in visa
 assert 'V0230(0,0)<1> V0192' in visa
 assert len(re.findall(r'load\.ugm',asm))==len(re.findall(r'load\.ugm',control_asm))+1
 assert len(re.findall(r'store\.ugm',asm))==len(re.findall(r'store\.ugm',control_asm))
 zeinfo=(dump/(prefix+'.zeinfo')).read_text()
 kernels=[]
 for name,text in [('p119',asm),('production',control_asm)]:
  kernel=text.splitlines()[0].removeprefix('//.kernel ')
  block=next(b for b in re.split(r'\n  - name:\s*',zeinfo)[1:] if b.splitlines()[0].strip()==kernel)
  grf=int(re.search(r'numGRF=(\d+)',text)[1])
  scratch=bool(re.search(r'per_thread_memory_buffers|scratch_size|spill_size|private_size',block))
  assert grf==128 and not scratch,(name,grf,scratch)
  kernels.append(dict(view=name,name=kernel,grf=grf,scratch_bytes=0,spill_free=True,
   static_ugm_loads=len(re.findall(r'load\.ugm',text)),static_ugm_stores=len(re.findall(r'store\.ugm',text))))
 artifacts={}
 for source,label in [(candidate,'p119-warm.asm'),(candidate.with_suffix('.visaasm'),'p119-warm.visaasm'),
   (production,'p119-production.asm'),(llvm,'p119-optimized.ll'),(dump/(prefix+'.zeinfo'),'p119-micro.zeinfo')]:
  target=evidence/(label+'.gz');target.write_bytes(gzip.compress(source.read_bytes(),mtime=0))
  artifacts[str(target.relative_to(P))]=sha(target)
 excerpt=evidence/'warm-isa-excerpt.txt'
 excerpt.write_text('Exact micro AOT image: '+sha(image)+'\n\nLLVM address/load witnesses:\n'+
  '\n'.join(witnesses)+'\n\nvISA address dataflow:\n'+
  '\n'.join(l for l in visa.splitlines() if any(k in l for k in ('.decl V0035 ','.decl V0191 ','.decl V0231 ','/// $133','/// $141','/// $175','/// $179','/// $180','/// $181')))+
  '\n\nNative retained load:\n'+warm_send+'\n')
 artifacts[str(excerpt.relative_to(P))]=sha(excerpt)
 sources=dict(receipt['sources'])
 for path in [Path(__file__),evidence/'micro-compile.json']:
  sources[str(path.relative_to(ROOT))]=sha(path)
 report=dict(schema='packet119.warm-isa.v1',passed=True,device_executed=False,sources=sources,artifacts=artifacts,
  micro_binary_sha256=receipt['artifact_sha256'],native_image_sha256=sha(image),native_image_bytes=image.stat().st_size,
  embedded_native_image_offset=offset,kernels=kernels,
  down_pointer_proof='p[9] captured as kernel argument2 / vISA V0035; expert_id*921600 +64*line reaches volatile i32 load; vISA V0232 has no consumers',
  native_warm_send=warm_send.strip(),visa_warm_send=warm_visa.strip(),
  cache_policy='default policy: no explicit UC/UC override; cache residency and effective capacity require queued device probe',
  scheduling='one retained send instruction in loop steps7,8,9; each worker issues0-3 loads under runtime line_limit',
  runtime_cache_capacity_measured=False,speed_measured=False,
  limits='AOT evidence for exact embedded micro image; v5 separately compiles same source and still needs device byte/speed gates')
 (evidence/'warm-isa.json').write_text(json.dumps(report,indent=2)+'\n')
 print('warm ISA PASS: embedded image;52vs51 loads;2 stores each;128GRF;zero scratch;no device')

if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 main()
