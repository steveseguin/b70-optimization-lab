"""Review26/27 selection, one-lane brackets and exact other-lane smoke.

The product is an admission estimate, never a measured composed speed. No idle
exception: this packet's requested readiness policy always requires >=2%.
"""
import argparse,json,math,sys
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=Path('/home/steve/llm-optimizations');P=ROOT/'experiments/own-xpu-runtime/stage2/packet143-record-bundle'
sys.path.insert(0,str(P))
from compositions import BASE,DIMENSIONS,key,read,sha,save,validate

def qualify_bracket(row):
 r=row['result'];views=r['views']
 if not(r['passed'] is True and r['kind']=='bracket' and r['model_lifetimes']==1 and len(views)==5):raise ValueError('complete one-load five-view bracket required')
 if [v['choice'] for v in views]!=['control','candidate','control','candidate','control']:raise ValueError('C/X/C/X/C required')
 for i,v in enumerate(views):
  if not(v['index']==i and v['lane']=='B' and v['all_13_exact'] is True and v['exact_count']==13):raise ValueError('all 13 outputs must be exact in every lane-B view')
  if type(v['rate']) not in (float,int) or not math.isfinite(v['rate']) or v['rate']<=0:raise ValueError('invalid rate')
  if not v['acceptance_counts'] or v['acceptance_counts']!=views[0]['acceptance_counts']:raise ValueError('acceptance changed')
  if not v['draft_proposals'] or v['draft_proposals']!=views[0]['draft_proposals']:raise ValueError('draft proposals changed')
 controls=[v['rate'] for v in views[::2]];candidates=[v['rate'] for v in views[1::2]]
 ratio=min(candidates)/max(controls);drift=max(controls)/min(controls)-1
 if not math.isfinite(ratio) or not math.isfinite(drift):raise ValueError('nonfinite derived ratio')
 if drift>0.01+1e-12:raise ValueError('control drift exceeds 1%')
 if ratio<1.005-1e-12:raise ValueError('every candidate must beat every control by at least 0.5%')
 return dict(passed=True,strict_ratio=ratio,strict_gain_percent=100*(ratio-1),control_drift_percent=100*drift,controls=controls,candidates=candidates,evidence={k:row[k] for k in ('window_sha256','summary_sha256','selection_sha256','evidence_path','coordination_sha256')})
def choose(evidence):
 selection=dict(BASE);winners={};rejected={}
 for dimension in DIMENSIONS:
  try:
   row=evidence(dimension);winners[dimension]=qualify_bracket(row);selection[dimension]='both' if dimension=='token_input' else 'order600'
  except (OSError,ValueError,AssertionError,KeyError,TypeError) as e:rejected[dimension]=str(e) or type(e).__name__
 return dict(selection=selection,winners=winners,rejected=rejected,combined_ratio=math.prod(r['strict_ratio'] for r in winners.values()),gain_kind='product of component strict gains; not measured composed performance')
def evidence(dimension):
 from evidence_reader143 import bracket
 row=read(P/'lineage-inputs/component-registration.json')[dimension]
 return bracket(Path(row['evidence_directory']),dimension)
def evaluate():
 row=dict(schema='packet143.ready.v1',ready=False,cpu_preparation_ready=False,device_executed=False,record_tok_s=58.798109,minimum_combined_ratio=1.02,chain_output=str(P/'build/device-cards01-p143-a'),lane_B_pause='decided at launch from current lane state; never captured by preparation')
 try:
  from cpu_prepare143 import verify
  verify();row['cpu_preparation_ready']=True
  from argument_gate import verify as arguments
  arguments()
  limits=read(O/'evidence/launch-limits.json');assert limits['passed'] and not limits['device_executed']
  for n,h in limits['sources'].items():assert sha(ROOT/n)==h,'launch-limit sources changed'
  decision=choose(evidence);row.update(decision)
  if not decision['winners']:raise ValueError('no qualifying winners')
  from cpu_prepare143 import verify
  verify();row['cpu_preparation_ready']=True
  from evidence_reader143 import smoke
  row['smoke']=smoke(P/'evidence'/('device-smoke-A-'+key(row['selection'])),row['selection'])
  if not math.isfinite(row['combined_ratio']) or row['combined_ratio']<1.02-1e-12:raise ValueError('combined strict gain is below +2% over the pinned 58.798109 record')
  from storage import precheck
  row['storage']=precheck()
  if not row['storage']['passed']:raise ValueError('fresh chain storage reserve unavailable')
  if Path(row['chain_output']).exists():raise ValueError('record chain folder is not fresh')
  from compositions import selected
  if selected()!=row['selection']:raise ValueError('active chain selection differs from evidence; activate the selected sealed composition first')
  row['ready']=True
 except (OSError,ValueError,AssertionError,KeyError,TypeError) as e:row['reason']=str(e) or type(e).__name__
 return row
def verify():
 stored=read(O/'ready.json');actual=evaluate()
 if not(stored['ready'] is True and actual['ready'] is True):raise ValueError(actual.get('reason','stored readiness false'))
 if stored!=actual:raise ValueError('readiness evidence changed; regenerate deliberately')
 return actual
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--refresh',action='store_true');a=ap.parse_args()
 if a.refresh:result=evaluate();save(O/'ready.json',result);print(json.dumps(result,indent=2))
 else:
  try:print(json.dumps(verify(),indent=2))
  except (OSError,ValueError,AssertionError,KeyError,TypeError) as e:raise SystemExit('REFUSED: '+str(e))
