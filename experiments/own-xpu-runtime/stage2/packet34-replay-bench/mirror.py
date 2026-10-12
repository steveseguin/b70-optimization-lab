"""Reproduce packet29's qualified capture guard/overlay locally; no prior writes."""
import sys,json,re,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent; R=P.parent/'packet29-merged'
sys.path.insert(0,str(R))
from math_gate import closure,ROOT,OWNER
from kernel_overlay import apply
def make():
 paths=closure(); dest=P/'build/checked'; mapping={x:dest/x.relative_to(ROOT) for x in paths}; rows=[]; proof={}
 for src in paths:
  text=apply(src,src.read_text()); edits=[]
  for m in re.finditer(r'\.\s*(parallel_for|single_task)(?:<[^;]*?>)?\s*\(',text):
   a=re.search(r'\[(?:=|&)?\]\s*(?:\([^;]*?\))?\s*(?:\[\[.*?\]\])?\s*\{',text[m.end():],re.S)
   assert a and not a.group().startswith('[&]'),str(src)
   start=m.end()+a.start(); assert ';' not in text[m.end():start]
   end=m.end()+a.end(); depth=1
   while depth: depth+=(text[end]=='{')-(text[end]=='}'); end+=1
   edits.extend([(start,'packet26::checked('),(end,')')]); rows.append({'source':str(src.relative_to(ROOT)),'line':text[:m.start()].count('\n')+1})
  assert len(edits)//2==len(re.findall(r'(?:\.|::)\s*(?:parallel_for\w*|single_task)\b',text)),str(src)
  for at,value in sorted(edits,reverse=True):text=text[:at]+value+text[at:]
  def inc(m):
   options=[src.parent/m[1],R/m[1],OWNER/m[1],R.parent/'packet2/kernels'/m[1],R.parent/'packet2/loader'/m[1]]
   target=next(x.resolve() for x in options if x.is_file());return '#include '+json.dumps(str(mapping[target]))
  text=re.sub(r'^\s*#include\s*"([^"\n]+)"',inc,text,flags=re.M)
  target=mapping[src];target.parent.mkdir(parents=True,exist_ok=True)
  content='#include '+json.dumps(str(R/'kernel_guard.hpp'))+'\n#line 1 '+json.dumps(str(src))+'\n'+text
  if not target.exists() or target.read_text()!=content:target.write_text(content)
  proof[str(src.relative_to(ROOT))]=hashlib.sha256(src.read_bytes()).hexdigest()
 (P/'source-proof.json').write_text(json.dumps({'unchanged_packet29_inputs':proof,'overlay':'packet29 kernel_overlay.apply unchanged; capture-size guard unchanged','guarded_submission_sites':rows},indent=2)+'\n')
if __name__=='__main__':make()
