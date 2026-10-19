import json,math
from pathlib import Path
def partial(out,manifest):
 from suite_driver import CHECK,ORACLE
 completed=0
 for label in ('A0','B0','A1','B1','A2'):
  for entry in manifest['prompts']:
   d=out/'run'/label/entry['prompt_id']
   result=d/'result.json'
   if not result.exists():continue
   # Native writes a completion marker only after closing result.json.
   if not (d/'lookup-request-complete.json').exists():continue
   r=json.loads(result.read_text());expected=CHECK.token_record(ORACLE/'results'/entry['prompt_id'])
   if r['tokens']!=expected or r['cached_tokens']!=0:raise ValueError('live exactness')
   for leaf in ('timings.jsonl','prefill-timings.jsonl'):
    rows=[json.loads(s) for s in (d/leaf).read_text().splitlines()]
    if not rows or any(not math.isfinite(x['wall_ms']) or x['wall_ms']<0 for x in rows):raise ValueError('timing stream missing/invalid')
   completed+=1
 return dict(passed=True,complete_exact_requests=completed,checks='stream presence/format and exactness only')
