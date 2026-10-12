#!/usr/bin/env python3
"""Serial post-snapshot CPU qualification; no automatic retry or device run."""
import argparse,json,os,sys,time
from pathlib import Path
from seal40 import P,record_phase,save,sha
from storage import admit

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--start',default='cheap')
 ap.add_argument('--stop-after',default='')
 a=ap.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 py=sys.executable;b=P/'build'
 steps=[
  ('cheap',['cpu_campaign.py','cheap'],[]),
  ('real-intel',['real40_campaign.py','--compiler','icpx-host'],[]),
  ('p38kernels',['p38_kernel_gate.py'],['p38-kernel-gates.json','p30-attention-cpu.json','p30-small-cpu.json']),
  ('capacity',['capacity_gate.py'],['p38-qsa-capacity-gates.json']),
 ]
 for controller in ('native','python'):
  steps.append(('cancel-mini-'+controller,['cancellation_retention_gate.py','--binary',str(b/'gnu-host/own-rt-iq3'),'--controller',controller],['cancellation-retention-mini-'+controller+'.json']))
 steps += [
  ('cancel-real',['cancellation_retention_gate.py','--binary',str(b/'icpx-host/own-rt-iq3'),'--real','--controller','native'],['cancellation-retention-real-native.json']),
  ('cancel-inventory',['cancellation_inventory_gate.py'],['cancellation-inventory-gates.json']),
  ('retentioncaps',['retention_caps_gate.py'],['retention-caps-gates.json']),
  ('draftasync',['draft_async_gate.py','--binary',str(b/'gnu-host/own-rt-iq3'),'--output',str(P/'draft-async-gates-gnu.json')],['draft-async-gates-gnu.json']),
  ('captures40',['capture40.py','all'],[f'{prefix}-{prompt}.json' for prompt in ('incident-retrospective','code-review','customer-email','benchmark-analysis') for prefix in ('capture-run','capture-repeat','agreement')]),
  ('draftauth',['draft_auth_gate.py'],['draft-auth-gates.json']),
  ('suite',['cpu_campaign.py','suite'],[]),
  ('suite128-tail',['suite128_cpu_gate.py'],['suite128-tail-cpu-gates.json']),
  ('integrity',['qualification_extra40.py','integrity'],['resume-input-integrity.json']),
  ('pythonstandalone',['python_regression40.py'],[
   'receipt-metadata-gates.json','review-resume-storage-gates.json','review-resume-window-storage-gates.json',
   'draft-window-cleanup-gates.json','reset-retention-gate-results.json','suite-export-retention-gates.json',
   'storage-race-gates.json','suite-warmup-gates.json','cleanup-path-gates.json','suite-compiler-gates.json',
   'seal-bootstrap-gates.json','window-retention-gates.json','python-standalone-gates.json']),
  ('pythondiscovery',['python_tests.py'],['python-regression-gates.json']),
  ('fullwrapper',['full_wrapper_gate.py'],['full-wrapper-gates.json']),
 ]
 names=[s[0] for s in steps];assert a.start in names
 if a.stop_after:assert a.stop_after in names and names.index(a.stop_after)>=names.index(a.start)
 selected=steps[names.index(a.start):names.index(a.stop_after)+1 if a.stop_after else None]
 rows=[];stamp=time.time_ns()
 cancellation_cases=(('cancel-mini-native','cancellation-retention-mini-native.json','gnu-host'),
                     ('cancel-mini-python','cancellation-retention-mini-python.json','gnu-host'),
                     ('cancel-real','cancellation-retention-real-native.json','icpx-host'))
 def inventory_arguments():
  candidates=list(reversed(rows))
  for previous in sorted(P.glob('refresh40-campaign-*.json'),reverse=True):
   saved=json.loads(previous.read_text());candidates.extend(reversed(saved.get('rows',[])))
  arguments=[]
  for phase,receipt,compiler in cancellation_cases:
   current_sha=sha(P/receipt);current=json.loads((P/receipt).read_text())
   assert current.get('passed') is True and current.get('binary_sha256')==sha(b/compiler/'own-rt-iq3'), 'missing/stale cancellation prerequisite '+receipt
   matched=None
   for candidate in candidates:
    if candidate.get('phase')!=phase or candidate.get('passed') is not True:continue
    if candidate.get('receipt_sha256')!=current_sha:continue
    case=candidate.get('inventory_case','')
    if not case.startswith(receipt+':'):continue
    archive=candidate.get('reference_archive',{})
    path=P/archive.get('path','')
    if path.parent!=(P/'evidence') or not path.is_file() or sha(path)!=archive.get('sha256'):continue
    if path.name!=case.split(':',1)[1]+'-reference.jsonl.gz':continue
    matched=case;break
   assert matched, 'no exact receipt/archive-bound earlier cancellation phase for '+receipt
   arguments+=['--case',matched]
  return arguments
 for name,args,receipts in selected:
  admit(550_000_000)
  print('BEGIN refresh '+name,flush=True)
  if name=='cancel-inventory':args=[*args,*inventory_arguments()]
  command=[py,'-B',str(P/args[0]),*args[1:]]
  before=set((P/'evidence').glob('scratch-p40-cancellation-*-reference.jsonl.gz'))
  ledger=record_phase(name,command,receipts)
  row=dict(phase=name,passed=True,execution_start_unix_ns=ledger['start_unix_ns'])
  if name in {entry[0] for entry in cancellation_cases}:

   added=set((P/'evidence').glob('scratch-p40-cancellation-*-reference.jsonl.gz'))-before
   assert len(added)==1,'one fresh cancellation reference archive required'
   reference=added.pop()
   row['inventory_case']=receipts[0]+':'+reference.name.removesuffix('-reference.jsonl.gz')
   row['receipt_sha256']=sha(P/receipts[0])
   row['reference_archive']=dict(path=str(reference.relative_to(P)),sha256=sha(reference))
  rows.append(row)
  save(P/f'refresh40-campaign-{stamp}.json',dict(passed=len(rows)==len(selected),device_executed=False,rows=rows,planned=names[names.index(a.start):names.index(a.stop_after)+1 if a.stop_after else None],deferred=(['cheap: run separately after concurrent strict real proof so nested host-issue helper cannot change during that proof'] if 'cheap' not in [item[0] for item in selected] else [])+['draft-final: execute pipeline_draft_agreement.py only after fresh GNU and Intel MTP receipts plus captures; GNU campaign is scheduled separately']))
  print('END refresh '+name,flush=True)
 print(json.dumps(dict(passed=True,phases=len(rows),device_executed=False,deferred='draft-final awaits separately scheduled GNU MTP and fresh captures')),flush=True)

if __name__=='__main__':main()
