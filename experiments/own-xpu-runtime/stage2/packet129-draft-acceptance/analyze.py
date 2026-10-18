"""Paired acceptance counts only. No timing-based candidate decision."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
def paired(native,shadow,prompt_length,output_count=128):
 rows={r['draft_position']:r for r in shadow}
 if len(rows)!=len(shadow):raise ValueError('duplicate shadow position')
 selected=[]
 for r in native['draft_rows']:
  # Native publication.position = draft_position + 2. Include only predictions
  # for generated target tokens, including the final verified token.
  if r['position']<prompt_length:continue
  s=rows.pop(r['position']-2,None)
  if s is None or s.get('restored_exact') is not True:raise ValueError('missing/restoration-failed shadow')
  if r['provider_error'] or r['guess'] is None or s['production']!=r['guess']:raise ValueError('production guess changed')
  actual=r['actual']
  if type(actual) is not int or actual<0:raise ValueError('missing target verification')
  # The terminal target token has no next speculative HALF. Retain its shadow
  # integrity check but exclude it from the used-proposal denominator.
  if r['hit'] is not None:
   selected.append(dict(position=r['position'],actual=actual,production=s['production'],candidate=s['candidate'],production_hit=s['production']==actual,candidate_hit=s['candidate']==actual))
 if rows:raise ValueError('unmatched shadow rows')
 if not 1<=output_count<=128 or len(selected) not in (output_count-1,output_count):raise ValueError(f'incomplete paired request: {len(selected)}')
 return dict(verified=len(selected),production_hits=sum(r['production_hit'] for r in selected),candidate_hits=sum(r['candidate_hit'] for r in selected),rows=selected)
def decide(requests):
 groups={k:[r for r in requests if r['group']==k] for k in ('independent','secondary')}
 if len(groups['independent'])!=10 or len(groups['secondary'])!=12:raise ValueError('complete preregistered corpus required')
 result={}
 for group,rows in groups.items():
  n=sum(r['paired']['verified'] for r in rows);a=sum(r['paired']['production_hits'] for r in rows);b=sum(r['paired']['candidate_hits'] for r in rows)
  if any(not 0<=r['paired']['verified']<=128 for r in rows):raise ValueError('invalid denominator')
  if n==0:raise ValueError('no verified proposals')
  result[group]=dict(verified=n,production_hits=a,candidate_hits=b,production_acceptance=a/n,candidate_acceptance=b/n,gain_percentage_points=100*(b-a)/n)
 independent=result['independent']
 if independent['verified']<512:raise ValueError('fewer than 512 independent verified proposals; no verdict')
 passes=(independent['candidate_hits']-independent['production_hits'])*1000>=15*independent['verified']
 return dict(passed=True,acceptance_gate_passed=passes,decision='advance-to-format-and-timing-gates' if passes else 'close-candidate',groups=result,performance_claim=False,realistic_final_gate=dict(passed=False,reason='paired shadow diagnostic; 128-token cap; no performance claim'),target_oracle='iq3-p49-split32-v1',production_drives_every_step=True)
def summarize(rows,incident,profile):
 return decide(rows)
if __name__=='__main__':
 source=P/'evidence/device-B/run/report-inputs.json'
 result=decide(json.loads(source.read_text())['requests'])
 (P/'evidence/acceptance-result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
