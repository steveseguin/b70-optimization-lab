"""Two fixed layouts; draft_hc_schedule is the only one-load switch."""
import copy
from common import HERE, ROOT, P56, read, require, sha, save, verify_map, module

VALUES=('p122',)
LINEAGE=HERE/'lineage'

def prepare(candidate):
 require(candidate in VALUES,'unknown packet122 candidate')
 (HERE/'configs').mkdir(exist_ok=True)
 row=read(LINEAGE/'selection.json')
 require(row['choices']['experts']=='exp-halfcache+down-tile16','packet111 expert baseline changed')
 row['choices']['draft_hc_schedule']='production';row['decision']=None
 save(LINEAGE/'selection.json',row)
 alt=copy.deepcopy(row);alt['choices']['draft_hc_schedule']=candidate
 save(LINEAGE/'candidate.json',alt)
 views=[]
 for choice in ('control','candidate','control','candidate','control'):
  p=LINEAGE/('selection.json' if choice=='control' else 'candidate.json')
  views.append(dict(choice=choice,selection=str(p),selection_sha256=sha(p)))
 save(HERE/'configs/bracket.json',dict(kind='bracket',views=views,draft_hc_schedule=candidate))
 return candidate

def sealed_identity(args):
 from cpu_seal import verify
 row=verify()
 require(args.profile=='tp2' and args.placement=='1' and args.timing=='token','fixed two-card token-timing identity required')
 binary=HERE/'build/device/own-rt-iq3';dispatch=LINEAGE/'dispatch-speed6.json';seal=LINEAGE/'screen-seal.json'
 for value,path in ((args.binary,binary),(args.dispatch,dispatch),(args.seal,seal)):
  require(value is None or value.resolve()==path,'sealed input differs')
 gate=module('p122_memory',P56/'memory_gate.py')
 configuration=gate.configuration(read(LINEAGE/'memory-plan.json'),4096,1,0)
 placement=dict(name='1',draft_rank=1,target_split=0,layer_boundary=24,target_layers=[24,24],context=4096,memory_admitted=True,supported=True,reason='packet122 selected-view full-shape checks',configuration=configuration,memory_gate=str(P56/'memory_gate.py'),memory_gate_sha256=sha(P56/'memory_gate.py'))
 return dict(placement=placement,timing='token',timing_modes=['token'],lineage=str(LINEAGE),seal=str(seal),seal_sha256=sha(seal),binary=str(binary),binary_sha256=sha(binary),dispatch=str(dispatch),dispatch_sha256=sha(dispatch),profile='tp2',selection_sha256=sha(LINEAGE/'selection.json'),memory_plan_sha256=sha(LINEAGE/'memory-plan.json'))

if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--candidate',choices=VALUES,required=True)
 prepare(ap.parse_args().candidate)
