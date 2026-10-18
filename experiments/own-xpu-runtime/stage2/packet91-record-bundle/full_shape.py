"""Run the frozen full-size startup fixtures on each actual packet91 selection.
Only model payloads/backend are mocked; allocation, capture and draft startup run.
"""
import gzip,json,shutil,subprocess
from build_engine import P,ROOT,B,PARENTS,sha,save,limits,provenance
from bundle_selection import views,selection
from chain_seal import check_map
from memory_gate import check

def main():
 limits();provenance();sources={};runs=[];scratch=B/'shape-current'
 for label,v in views().items():
  parent=PARENTS[v[6]];report=parent/'evidence/full-shape.json';r=json.loads(report.read_text());check_map(ROOT,r['sources'])
  sources.update(r['sources']);sources[str(report.relative_to(ROOT))]=sha(report)
  binary=parent/'build/full-shape/fixture';assert sha(binary)==r['binary_sha256'];sources[str(binary.relative_to(ROOT))]=sha(binary)
  assert sha(P/'dispatch-speed6.json')==sha(parent/'dispatch-speed6.json')
  for rank in (0,1):
   limits();scratch.mkdir();save(scratch/'selection.json',selection(v))
   try:
    cmd=[str(binary),str(scratch/'selection.json'),sha(scratch/'selection.json'),str(rank),str(scratch/'output'),'positive','1','0']
    result=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=120)
    out=scratch/'output';native=json.loads((out/'result.json').read_text());census=json.loads((out/'census.json').read_text());ops=(out/'selected-operations.txt').read_text()
    assert native['passed'] and not native['device_executed']
    assert ('p78route::Kernel' in ops)==(v[4]=='fast')
    assert ('p82brec::Kernel<true>' in ops)==(v[6]=='rec-both-plus')
    assert ('p82rec::Kernel<true>' in ops)==(v[6]=='rec-parallel')
    assert 'p60::Kernel<2, true, false>' in ops
    checked=check(census,json.loads((P/'memory-plan.json').read_text()),rank,mtp=True,context=4096,draft_rank=1,target_split=0)
    retained={}
    for leaf in ('census.json','selected-operations.txt','draft-prefix.json','result.json'):
     if (out/leaf).exists():
      dest=P/'evidence'/f'shape-{label}-rank{rank}-{leaf}.gz';dest.write_bytes(gzip.compress((out/leaf).read_bytes(),mtime=0));retained[leaf]=dict(path=str(dest.relative_to(ROOT)),sha256=sha(dest))
    runs.append(dict(view=label,placement='1',command=cmd,selection_key_consumers_verified=True,memory=checked,artifacts=retained,**native))
   finally:shutil.rmtree(scratch)
   print(label,rank,'full post-load startup PASS',flush=True)
 for leaf in ('full_shape.py','bundle_selection.py','selection-template.json','memory-plan.json','memory_gate.py','dispatch-speed6.json'):
  sources[str((P/leaf).relative_to(ROOT))]=sha(P/leaf)
 save(P/'evidence/full-shape.json',dict(passed=True,device_executed=False,model_payload_read=False,sources=sources,runs=runs))
if __name__=='__main__':main()
