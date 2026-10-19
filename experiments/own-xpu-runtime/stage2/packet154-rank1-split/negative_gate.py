"""Reject malformed selections and undersized real target-head allocations."""
import json,subprocess
from build_engine import P,ROOT,B,sha,save,limits
from bundle_selection import selection
def main():
 limits();binary=B/'full-shape/fixture';dest=B/'negative';dest.mkdir(exist_ok=True);runs=[]
 v=('production','hc-wide','input-packed','ordered','fast','fused','rec-parallel','q4-g32')
 for case in ('expert','recurrence','host','missing-prefix','unknown-prefix','unknown-format','combined','short-target-head'):
  s=selection(v)
  if case in ('expert','recurrence','host'):s['choices'][{'expert':'experts','host':'host_retire'}.get(case,case)]='unknown'
  if case=='missing-prefix':del s['draft']['head_prefix']
  if case=='unknown-prefix':s['draft']['head_prefix']='bogus'
  if case=='unknown-format':s['draft']['head_format']='bogus'
  if case=='combined':s['draft']['head_prefix']='coverage990'
  path=dest/(case+'.json');save(path,s);out=dest/case;out.mkdir(exist_ok=True)
  cmd=[str(binary),str(path),sha(path),'1',str(out),'negative' if case=='short-target-head' else 'positive','1','0']
  r=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True)
  assert r.returncode!=0,(case,'invalid input accepted')
  assert ('extent' in r.stderr if case=='short-target-head' else 'selection' in r.stderr or 'draft' in r.stderr),(case,r.stderr)
  (out/'run.log').write_text(r.stdout+r.stderr);runs.append(dict(case=case,command=cmd,returncode=r.returncode,stderr=r.stderr))
 sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('negative_gate.py','p59c_select.hpp','p49d_submit.cpp','bundle_selection.py','selection-template.json')}
 save(P/'evidence/negative-gates.json',dict(passed=True,device_executed=False,runs=runs,sources=sources,binary_sha256=sha(binary)))
 print(len(runs),'negative admission/extent cases PASS')
if __name__=='__main__':main()
