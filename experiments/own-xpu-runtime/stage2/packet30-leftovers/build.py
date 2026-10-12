#!/usr/bin/env python3
"""CPU build only: never execute the native binary or query a device."""
import argparse,hashlib,importlib.util,json,os,re,resource,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent; ROOT=P.parents[3]; B=P/'build'; P26=P.parent/'packet27-round2'; OWNER=P.parents[1]/'stage1/packet3-prep/src'
IC='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
FLAGS=['-O2','-std=c++20','-Werror=return-type','-fno-fast-math','-ffp-contract=off']
PRECISE=['-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt']
COMMON=[P/'g3.cpp',P/'route.cpp',P/'route_cpu.cpp',P/'attention.cpp',P/'small.cpp',P/'fusion.cpp',P/'p28_incumbent.cpp',P.parent/'packet28-dense/submit.cpp']+[P26/x for x in ('performance.cpp','adapter.cpp','specialised_submit.cpp','round2_submit.cpp','small_gemv.cpp','runtime_kernels.cpp','owner.cpp','owner_retire.cpp')]
NATIVE=[P26/'native.cpp',OWNER/'sycl_device.cpp',P.parent/'packet2/kernels/device.cpp']+[P.parent/x/'kernels.cpp' for x in ('packet6-kopt','packet7-kopt2','packet8-kopt3','packet9-kopt4','packet10-kopt5')]
INCLUDES=[P,P26,OWNER,P.parent/'packet2/kernels',P.parent/'packet2/loader',B]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(cmd,log):
 with log.open('w') as f:r=subprocess.run(list(map(str,cmd)),stdout=f,stderr=subprocess.STDOUT)
 if r.returncode:raise RuntimeError(str(log))
 print(log.name+' PASS',flush=True)
def closure():
 todo=COMMON+NATIVE; seen=set()
 while todo:
  p=todo.pop().resolve()
  if p in seen:continue
  seen.add(p)
  for name in re.findall(r'^\s*#include\s*"([^"\n]+)"',p.read_text(),re.M):
   choices=[p.parent/name]+[d/name for d in INCLUDES]
   q=next((c.resolve() for c in choices if c.is_file()),None)
   if q is None:raise ValueError(f'unresolved include {name} in {p}')
   todo.append(q)
 return sorted(seen)
def mirror():
 spec=importlib.util.spec_from_file_location('p26overlay',P26/'kernel_overlay.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 paths=closure();dest=B/'checked';mapping={p:dest/p.relative_to(ROOT) for p in paths}; kernels=[]
 for src in paths:
  text=mod.apply(src,src.read_text());edits=[]
  for m in re.finditer(r'\.\s*(parallel_for|single_task)(?:<[^;]*?>)?\s*\(',text):
   a=re.search(r'\[(?:=|&)?\]\s*(?:\([^;]*?\))?\s*(?:\[\[.*?\]\])?\s*\{',text[m.end():],re.S)
   if not a or ';' in text[m.end():m.end()+a.start()]:
    if src.parent==P and 'static_assert(sizeof(kernel)<=1024)' in text:
     kernels.append(dict(source=str(src.relative_to(ROOT)),line=text[:m.start()].count('\n')+1,named_capture_asserted=True));continue
    raise ValueError('unknown submission '+str(src))
   assert a.group().startswith(('[=]','[]')),('device capture must be by value',str(src),a.group()[:160])
   start=m.end()+a.start();body=m.end()+a.end()-1;depth=1;end=body+1
   while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
   # Even candidates already guarded get the uniform outer assertion.
   edits.extend([(start,'p30_guard::checked('),(end,')')]);kernels.append(dict(source=str(src.relative_to(ROOT)),line=text[:m.start()].count('\n')+1))
  for at,value in sorted(edits,reverse=True):text=text[:at]+value+text[at:]
  def inc(m):
   choices=[src.parent/m[1]]+[d/m[1] for d in INCLUDES];target=next(q.resolve() for q in choices if q.is_file())
   return '#include '+json.dumps(str(mapping[target]))
  text=re.sub(r'^\s*#include\s*"([^"\n]+)"',inc,text,flags=re.M)
  target=mapping[src];target.parent.mkdir(parents=True,exist_ok=True)
  target.write_text('#include '+json.dumps(str(P/'kernel_guard.hpp'))+'\n#line 1 '+json.dumps(str(src))+'\n'+text)
 (B/'mirror-inputs.json').write_text(json.dumps({str(x):sha(x) for x in paths},indent=2)+'\n')
 (P/'kernel-submissions.json').write_text(json.dumps(dict(passed=True,kernels=kernels,count=len(kernels)),indent=2)+'\n')
 return mapping

def build(mode):
 compiler='/usr/bin/g++' if mode=='host' else IC; native=mode=='device'; out=B/mode;out.mkdir(exist_ok=True)
 flags=FLAGS+(['-fsycl']+PRECISE if native else ['-DOWN_RT_HOST_ONLY','-DHOST_ONLY']+(['-fdenormal-fp-math=ieee'] if mode=='icpx-host' else []))
 mapping=mirror() if native else None
 sources=[x for x in COMMON if native or x.name not in ('small.cpp','fusion.cpp')]+(NATIVE if native else [])
 commands=[];objects=[]
 for index,src in enumerate(sources):
  obj=out/(str(index)+'-'+src.stem+'.o');source=mapping[src.resolve()] if native else src
  cmd=[compiler,*flags,*sum((['-I',str(d)] for d in INCLUDES),[]),'-c',str(source),'-o',str(obj)]
  commands.append(dict(kind='compile',source=str(src),argv=cmd));run(cmd,out/(str(index)+'-compile.log'));objects.append(obj)
 cmd=[compiler,*flags,*map(str,objects),'-o',str(out/'g3'),'-lcrypto']+(['-lze_loader','-Wl,-rpath,/opt/intel/oneapi/compiler/2026.0/lib'] if native else [])
 commands.append(dict(kind='link',argv=cmd));run(cmd,out/'link.log')
 for c in commands:assert all(f in c['argv'] for f in ['-fno-fast-math','-ffp-contract=off']+(PRECISE if native else []))
 (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 if not native:
  for repeat in (1,2):
   run([out/'g3','--validate','--output',out/f'validation{repeat}'],out/f'validation{repeat}.log')
   run([out/'g3','--cpu-fixtures','--output',out/f'fixtures{repeat}'],out/f'fixtures{repeat}.log')
 return commands

def seal():
 cpu=json.loads((P/'cpu-tests.json').read_text());assert cpu['passed'] and not cpu['device_executed']
 for n,digest in cpu['source_sha256'].items():assert sha(P/n)==digest,n+' changed since CPU seal'
 for n,digest in cpu['receipt_hashes'].items():assert sha(P/n)==digest,n+' evidence changed'
 for row in cpu['harness']:assert sha(B/row['compiler']/'g3')==row['binary_sha256']
 paths=closure()
 for name,digest in json.loads((B/'mirror-inputs.json').read_text()).items():assert sha(name)==digest,'rebuild device: '+name
 pattern=r'(std::|sycl::(native::|half_precision::)?|__builtin_)(exp|log|pow|sin|cos)(2|10|1p|m1)?f?\s*\('
 bad=[str(p) for p in paths if re.search(pattern,p.read_text())];assert not bad,bad
 commands={mode:json.loads((B/mode/'commands.json').read_text()) for mode in ('host','icpx-host','device')}
 for mode,rows in commands.items():
  for row in rows:assert all(f in row['argv'] for f in ['-fno-fast-math','-ffp-contract=off']+(PRECISE if mode=='device' else []))
 local={str(p.relative_to(P)):sha(p) for p in P.iterdir() if p.suffix in ('.py','.cpp','.hpp','.md') or p.name in ('.gitignore','class-registry.json','kernel-submissions.json')}
 local.update(cpu['receipt_hashes'])
 external={str(p.relative_to(ROOT)):sha(p) for p in paths if not p.is_relative_to(P)}
 external[str((P26/'kernel_overlay.py').relative_to(ROOT))]=sha(P26/'kernel_overlay.py')
 times=P26/'receipts-cards01-20261012-chain/w2c-r27/class-times.json';external[str(times.relative_to(ROOT))]=sha(times)
 binaries={str(p.relative_to(P)):sha(p) for p in (B/'host/g3',B/'icpx-host/g3',B/'device/g3')}
 receipt=dict(schema='packet30.build.v1',passed=True,device_executed=False,arithmetic='iq3-p17-detmath-v2',max_compile_jobs=2,numeric_threads=2,host_memory_limit_bytes=8*1024**3,artifacts_sha256=binaries,sources_sha256=local,external_sources_sha256=external,cpu_receipt_sha256=sha(P/'cpu-tests.json'),precision_commands=commands,math_gate=dict(passed=True,files=len(paths),pattern=pattern),kernel_guard_sha256=sha(P/'kernel_guard.hpp'))
 (P/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['host','icpx-host','device','seal']);a=p.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 B.mkdir(exist_ok=True);(B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 if a.mode=='seal':seal()
 else:build(a.mode)
if __name__=='__main__':main()
