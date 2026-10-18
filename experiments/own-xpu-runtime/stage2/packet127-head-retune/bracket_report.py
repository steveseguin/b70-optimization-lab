"""Read-only exactness/speed decision, plus hit/miss and rank command budgets.
No resource limit is set by import; device launchers may safely import this.
"""
import argparse,json,statistics,hashlib
from pathlib import Path
from build_engine import P,ROOT,sha
from screen_jobs import jobs,output,view,verify
from timing_accounting import intervals

def gains_pass(rates):
 return len(rates)==3 and all(x>0 for x in rates) and all(rates[1]>=x*1.005 for x in (rates[0],rates[2]))

def paths(requests):
 rows=[r for request in requests for r in intervals(request)]
 out={}
 for hit,label in [(True,'hit'),(False,'miss')]:
  subset=[r for r in rows if r['hit']==hit]
  out[label]=dict(n=len(subset),mean_ms={k:statistics.mean(r[k] for r in subset) if subset else None for k in ('elapsed_ms','A','B','C','D','R','rank0_slack_ms','unresolved_control_gaps_ms')})
 return dict(intervals=len(rows),paths=out,definitions=dict(A='next rank0 speculative HALF',B='rank1 target HALF including head',C='rank0 corrected HALF on miss',D='rank1 draft',R='rank0 rollback'),timing_scope='host command envelopes; GPU work, transfers and waits overlap; not GPU idle')

def acceptance(request):
 return [(r['position'],r['guess'],r['hit']) for r in request['guess_rows']]

def bracket(lane,winner=None):
 verify()
 if lane=='A' and winner is None:
  result=bracket('B');assert result['passed'];winner=result['winner']
 from common import D,sealed
 from types import SimpleNamespace
 records=[];source_hashes={};accept=[]
 for job in jobs(lane,winner):
  dest=output(job)
  for n in ('window.json','identity.json','summary.json'):
   path=dest/n;assert path.is_file(),'pending '+str(path);source_hashes[str(path.relative_to(ROOT))]=sha(path)
  window=json.loads((dest/'window.json').read_text());identity=json.loads((dest/'identity.json').read_text());summary=json.loads((dest/'summary.json').read_text())
  assert window['passed'] is True and window['device_executed'] is True and window['device_complete'] is True and window['lease_released'] is True
  def bound(path):
   assert window['files'][str(path.relative_to(dest))]==sha(path),'lifecycle artifact changed: '+str(path)
   source_hashes[str(path.relative_to(ROOT))]=sha(path)
  bound(dest/'summary.json');bound(dest/'identity.json')
  lineage=view(job['choice']);expected=sealed(SimpleNamespace(lineage=lineage,seal=lineage/'screen-seal.json',binary=None,dispatch=None,profile='tp2',timing='token',placement=job['placement']))
  assert all(identity.get(k)==v for k,v in expected.items()) and identity['lane']==lane
  assert summary['passed'] is True and summary['arithmetic']=='iq3-p49-split32-v1' and summary['kv_dtype']=='BF16'
  assert summary['request_count']==12 and summary['requested_max_new']==128 and summary['cached_tokens']==0
  assert summary['prompt_kv_response_reuse'] is False
  requests=summary['requests'];assert [r['prompt_id'] for r in requests]==list(D.CHECK.PROMPT_IDS)
  for r in requests:
   assert r['passed'] and r['exact_oracle'] and r['cached_tokens']==0
   tokens=D.CHECK.token_record(D.ORACLE/'results'/r['prompt_id'])
   assert len(r['tokens'])==128 and r['tokens']==tokens[:128]
  accept.append([acceptance(r) for r in requests])
  memory=dest/'run/ranks/device-memory-admission.json';assert memory.is_file();source_hashes[str(memory.relative_to(ROOT))]=sha(memory)
  bound(memory);admission=json.loads(memory.read_text());assert admission['passed'] and [r['rank'] for r in admission['ranks']]==[0,1]
  from memory_gate import check as admit
  ledger=json.loads((lineage/'memory-plan.json').read_text())
  for rank,row in enumerate(admission['ranks']):
   census=dest/'run/ranks'/f'rank{rank}'/'census.json';bound(census)
   recalculated=admit(json.loads(census.read_text()),ledger,rank,True,4096,1,expected['placement']['target_split'])
   assert all(row.get(k)==v for k,v in recalculated.items()),'recorded memory admission differs from raw census'
  from memory_observation import validate
  from conditions import LANES
  observations={}
  for phase in ('ready','after-suite'):
   f=dest/'run'/f'memory-{phase}.json';assert f.is_file();source_hashes[str(f.relative_to(ROOT))]=sha(f);bound(f);observations[phase]=json.loads(f.read_text())
   validate(observations[phase],phase,admission,LANES[lane]['pci'])
  rate=summary['class_balanced_tok_s_1_100_intervals_after_ttft']['median']
  records.append(dict(choice=job['choice'],rate=rate,first99=paths(requests),memory=admission,memory_observations=observations))
 assert all(a==accept[0] for a in accept),'placement changed draft acceptance or determinism'
 rates=[r['rate'] for r in records]
 candidates=[]
 for index in range(1,len(records)-1):
  gains=[100*(rates[index]/r-1) for r in (rates[0],rates[-1])]
  candidates.append(dict(choice=records[index]['choice'],rate=rates[index],passed=all(rates[index]>=r*1.005 for r in (rates[0],rates[-1])),gains_percent=gains))
 winners=sorted((r for r in candidates if r['passed']),key=lambda r:(-r['rate'],int(r['choice'])))
 return dict(passed=bool(winners),winner=winners[0]['choice'] if winners else None,complete=True,device_executed=True,lane=lane,exact=True,acceptance_identical=True,threshold_percent=.5,candidates=candidates,runs=records,sources=source_hashes,qualifying=False,submission_eligible=False)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--lane',choices=('A','B'),required=True);ap.add_argument('--winner',choices=('81920','122880'));a=ap.parse_args()
 print(json.dumps(bracket(a.lane,a.winner),indent=2))
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 main()
