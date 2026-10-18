"""Real eleven-window queue loop with synthetic child/operational receipts.

Complements startup131's real parsers and CPU native startup. No subprocess,
service, journal or device executes. This does not admit a legacy chain.
"""
import contextlib,json,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from build131 import P,ROOT,sha,save,cpu_main
import queue_runner as q
import bundle_selection
def main():
 rows=[];names=q.EARLY+q.LATE
 for view in ('control','candidate'):
  selection=P/'selections'/view/'selection.json';selection_sha=sha(selection)
  for failed in (None,*names):
   with tempfile.TemporaryDirectory(prefix='p131-all-window-') as directory,contextlib.ExitStack() as stack:
    out=Path(directory)/'chain';now=[1000.];starts=[];commands=[]
    args=SimpleNamespace(authorized_device_window=True,prefix_windows=[],output_root=out,resume_from=None,phase='all',wait_oracle=False)
    def verify(row):
     assert row['selection_sha256']==selection_sha and row['queue_source_sha256']==sha(P/'queue_runner.py')
    def launch(cmd,**kwargs):
     name=cmd[cmd.index('--window')+1];starts.append(now[0]);commands.append(cmd)
     dest=out/name;dest.mkdir()
     row=dict(window=name,passed=name!=failed,device_executed=True,qualifying=True,card=0,context=4096,draft_rank=1,target_split=0,selection_sha256=selection_sha,queue_source_sha256=sha(P/'queue_runner.py'))
     (dest/'window.json').write_text(json.dumps(row));return SimpleNamespace(wait=lambda:0)
    for target,name,value in [(q.os,'getpriority',0),(q.os,'sched_getaffinity',q.DEVICE_CORES),(q,'user_unit_gate',None),(q,'input_preflight',None),(q,'prefix_prerequisites',{}),(q,'admitted_output',out),(q,'oracle_ready',True),(q,'journal','synthetic-cursor'),(bundle_selection,'selected',dict(draft_rank=1,target_split=0))]:
     stack.enter_context(patch.object(target,name,return_value=value))
    for target,value in [('p49_seal.verify',{}),('storage.precheck',{'passed':True}),('storage.early_retention_gate',{})]:stack.enter_context(patch(target,return_value=value))
    stack.enter_context(patch('window_adapter.verify_receipt',side_effect=verify))
    stack.enter_context(patch.object(q.subprocess,'Popen',side_effect=launch))
    stack.enter_context(patch.object(q.time,'time',side_effect=lambda:now[0]))
    stack.enter_context(patch.object(q.time,'sleep',side_effect=lambda seconds:now.__setitem__(0,now[0]+seconds)))
    try:q.run(args)
    except RuntimeError:
     assert failed is not None and (out/'STOP').exists()
    else:assert failed is None
    completed=json.loads((out/'queue-state.json').read_text())['completed']
    stop=len(names) if failed is None else names.index(failed)
    assert completed==list(names[:stop]) and len(commands)==stop+(failed is not None)
    assert all(b-a==90 for a,b in zip(starts,starts[1:]))
    # Retry of either completed or failed output must refuse before child launch.
    count=len(commands)
    try:q.run(args)
    except RuntimeError:pass
    else:raise AssertionError('queue retried prior output')
    assert len(commands)==count
    if failed is None:
     for name in names:
      file=out/name/'window.json';original=json.loads(file.read_text())
      for field in original:
       invalid=dict(original);invalid[field]=None;file.write_text(json.dumps(invalid))
       try:q.validate_success(name,out,0)
       except (AssertionError,RuntimeError):pass
       else:raise AssertionError('accepted changed receipt '+field)
      file.write_text(json.dumps(original))
      try:q.validate_success(name,out,1)
      except RuntimeError:pass
      else:raise AssertionError('accepted nonzero child')
    rows.append(dict(view=view,failed_window=failed,commands=commands,completed=completed,inter_window_gap=90,no_retry=True))
 sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'extended_queue131.py',P/'queue_runner.py',P/'window_adapter.py',*(P/'selections'/v/'selection.json' for v in ('control','candidate'))]}
 save(P/'evidence/extended-queue131.json',dict(passed=True,device_executed=False,operational_admission_synthetic=True,service_executed=False,windows_per_view=11,runs=rows,sources=sources))
 print('Both selections: eleven-window success, each failure position, invalid receipts and no retry PASS')
if __name__=='__main__':cpu_main();main()
