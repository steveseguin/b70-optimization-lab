"""Checked by-value kernel mirror; reject unknown submission syntax."""
import re,json
from pathlib import Path
from kernel_overlay import apply
from math_gate import closure,ROOT,HERE,OWNER
def mirror():
 assert not re.search(r'\b(malloc_device|malloc_shared|malloc_host|parallel_for|single_task|submit)\s*\(', (HERE/'jit_smoke.cpp').read_text()),'K0 must build only'
 paths=closure();dest=HERE/'build/checked';mapping={x:dest/x.relative_to(ROOT) for x in paths}
 # All imported owner consumers must use the packet-local diagnostic ABI.
 original=None
 rows=[]
 for src in paths:
  if src==original:continue
  text=src.read_text()
  text=apply(src,text)
  edits=[]
  for m in re.finditer(r'\.\s*(parallel_for|single_task)(?:<[^;]*?>)?\s*\(',text):
   a=re.search(r'\[(?:=|&)?\]\s*(?:\([^;]*?\))?\s*(?:\[\[.*?\]\])?\s*\{',text[m.end():],re.S)
   if not a:raise ValueError('unrecognized kernel '+str(src))
   assert not a.group(0).startswith('[&]'),('device capture must be by value',src)
   start=m.end()+a.start();assert ';' not in text[m.end():start],('kernel bypasses wrapper',src);body=m.end()+a.end()-1;depth=1;end=body+1
   while depth:
    depth+=(text[end]=='{')-(text[end]=='}');end+=1
   edits.extend([(start,'packet26::checked('),(end,')')]);rows.append(dict(source=str(src.relative_to(ROOT)),line=text[:m.start()].count('\n')+1,kind=m[1]))
  assert len(edits)//2==len(re.findall(r'(?:\.|::)\s*(?:parallel_for\w*|single_task)\b',text)),("unsupported device submission bypass",src)
  for at,value in sorted(edits,reverse=True):text=text[:at]+value+text[at:]
  def inc(m):
   name=m[1];options=[src.parent/name,HERE/name,OWNER/name,HERE.parent/'packet2/kernels'/name,HERE.parent/'packet2/loader'/name]
   target=next(x.resolve() for x in options if x.is_file())
   return '#include '+json.dumps(str(mapping[target]))
  text=re.sub(r'^\s*#include\s*"([^"\n]+)"',inc,text,flags=re.M)
  target=mapping[src];target.parent.mkdir(parents=True,exist_ok=True)
  content='#include '+json.dumps(str(HERE/'kernel_guard.hpp'))+'\n#line 1 '+json.dumps(str(src))+'\n'+text
  if not target.exists() or target.read_text()!=content:target.write_text(content)
 (HERE/'kernel-submissions.json').write_text(json.dumps(dict(passed=True,kernels=rows,count=len(rows)),indent=2)+'\n')
 for name,entry in [('main','packet26_model_entry'),('nongemv_fixture','packet26_fixture_entry'),('k2_fixture','packet26_k2_entry')]:
  source=(HERE/(name+'.cpp')).resolve()
  if source not in mapping: continue
  content=mapping[source].read_text()
  content=re.sub(r'\bint\s+main\s*\(', 'int '+entry+'(', content)
  target=HERE/'build'/('jit-'+name+'.cpp')
  if not target.exists() or target.read_text()!=content:target.write_text(content)
 return mapping
if __name__=='__main__':mirror()
