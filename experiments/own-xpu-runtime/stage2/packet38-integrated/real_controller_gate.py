"""Real arithmetic-v2 target: each native mode versus current Python receipt."""
import json,time,fcntl
from pathlib import Path
from gates import P,B,ORACLE,invoke
from pipeline import sha
from compare_controllers import signature
from storage import admit,discard
rows=[]
for mode in ('none','ngram','hit','miss','mtp'):
 draft_lock=None
 if mode=='mtp':
  draft_lock=(B/'cpu-mtp.lock').open('a');fcntl.flock(draft_lock,fcntl.LOCK_EX)
 reference=json.loads((P/f'real-{mode}.json').read_text());assert reference['passed']
 expected=json.loads((ORACLE/'result.json').read_text())['tokens'][:8]
 script=B/('native-real-'+mode+'.txt')
 if mode in ('hit','miss'):script.write_text(' '.join(map(str,expected[:7] if mode=='hit' else [(t+1)%248320 for t in expected[:7]])))
 out=B/('real-native-'+mode+'-'+str(time.time_ns()));binary=B/'gnu-host/own-rt-iq3'
 admit(450_000_000)
 result=invoke(binary,out,'script' if mode in ('hit','miss') else mode,script if mode in ('hit','miss') else None,mini=False,oracle=ORACLE,controller='native')
 left=reference['controller_signature'];right=signature(out)
 assert len(left['final_states'])==2 and left['final_state_bytes'];assert left==right,(mode,[k for k in left if left[k]!=right[k]])
 row=dict(mode=mode,passed=True,tokens=len(result['tokens']),fixtures=len(right['fixtures']),stats=right['counts'],binary_sha256=sha(binary),python_receipt_sha256=sha(P/f'real-{mode}.json'),native_receipt_sha256=sha(out/'receipt.json'),root=str(out),device_executed=False)
 (P/f'real-native-{mode}.json').write_text(json.dumps(row,indent=2)+'\n');rows.append(row);discard(out);print(mode,'PASS',flush=True)
 if draft_lock:draft_lock.close()
(P/'real-controller-gates.json').write_text(json.dumps(dict(passed=True,device_executed=False,rows=rows),indent=2)+'\n')
