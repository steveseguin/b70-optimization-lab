import argparse,hashlib,json,re
from pathlib import Path
ROOT=Path('/home/steve/b70-optimization-lab')
PACKET=ROOT/'experiments/qwen38-27b-b70/data/2026-10-07-history-study'
OUTPUT=Path('/mnt/fast-ai/bench-results/context-history-study-v1-20261007/diagnostic')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=OUTPUT);parser.add_argument('--packet',type=Path,default=PACKET);parser.add_argument('--report',type=Path,default=Path('/tmp/history-study-answer-errors.json'));args=parser.parse_args()
OUTPUT=args.out;PACKET=args.packet
plan=json.loads((PACKET/'plan.json').read_text())
rows=[]
for item in plan['trials']:
 native=OUTPUT/item['native_result_path']
 if not native.exists():continue
 taskpath=PACKET/(item['case_id']+'-task.json');task=json.loads(taskpath.read_text());result=json.loads(native.read_text())
 owners={};initial={};closes={};reviews={};evidence={}
 for b in task['batches']:
  for line in b['text'].splitlines():
   m=re.fullmatch(r'(ticket-[a-z]+-[a-z]) belongs to counter ([a-z]+\d{2})\.',line)
   if m:owners[m[1]]=m[2];initial[m[1]]=m[2]
   m=re.fullmatch(r'(ticket-[a-z]+-[a-z]) was transferred to ([a-z]+\d{2}), effective before this batch ended\.',line)
   if m:owners[m[1]]=m[2];evidence.setdefault(m[1],[]).append({'batch':b['id'],'text':line})
   m=re.fullmatch(r'(review-[a-z]+-\d+) concerns (ticket-[a-z]+-[a-z])\.',line)
   if m:reviews[m[1]]=m[2]
  closes[b['id']]=dict(owners)
 calls=[json.loads(line) for line in (native.parent/'calls.jsonl').read_text().splitlines()]
 actions=[]
 for c in calls:
  if c['phase']!='answer':continue
  try:action=json.loads(c['response'])
  except (TypeError,ValueError):continue
  actions.append({k:action[k] for k in ('action','batch_id','counters','query') if k in action})
 errors=[]
 for q in task['questions']:
  predicted=result['answers'].get(q['id']);expected=task['oracle']['answers'][q['id']]
  if type(predicted) is type(expected) and predicted==expected:continue
  error={'question_id':q['id'],'category':q['category'],'question':q['text'],'predicted':predicted,'expected':expected}
  if q['category']=='join':
   review=re.search(r'Follow (review-[a-z]+-\d+)',q['text'])[1]
   batch=int(re.search(r'end of batch (\d+)',q['text'])[1]);ticket=reviews[review]
   owner=closes[batch][ticket];first=initial[ticket];final=owners[ticket];state=task['oracle']['after_batch'][batch-1]
   assert state[owner]==expected
   error.update(ticket=ticket,target_batch=batch,correct_owner=owner,initial_owner=first,final_owner=final,
    initial_owner_balance=state[first],final_owner_balance=state[final],
    matches_initial_owner_balance=type(predicted) is int and predicted==state[first],
    matches_final_owner_balance=type(predicted) is int and predicted==state[final],
    ownership_transfers=evidence.get(ticket,[]))
  errors.append(error)
 rows.append({'case_id':item['case_id'],'condition':item['condition'],'native_result_sha256':sha(native),
  'calls_sha256':sha(native.parent/'calls.jsonl'),'task_sha256':sha(taskpath),'status':result['status'],
  'score':result['score'],'checkpoints_exact':result['all_checkpoint_states_exact'],
  'actions':actions,'errors':errors})
report={'schema':'history-study-answer-error-analysis.v1','source_output':str(OUTPUT.parent),
 'scope':'Post-hoc diagnostic, not a new gate. Matching wrong-owner balance is an observed correspondence; causal claims require raw source/retrieval review.',
 'completed_native_rows':len(rows),'rows':rows}
args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
for r in rows:
 print(r['case_id'],r['condition'],'errors',len(r['errors']),[(e['question_id'],e.get('matches_initial_owner_balance')) for e in r['errors']])
