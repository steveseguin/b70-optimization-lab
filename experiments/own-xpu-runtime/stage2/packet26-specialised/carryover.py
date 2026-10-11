"""Exact source/region proof for historical packet18 default arithmetic only."""
import hashlib,json,subprocess,difflib
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];BASE=P.parent/'packet18-decode-v2'
def h(b):return hashlib.sha256(b).hexdigest()
def sha(p):return h(p.read_bytes())
def main():
 proof=json.loads((P/'source-proof.json').read_text());commit=proof['base_commit']
 def old(name):return subprocess.check_output(['git','show',commit+':'+str((BASE/name).relative_to(ROOT))])
 same={}
 for name in ('arithmetic.hpp','core_v2.hpp','detmath.hpp','kernels.hpp','runtime_kernels.cpp','rope.hpp','rope.bf16'):
  assert old(name)==(P/name).read_bytes(),name;same[name]=sha(P/name)
 oldmain=old('main.cpp').decode();newmain=(P/'main.cpp').read_text();anchor='static flash::Plan plan('
 oldplan=oldmain[oldmain.index(anchor):];oldplan=oldplan[:oldplan.index('  return p;')]
 newplan=newmain[newmain.index(anchor):];newplan=newplan[:newplan.index('  // Optional arithmetic-preserving specialised fusions.')]
 assert oldplan==newplan,'default packet18 plan prefix changed'
 oldadapter=old('adapter.cpp').decode();newadapter=(P/'adapter.cpp').read_text()
 prefix=oldadapter[:oldadapter.index('#ifdef OWN_RT_HOST_ONLY\nstruct NgHost')]
 current=newadapter[:newadapter.index('template<int Width,class F> float subtree')].replace('#include "specialised_submit.hpp"\n','').replace('#include "mock_order.hpp"\n','')
 assert prefix==current,'frozen Bound/tiny/simple arithmetic changed'
 anchor='#ifdef OWN_RT_HOST_ONLY\nstruct NgHost';end='Launch submit_parallel('
 a=oldadapter[oldadapter.index(anchor):oldadapter.index(end)];b=newadapter[newadapter.index(anchor):newadapter.index(end)]
 assert a==b,'frozen Glue/Team/NgHost numerical implementation changed'
 imported={str(x.relative_to(ROOT)):sha(x) for x in [P.parent/'packet3/step/plan.hpp',P.parent/'packet3/step/model.hpp'] if x.exists()}
 receipts={}
 for name in ('cpu-real-r5.json','receipts-cards23-20261011-w2/run/receipt.json','receipts-cards23-20261011-w3/run/receipt.json'):
  f=BASE/name
  if f.exists():receipts[str(f.relative_to(ROOT))]={'sha256':sha(f),'receipt':json.loads(f.read_text())}
 assert receipts,'historical receipt absent'
 r=dict(passed=True,device_executed=False,source_commit=commit,scope='historical default dispatch arithmetic and default schedule only; no packet26 binary/device qualification',qualifies_all_new=False,unchanged_files=same,default_plan_prefix_sha256=h(oldplan.encode()),default_adapter_arithmetic_prefix_sha256=h(prefix.encode()),default_adapter_glue_sha256=h(a.encode()),shared_plan_sources=imported,prior_receipts=receipts,limitations=['Host owner, flags and captures changed; W0/W2 remain mandatory.','GEMV compile mirror specialises single descriptor/type without changing reduction expressions; no new device parity is inferred.','Optional specialised fusions do not inherit these receipts.'])
 (P/'carryover-proof.json').write_text(json.dumps(r,indent=2)+'\n')
 print('exact default arithmetic/schedule source regions PASS')
if __name__=='__main__':main()
