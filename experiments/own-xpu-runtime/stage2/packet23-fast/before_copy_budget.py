"""Build/run the committed r2 CPU path with submission counters only.
Native-only parameter uploads are intentionally NOT fabricated by this mock.
"""
import re,json,subprocess,hashlib,resource,concurrent.futures,time
from pathlib import Path
from math_gate import closure,ROOT,HERE,OWNER
P=HERE;B=P/'build';DEST=B/'r2-count'
def main():
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 revision='dcd6124df7f147b3c0b64ee5a51ffce95b7e74d9'
 paths=closure();mapping={p:DEST/p.relative_to(ROOT) for p in paths}
 current=(P/'main.cpp').read_text()
 for src in paths:
  text=src.read_text()
  if src.is_relative_to(P):
   old=subprocess.run(['git','show',revision+':'+str(src.relative_to(ROOT))],capture_output=True,text=True)
   if old.returncode==0:text=old.stdout
  if src==P/'owner.hpp':text=(P/'owner.hpp').read_text()
  if src==P/'owner.cpp':
   text=(P/'owner.cpp').read_text().replace('if(dq>=0&&sq>=0){++counters[&owner_].launches;++counters[&owner_].byte_move_launches;}else {++counters[&owner_].device_copies;++counters[&owner_].device_copies_by_card[queue];}', '++counters[&owner_].device_copies;++counters[&owner_].device_copies_by_card[queue];')
  if src==P/'main.cpp':
   a=text.index('#ifdef OWN_RT_HOST_ONLY\nclass Host final');b=text.index('struct Options',a)
   c=current.index('#ifdef OWN_RT_HOST_ONLY\nstatic bool count_only');d=current.index('struct Options',c)
   text=text[:a]+current[c:d]+'static bool counting_token=false;\n'+text[b:]
   text=text.replace('    if (k == "--canary")','    if(k=="--count-submissions"){count_only=true;continue;}\n    if (k == "--canary")')
   text=text.replace('    weights[c][name] = id;', '    weights[c][name] = id;\n    if(count_only)return;')
   text=text.replace('    drain();\n    auto started=std::chrono::steady_clock::now();\n    for (size_t i','    if(count_only && !counting_token)return;\n    drain();\n    auto started=std::chrono::steady_clock::now();\n    for (size_t i')
   text=text.replace('std::memcpy(b.data() + i, dev(c).arena.row(slab[c]).pointer, k);','if(!count_only)std::memcpy(b.data() + i, dev(c).arena.row(slab[c]).pointer, k);')
   text=text.replace('auto row = w.read(t.name, id * rb, rb);','auto row = count_only?std::vector<uint8_t>(rb):w.read(t.name, id * rb, rb);')
   text=text.replace('      auto token_sub=e->submitted,token_wait=e->host_waits;', '      counting_token=true;auto counts_before=ownrt::submission_counts(e->dev(0));\n      auto token_sub=e->submitted,token_wait=e->host_waits;')
   text=text.replace('      require(!status,"sticky device error', '      if(count_only){status=0;result=0;}\n      require(!status,"sticky device error')
   text=text.replace('<<",\\"host_waits\\":"<<e->host_waits-token_wait', '<<",\\"device_copies\\":"<<ownrt::submission_counts(e->dev(0)).device_copies-counts_before.device_copies<<",\\"launches\\":"<<ownrt::submission_counts(e->dev(0)).launches-counts_before.launches<<",\\"host_waits\\":"<<e->host_waits-token_wait')
  def inc(m):
   name=m[1];options=[src.parent/name,P/name,OWNER/name,P.parent/'packet2/kernels'/name,P.parent/'packet2/loader'/name]
   target=next(x.resolve() for x in options if x.is_file())
   return '#include '+json.dumps(str(mapping[target]))
  text=re.sub(r'^\s*#include\s*"([^"\n]+)"',inc,text,flags=re.M)
  dest=mapping[src];dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text)
 import shutil
 shutil.copyfile(P/'rope.bf16',mapping[P/'main.cpp'].parent/'rope.bf16')
 sources=[P/n for n in ('main.cpp','gemv_batch.cpp','performance.cpp','adapter.cpp','runtime_kernels.cpp','owner_retire.cpp','owner.cpp')]+[P.parent/'packet2/loader/gguf.cpp']
 def compile(src):
  obj=mapping[src].with_suffix('.o')
  with obj.with_suffix('.log').open('w') as log:subprocess.run(['g++','-std=c++20','-O2','-fopenmp','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(OWNER),'-c',str(mapping[src]),'-o',str(obj)],check=True,stdout=log,stderr=subprocess.STDOUT)
  return obj
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:objects=list(pool.map(compile,sources))
 binary=DEST/'r2-mock';subprocess.run(['g++','-fopenmp',*map(str,objects),'-lcrypto','-o',str(binary)],check=True)
 rows=[]
 for mini in (True,False):
  out=DEST/('mini' if mini else 'real-metadata');cmd=[str(binary),'--cards','2','--card','0','--memory','resident','--context','256','--tokens',str(2 if mini else 10),'--output',str(out)]
  if mini:cmd+=['--mini']
  else:cmd+=['--count-submissions','--plan',str(B/'input/plan.tsv'),'--identity',str(B/'input/identity.tsv'),'--input',str(B/'input/tokens.txt'),'--model-dir',json.loads((B/'input/input.json').read_text())['model_dir']]
  with out.with_suffix('.log').open('w') as log:subprocess.run(cmd,check=True,stdout=log,stderr=subprocess.STDOUT)
  rows.append(dict(kind='mini-arithmetic' if mini else 'real-plan-metadata-only',tokens=[json.loads(x) for x in (out/'timings.jsonl').read_text().splitlines()]))
 (P/'copy-budget-before.json').write_text(json.dumps(dict(passed=True,device_executed=False,baseline_commit=revision,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),rows=rows,limitation='r2 native-only parameter uploads were absent from its CPU mock; these are host-visible counts, not the total native copy count'),indent=2)+'\n')
if __name__=='__main__':main()
