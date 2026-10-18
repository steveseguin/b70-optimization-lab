"""Read-only port and footprint audit; no device or parent mutation."""
import json,shutil
from pathlib import Path
from source_decision import O,P,ROOT,STAGE,sha,save

def main():
 parent=STAGE/'packet111-record-bundle';changed=[];checked=[]
 for path in sorted(P.iterdir()):
  if path.suffix not in ('.cpp','.hpp') or not (parent/path.name).is_file():continue
  old=(parent/path.name).read_text().replace('packet111-record-bundle','packet118-record-bundle').replace('packet111','packet118').replace('p111','p118')
  if path.read_text()!=old:changed.append(path.name)
  checked.append(dict(path=str(path.relative_to(ROOT)),sha256=sha(path),parent_sha256=sha(parent/path.name)))
 assert changed==['p59c_select.hpp','p83_head.hpp'],changed
 original=STAGE/'packet114-draft-prefix/sources'/parent.with_name('packet103-record-bundle').relative_to(ROOT)
 deltas={'p83_head.hpp':(' if(choice=="coverage990")return 80128;',' if(choice=="p114-80128")return 80128;\n if(choice=="coverage990")return 80128;'), 'p59c_select.hpp':('value!="production"&&value!="coverage990"','value!="production"&&value!="p114-80128"&&value!="coverage990"')}
 for leaf,(old,new) in deltas.items():
  assert new in (original/leaf).read_text(),'packet114 implementation missing'
  assert (parent/leaf).read_text().replace(old,new)==(P/leaf).read_text(),leaf
 assert sha(P/'prefix_cpu.cpp')==sha(STAGE/'packet114-draft-prefix/prefix_cpu.cpp')
 size=sum(f.stat().st_size for f in (P/'build').rglob('*') if f.is_file() and not f.is_symlink())
 free=shutil.disk_usage('/').free
 assert size<=250_000_000 and free>=25_000_000_000
 result=dict(passed=True,device_executed=False,kernel_changes=changed,checked=checked,build_bytes=size,root_free_bytes=free,no_new_head_allocation=True,shape_evidence_sha256=sha(P/'evidence/full-shape.json'))
 save(O/'source-audit.json',result)
 print(json.dumps({k:v for k,v in result.items() if k!='checked'}))
if __name__=='__main__':main()
