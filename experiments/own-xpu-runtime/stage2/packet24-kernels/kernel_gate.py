"""Generate checked source mirror; reject unknown kernel submission syntax."""
import re,json,subprocess
from kernel_overlay import apply
BASELINE='cb1643cd91fc142288b48367d34fd34fc4aef60f'
from pathlib import Path
from math_gate import closure,ROOT,HERE,OWNER

def mirror(before=False):
 assert not re.search(r'\b(malloc_device|malloc_shared|malloc_host|parallel_for|single_task|submit)\s*\(', (HERE/'jit_smoke.cpp').read_text()),'K0 must build only'
 paths=closure();dest=HERE/('build/before-checked' if before else 'build/checked');mapping={x:dest/x.relative_to(ROOT) for x in paths}
 # All imported owner consumers must use the packet-local diagnostic ABI.
 original=None
 rows=[]
 for src in paths:
  if src==original:continue
  text=src.read_text()
  if before and src.is_relative_to(HERE):
   old=subprocess.run(['git','show',BASELINE+':'+str(src.relative_to(ROOT))],capture_output=True,text=True)
   if old.returncode==0:text=old.stdout
  if not before:text=apply(src,text)
  edits=[]
  for m in re.finditer(r'\.\s*(parallel_for|single_task)(?:<[^;]*?>)?\s*\(',text):
   a=re.search(r'\[(?:=|&)?\]\s*(?:\([^;]*?\))?\s*(?:\[\[.*?\]\])?\s*\{',text[m.end():],re.S)
   if not a:raise ValueError('unrecognized kernel '+str(src))
   start=m.end()+a.start();assert ';' not in text[m.end():start],('kernel bypasses wrapper',src);body=m.end()+a.end()-1;depth=1;end=body+1
   while depth:
    depth+=(text[end]=='{')-(text[end]=='}');end+=1
   edits.extend([(start,'packet23::checked('),(end,')')]);rows.append(dict(source=str(src.relative_to(ROOT)),line=text[:m.start()].count('\n')+1,kind=m[1]))
  assert len(edits)//2==len(re.findall(r'(?:\.|::)\s*(?:parallel_for\w*|single_task)\b',text)),("unsupported device submission bypass",src)
  for at,value in sorted(edits,reverse=True):text=text[:at]+value+text[at:]
  def inc(m):
   name=m[1];options=[src.parent/name,HERE/name,OWNER/name,HERE.parent/'packet2/kernels'/name,HERE.parent/'packet2/loader'/name]
   target=next(x.resolve() for x in options if x.is_file())
   return '#include '+json.dumps(str(mapping[target]))
  text=re.sub(r'^\s*#include\s*"([^"\n]+)"',inc,text,flags=re.M)
  target=mapping[src];target.parent.mkdir(parents=True,exist_ok=True)
  content='#include '+json.dumps(str(HERE/('build/kernel_guard_before.hpp' if before else 'kernel_guard.hpp')))+'\n#line 1 '+json.dumps(str(src))+'\n'+text
  if not target.exists() or target.read_text()!=content:target.write_text(content)
 (HERE/('kernel-submissions-before.json' if before else 'kernel-submissions.json')).write_text(json.dumps(dict(passed=True,kernels=rows,count=len(rows)),indent=2)+'\n')
 if not before:
  for name,entry in [('main','packet23_model_entry'),('gemv_fixture','packet23_gemv_fixture_entry'),('nongemv_fixture','packet23_nongemv_fixture_entry')]:
   content=mapping[(HERE/(('k2' if name=='main' else name)+'.cpp')).resolve()].read_text()
   if name=='main':entry='packet24_k2_entry'
   content=content.replace('int main(int argc, char **argv)', 'int '+entry+'(int argc, char **argv)').replace('int main(int argc,char** argv)', 'int '+entry+'(int argc,char** argv)')
   target=HERE/'build'/('jit-'+name+'.cpp')
   if not target.exists() or target.read_text()!=content:target.write_text(content)
 return mapping
if __name__=='__main__':mirror()
