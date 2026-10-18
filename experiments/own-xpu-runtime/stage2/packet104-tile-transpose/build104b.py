"""Bounded incremental build; immutable object inputs, no parent live receipts."""
import json, os, subprocess, resource
from pathlib import Path
from build_engine import P, ROOT, B, sha, save, limits
from compile_turn import turn
BASE=P.parent/'packet100-down-locality'
def main():
 limits();(B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 from kernel_gate import mirror
 from math_gate import closure,check
 check();mapping=mirror();sources={str(f.relative_to(ROOT)):sha(f) for f in closure()}
 sources.update({str(f.relative_to(ROOT)):sha(f) for f in mapping.values()})
 prior=json.loads((BASE/'engine-commands.json').read_text());save(P/'p104b-parent-commands.json',prior)
 parent=json.loads((BASE/'build-device-receipt.json').read_text())
 immutable={n:h for n,h in parent['sources'].items() if n.endswith(('.cpp','.hpp','.h','.o','.tsv','.bf16'))}
 for n,h in immutable.items():assert sha(ROOT/n)==h,n
 save(P/'p104b-parent-inputs.json',immutable);sources.update(immutable)
 entry=B/'entry-main.cpp';entry.write_text('#define main packet26_model_entry\n#include '+json.dumps(str(mapping[P/'main.cpp']))+'\n#undef main\n')
 commands=[];artifacts={};objects=[]
 def run(cmd,name):
  cmd=list(map(str,cmd));commands.append(dict(name=name,command=cmd,cwd=str(ROOT)))
  with turn(),(B/(name+'.log')).open('w') as f:subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=1200)
  print(name,'PASS',flush=True)
 for mode in ('gnu-host','device'):
  dest=B/mode;dest.mkdir(exist_ok=True)
  args=next(r['command'] for r in prior if r['name']==mode+'-entry-main');args=args[:args.index('-o')]
  args=[x.replace(str(BASE),str(P)) if x.startswith('-I') else x for x in args]
  rebuilt=('entry-main','p49d_submit','p49d_expert_submit','p60_submit')
  for stem in rebuilt:run([*args,'-o',dest/(stem+'.o'),'-c',entry if stem=='entry-main' else mapping[P/(stem+'.cpp')]],mode+'-'+stem)
  link=list(next(r['command'] for r in prior if r['name']==mode+'-link'));link[link.index('-o')+1]=str(dest/'own-rt-iq3');replaced=[]
  for i,arg in enumerate(link):
   if not arg.endswith('.o'):continue
   stem=next((s for s in rebuilt if Path(arg).name in (s+'.o',s+'.cpp.o') or Path(arg).name.endswith('-'+s+'.cpp.o') or Path(arg).name.endswith('-'+s+'.o')),None)
   if stem:link[i]=str(dest/(stem+'.o'));replaced.append(stem)
   else:sources[str(Path(arg).relative_to(ROOT))]=sha(arg);objects.append(dict(path=arg,sha256=sha(arg)))
  assert sorted(replaced)==sorted(rebuilt),replaced
  run(link,mode+'-link');artifacts[str((dest/'own-rt-iq3').relative_to(P))]=sha(dest/'own-rt-iq3')
 save(P/'engine-commands.json',commands)
 for f in (P/'build104b.py',P/'p104b-parent-commands.json',P/'p104b-parent-inputs.json',P/'engine-commands.json',P/'rope.bf16',P/'mtp-manifest.tsv',entry):sources[str(f.relative_to(ROOT))]=sha(f)
 size=sum(f.stat().st_size for f in B.rglob('*') if f.is_file());assert size<=200_000_000,size
 save(P/'build-device-receipt.json',dict(schema='packet104b.cpu-build.v1',passed=True,device_executed=False,sources=sources,artifacts=artifacts,objects=objects,build_logical_bytes=size,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
 print('build bytes',size,flush=True)
def provenance():
 from chain_seal import check_map
 row=json.loads((P/'build-device-receipt.json').read_text());assert row['passed'] and not row['device_executed']
 check_map(ROOT,row['sources']);check_map(P,row['artifacts']);return row
if __name__=='__main__':main()
