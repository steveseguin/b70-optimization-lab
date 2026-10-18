"""Read original packet118 trace and head-copy receipts without device contact."""
import hashlib,json,resource,statistics
from pathlib import Path
from timing_accounting import intervals
P=Path(__file__).resolve().parent;S=P.parent;ROOT=P.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 root=S/'screen/v4-lanes/evidence/p118-89f2d60778eb2d6e-composite-B-1-candidate'
 sources={}
 def load(p):sources[str(p.relative_to(ROOT))]=sha(p);return json.loads(p.read_text())
 summary=load(root/'summary.json');window=load(root/'window.json')
 assert window['passed'] and window['device_complete'] and window['files']['summary.json']==sha(root/'summary.json')
 assert summary['passed'] and summary['arithmetic']=='iq3-p49-split32-v1'
 rows=[r for request in summary['requests'] for r in intervals(request)]
 grouped={}
 for hit in (True,False):
  part=[r for r in rows if r['hit']==hit]
  grouped['hit' if hit else 'miss']=dict(count=len(part),mean_ms={k:statistics.mean(r[k] for r in part) for k in ('elapsed_ms','A','B','C','D','R','rank0_slack_ms','spec_start_offset_ms')})
 transfer=root/'run/ranks/rank0/p105-transfers.jsonl';sources[str(transfer.relative_to(ROOT))]=sha(transfer)
 assert window['files'][str(transfer.relative_to(root))]==sha(transfer)
 calls=[json.loads(line) for line in transfer.read_text().splitlines()];copies={}
 for leg in ('hidden-import','best-export'):
  values=[r['host_us']/1000 for r in calls if r['leg']==leg];assert values
  copies[leg]=dict(count=len(values),mean_ms=statistics.mean(values),minimum_ms=min(values))
 lower=sum(row['minimum_ms'] for row in copies.values());upper=grouped['hit']['mean_ms']['rank0_slack_ms']-lower
 model=load(S/'packet87-slack-model/DECISION.json');head=model['measured_head_ms']['target']
 result=dict(passed=True,device_executed=False,raw_source=str(root.relative_to(ROOT)),first99=grouped,copy_samples=copies,minimum_mandatory_copy_cost_ms=lower,apparent_hit_tail_less_known_copies_ms=upper,usable_slack_ms=None,reason='Rank0 suffix compute is absent from command envelopes. Apparent tail and copy-only upper bound are not usable idle time.',old_model_full_target_head_ms=head,candidate_added_rank0_head_time_sensitivity_ms={str(n):head*(n-46080)/248320 for n in (81920,122880)},scope='Original trace accounting and old linear row-cost sensitivity only, not new device measurements or a speed forecast',sources=sources)
 (P/'evidence/bundle7-traces.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:result[k] for k in ('first99','minimum_mandatory_copy_cost_ms','apparent_hit_tail_less_known_copies_ms','candidate_added_rank0_head_time_sensitivity_ms')},indent=2))
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));main()
