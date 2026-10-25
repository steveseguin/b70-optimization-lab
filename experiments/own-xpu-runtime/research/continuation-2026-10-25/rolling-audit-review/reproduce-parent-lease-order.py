from copy import deepcopy
import json,hashlib
from pathlib import Path
from rolling_provider_trace_audit import audit_controller
from test_rolling_ring_socket import exercise
x,_=exercise(2,maximum=6)
commands=x['commands'];i=next(i for i,e in enumerate(commands) if e['event']=='issued' and e['op']==27)
seed=commands[i]['row']['id']
j=next(j for j,e in enumerate(commands) if j>i and e['event']=='issued' and e['op']==24 and e['stage']==1 and e['row']['id']==seed)
changed=deepcopy(commands);event=changed.pop(j);changed.insert(i,event)
result={'moved_final_row_issue_index':j,'before_provider_issue_index':i,'seed':seed}
try:
 audit_controller(changed,x['records'],x['batches'],[3,5,8,11],x['output_ids'],commands[0]['row']['request'],2,16,97,128,500)
 result['incorrectly_accepted']=True
except ValueError as error:result.update(incorrectly_accepted=False,refusal=str(error))
print(json.dumps(result))
