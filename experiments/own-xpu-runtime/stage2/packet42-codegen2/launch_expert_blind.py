"""Recount explicit independently selected GEN basic-block regions, CPU only.
Input assumptions are in launch-expert-blind-counts.json. This is not a cost model.
"""
import gzip,hashlib,json,re
from pathlib import Path
P=Path(__file__).resolve().parent;root=P.parent
receipt=json.loads((P/'launch-expert-blind-counts.json').read_text())
for row in receipt['rows']:
 f=P/row['retained_assembly'];raw=gzip.decompress(f.read_bytes())
 if hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('changed assembly: '+str(f))
 parts=re.split(r'^// (B\d+):',raw.decode(),flags=re.M);blocks={int(parts[i][1:]):parts[i+1] for i in range(1,len(parts),2)}
 def count(ids):
  ops=[]
  for b in ids:
   for line in blocks[b].splitlines():
    m=re.match(r'([a-z][\w.]*(?:\([^)]*\))?)\s+(?:\((\d+)\|M\d+\))?',re.sub(r'^\([^)]*\)\s*','',line.strip()))
    if m:ops.append((m[1],int(m[2] or 1)))
  return len(ops),sum(bool(re.match(r'load\.|store\.|send|atomic\.',op)) for op,_ in ops),sum(max(1,w/16) for _,w in ops)
 instructions,messages,issues=count(row['blocks'])
 assert instructions==row['instructions'] and messages==row['memory_messages'] and issues==row['simd16_issue_units'],f
 if 'homogeneous_arms' in row:
  base=count([78,79,80,143]);arms=[]
  for start in range(87,143,7):arms.append([count([start,*arm])[:2] for arm in [[start+1,start+2],[start+1,start+3],[start+4,start+5],[start+4,start+6]]])
  assert [[list(v) for v in a] for a in arms]==row['homogeneous_arms']
 print(f.name,instructions,messages,'matched')
