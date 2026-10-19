"""Pin the lab-owned native include closure; never alter an ancestor packet."""
import hashlib,json,re
from pathlib import Path
P=Path(__file__).resolve().parent; ROOT=P.parents[3]; BASE=P.parent/'packet136-record-bundle'; OLD=P.parent/'packet151-sibling-cost'
seeds=[BASE/n for n in ['kernel_guard.hpp','p42_cooperative.hpp','p60_kernels.hpp','p73_hc.hpp','p82b_recurrence.hpp','p49_qsa_reference.hpp','p49_qsa_kernel.hpp','p109_fusion.hpp','p100_down.hpp','p90_expert.hpp','p42_tiny.hpp','round2.hpp']]+[OLD/n for n in ['batched_rows.hpp','batched_experts.hpp']]
seen={}
def visit(src):
 src=src.resolve()
 if src.name=='owner.hpp':src=(BASE/'owner.hpp').resolve()
 if ('packet151-sibling-cost' in str(src) and src.name not in ('batched_rows.hpp','batched_experts.hpp','production_expert_chains.hpp') and (BASE/src.name).exists()):src=(BASE/src.name).resolve()
 if src in seen:return seen[src]
 dest=P/'native'/src.relative_to(ROOT);seen[src]=dest
 text=src.read_text()
 def include(m):
  q=Path(m[1]);q=q if q.is_absolute() else src.parent/q
  if not q.exists() and (BASE/q.name).exists():q=BASE/q.name
  if not q.exists():
   q=next((base/Path(m[1]) for base in (BASE,BASE.parent/'packet28-dense',P.parents[1]/'stage1/packet3-prep/src') if (base/Path(m[1])).exists()),q)
  if not q.exists():raise RuntimeError('missing include '+str(q))
  target=visit(q)
  import os
  return '#include "'+os.path.relpath(target,dest.parent)+'"'
 text=re.sub(r'#include\s*"([^\"]+)"',include,text)
 dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text)
 return dest
for src in seeds:visit(src)
rows=[dict(source=str(s.relative_to(ROOT)),source_sha256=hashlib.sha256(s.read_bytes()).hexdigest(),copy=str(d.relative_to(P)),sha256=hashlib.sha256(d.read_bytes()).hexdigest()) for s,d in seen.items()]
(P/'lineage').mkdir(exist_ok=True)
(P/'lineage/native-provenance.json').write_text(json.dumps(rows,indent=2)+'\n')
(P/'native_headers.hpp').write_text('#pragma once\n'+''.join('#include "'+str(seen[s.resolve()].relative_to(P))+'"\n' for s in seeds if s.name!='p49_qsa_kernel.hpp')+'\n#ifndef OWN_RT_HOST_ONLY\n#include "'+str(seen[(BASE/'p49_qsa_kernel.hpp').resolve()].relative_to(P))+'"\n#endif\n')
print(len(rows),'private native headers')
