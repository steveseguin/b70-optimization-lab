"""Mini CPU full-state retention independence at both sealed-suite caps."""
import json,os,time
from pathlib import Path
from cancellation_retention_gate import P,invoke,state
from pipeline import sha,save
from storage import admit,discard
assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
binary=P/'build/gnu-host/own-rt-iq3';rows=[]
def inventory(root):
 return {str(rank):json.loads((root/f'rank{rank}/request-state-inventory.json').read_text()) for rank in (0,1)}
for controller in ('native','python'):
 for cap in (64,128):
  admit(30_000_000);root=P/'build'/('retention-caps-'+str(time.time_ns()));root.mkdir()
  baseline=invoke(binary,root/'none',True,controller,'none',cap,P/'build/input')
  expected=state(root/'none');inv=inventory(root/'none')
  assert len(baseline['tokens'])==cap and expected
  assert not list((root/'none').glob('rank*/step*/layer-*.bf16'))
  baseline_archive=discard(root/'none')
  for retain in ('1-8','1-8,97-104'):
   out=root/retain.replace(',','-');r=invoke(binary,out,True,controller,retain,cap,P/'build/input')
   assert r['tokens']==baseline['tokens'] and state(out)==expected and inventory(out)==inv
   files=len(list(out.glob('rank*/step*/layer-*.bf16')))
   assert files==(16 if cap==128 and ',' in retain else 8)*4
   rows.append(dict(controller=controller,max_new=cap,retain_steps=retain,retained_fixtures=files,tokens_equal=True,full_state_equal=True,baseline_archive=baseline_archive,archive=discard(out),final_state_sha256=expected))
  discard(root)
save(P/'retention-caps-gates.json',dict(passed=True,device_executed=False,cases=len(rows),requests=12,binary_sha256=sha(binary),source_sha256={n:sha(P/n) for n in ('retention_caps_gate.py','cancellation_retention_gate.py','pipeline.py')},rows=rows))
print(json.dumps(dict(passed=True,cases=len(rows),requests=12)))
