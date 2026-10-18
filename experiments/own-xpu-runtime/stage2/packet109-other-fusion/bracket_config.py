"""Fixed packet103 selection, changing only exact other_fusion kernels."""
from common import HERE,ROOT,P56,read,require,sha,save,verify_map,module
LINEAGE=HERE/'lineage'
def sealed_identity(args):
 require(args.profile=='tp2' and args.placement=='1' and args.timing=='token','p109 fixed two-card identity')
 seal=LINEAGE/'screen-seal.json';row=read(seal)
 require(row.get('passed') is True and row.get('device_executed') is False,'CPU seal missing')
 verify_map(ROOT,row['sources']);binary=HERE/'build/device/own-rt-iq3';dispatch=LINEAGE/'dispatch-speed6.json'
 for value,path in ((args.binary,binary),(args.dispatch,dispatch),(args.seal,seal)):require(value is None or value.resolve()==path,'sealed input differs')
 require(row['binary_sha256']==sha(binary),'binary changed')
 gate=module('p109_memory',P56/'memory_gate.py');configuration=gate.configuration(read(LINEAGE/'memory-plan.json'),4096,1,0)
 placement=dict(name='1',draft_rank=1,target_split=0,layer_boundary=24,target_layers=[24,24],context=4096,memory_admitted=True,supported=True,reason='p109 full-shape allocation/capture',configuration=configuration,memory_gate=str(P56/'memory_gate.py'),memory_gate_sha256=sha(P56/'memory_gate.py'))
 return dict(placement=placement,timing='token',timing_modes=['token'],lineage=str(LINEAGE),seal=str(seal),seal_sha256=sha(seal),binary=str(binary),binary_sha256=sha(binary),dispatch=str(dispatch),dispatch_sha256=sha(dispatch),profile='tp2',selection_sha256=sha(LINEAGE/'selection.json'),memory_plan_sha256=sha(LINEAGE/'memory-plan.json'))
def prepare():
 import copy
 row=read(LINEAGE/'selection.json');row['choices']['other_fusion']='production';row['decision']=None
 save(LINEAGE/'selection.json',row)
 candidate=copy.deepcopy(row);candidate['choices']['other_fusion']='fused';save(LINEAGE/'candidate.json',candidate)
 views=[]
 for choice in ('control','candidate','control','candidate','control'):
  path=LINEAGE/('selection.json' if choice=='control' else 'candidate.json')
  views.append(dict(choice=choice,selection=str(path),selection_sha256=sha(path)))
 save(HERE/'configs/bracket.json',dict(kind='bracket',views=views))
 save(HERE/'selection-provenance.json',dict(parent='packet103-record-bundle',copied_selection=sha(LINEAGE/'selection.json'),mutable_parent_outputs_pinned=False,only_changed_dimension='other_fusion'))
if __name__=='__main__':prepare()
