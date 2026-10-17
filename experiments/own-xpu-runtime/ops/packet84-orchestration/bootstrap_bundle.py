"""One-time packet80 copy and explicit, independently reviewable source deltas."""
import hashlib,json,shutil,subprocess
from pathlib import Path
O=Path(__file__).resolve().parent;R=O.parents[3];S=R/'experiments/own-xpu-runtime/stage2'
P=S/'packet84-record-bundle';BASE=S/'packet80-record-bundle'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def edit(n,a,b):
 p=P/n;t=p.read_text();assert a in t,(n,a);p.write_text(t.replace(a,b))
pins={}
for f in BASE.iterdir():
 if f.is_file() and f.suffix in ('.py','.sh','.cpp','.hpp','.inc','.tsv','.bf16','.patch','.json','.md','.txt'):
  if f.suffix=='.json' and f.name not in ('selection-template.json','dispatch-speed6.json','input-fixtures.json','dependency-pins.json','shared-wrapper-pin.json','placement-policy.json','runtime-revision.json','kernel-registry.json','kernel-submissions.json','k2-class-registry.json','chain-registration.json','chain-binding.json','oracle-binding.json'):continue
  dest=P/f.name;shutil.copyfile(f,dest);pins[str(f.relative_to(R))]=sha(f)
for name in ('calibration','p28','prototype'):
 shutil.copytree(BASE/name,P/name,symlinks=False,dirs_exist_ok=True)
(P/'oracle').symlink_to('../packet49-integrate/oracle',target_is_directory=True)
for n in ('build','build/tmp','evidence','selections'): (P/n).mkdir(parents=True,exist_ok=True)
# Rename packet identity in the copy only, preserving explicit source ancestry below.
for f in P.rglob('*'):
 if f.is_file() and f.suffix in ('.py','.sh','.json','.md'):
  f.write_text(f.read_text().replace('packet80','packet84').replace('Packet80','Packet84').replace('p80-plan','p84-plan'))
for packet,files in ((81,('p65_expert.hpp','p49d_expert_submit.cpp','p81_cpu.cpp')),(82,('p82_recurrence.hpp','p82_cpu.cpp')),(83,('p83_head.hpp','p83_cpu.cpp','p59c_select.hpp','coverage.json','real_head_gate.py'))):
 source=next(S.glob(f'packet{packet}-*'))
 for name in files:
  f=source/name;shutil.copyfile(f,P/name);pins[str(f.relative_to(R))]=sha(f)
# Apply packet83's draft changes to packet80, retaining rank0 prefix support.
parent=S/'packet75-record-bundle/mtp.hpp';candidate=S/'packet83-draft-bytes/mtp.hpp'
patch=subprocess.run(['diff','-u','--label','mtp.hpp',str(parent),'--label','mtp.hpp',str(candidate)],capture_output=True,text=True)
(P/'packet83-draft.patch').write_text(patch.stdout)
subprocess.run(['patch','--batch','--forward','-p0','-i',str(P/'packet83-draft.patch')],cwd=P,stdin=subprocess.DEVNULL)
# The only overlap is packet80's rank0 private prefix allocation.
t=(P/'mtp.hpp').read_text();c=candidate.read_text()
a=c.index('  if(q4_head()){\n');b=c.index('  weights["output.weight"]=hw;',a)
new=c[a:b].replace('if(e.packed_weight("output.weight"))hw.rows=', 'if(e.a.rank==0||e.packed_weight("output.weight"))hw.rows=')
new=new.replace(':e.packed_weight("output.weight")?size_t(hw.rows)',':(e.a.rank==0||e.packed_weight("output.weight"))?size_t(hw.rows)')
start=t.index('  if(e.a.memory=="resident"&&e.weights[0].count("output.weight")');end=t.index('  weights["output.weight"]=hw;',start)
t=t[:start]+new+t[end:];(P/'mtp.hpp').write_text(t)
pins[str(candidate.relative_to(R))]=sha(candidate)
edit('p49d_submit.cpp','#include "p49d_recurrence.hpp"','#include "p49d_recurrence.hpp"\n#include "p82_recurrence.hpp"')
edit('p49d_submit.cpp','Launch mix(Device&d', 'template<bool Split>Launch recurrence82(Device&d,const Spec&s,IDs a,Allocation,Allocation,Allocation,Deps deps){\n auto b=p49drec::recurrence_bindings(s,a);recurrence_validate(d,s,a,b);p82rec::Kernel<Split>k;k.shape=b.shape;auto e=d.compute(k,b.ids,deps);return {e,e,1};\n}\nLaunch mix(Device&d')
edit('p49d_submit.cpp','choice=="experts2-b"','choice=="experts2-b"||choice=="input-packed"||choice=="gate-input-packed"||choice=="down-input-packed"')
edit('p49d_submit.cpp','if(cls=="recurrence"){','if(cls=="recurrence"){if(choice=="rec-gates")return recurrence82<false>;if(choice=="rec-parallel")return recurrence82<true>;')
edit('p49d_submit.cpp',' if(target_values!=',' if(target_values.at("recurrence")=="rec-gates"||target_values.at("recurrence")=="rec-parallel")target_values["recurrence"]="rows4-shared";\n if(target_values!=')
edit('build_engine.py',"BASE=P.parent/'packet75-record-bundle'","BASE=P.parent/'packet80-record-bundle'")
edit('build_engine.py',"rebuilt=('entry-main','p49d_submit','p60_submit','owner_retire') + (('single_device',) if mode=='device' else ())","rebuilt=('entry-main','p49d_submit','p49d_expert_submit')")
template=json.loads((P/'selection-template.json').read_text());template['draft'].update(head_format='production',head_prefix='production');save(P/'selection-template.json',template);save(P/'selection.json',template)
save(P/'parent-source-manifest.json',pins)
save(P/'baseline-pins.json',dict(source_packet='packet80-record-bundle',source_commit='d7051c047',authority='Owner packet84 brief; coordinator selection explicitly supplied',selection=dict(dense='production',hc='hc-wide',experts='wide64',host='ordered',route='production',norm='production',placement='1',recurrence='production',draft_head='production')))
for n in ('orchestrate.py','verify_ready.py','device-entry.sh'):
 f=O.parent/'packet80-orchestration'/n
 (O/n).write_text(f.read_text().replace('packet80','packet84').replace('Packet80','Packet84'))
print('Copied packet80 and applied packet81/82/83 changes; no frozen file written')
