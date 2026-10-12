"""CPU mocks: KD stop/drain cannot be bypassed by failed receipt writes."""
import ast,hashlib,json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import draft_window as kd
P=Path(__file__).resolve().parent

def main():
 rows=[]
 for label,receipt_error,latch_error,write_error,stalled in (
     ('normal',False,False,False,False),
     ('disk-full-and-journal-error',True,True,False,False),
     ('stop-write-error',True,True,True,False),
     ('bounded-retained-owner',True,True,False,True)):
  events=[];child=Mock(pid=1234)
  child.poll=Mock(side_effect=(lambda:None) if stalled else [None,None,0,0])
  def save(*unused):
   events.append('receipt')
   if receipt_error:raise OSError('No space left on device')
  def latch(*unused):
   events.append('latch')
   if latch_error:raise OSError('journal failed')
  def write(*unused):
   events.append('stop')
   if write_error:raise BrokenPipeError('closed pipe')
  ticks=iter(range(0,200,10))
  with patch.object(kd,'save',save),patch.object(kd.os,'write',write),patch.object(kd.os,'close') as close,patch.object(kd.time,'sleep'),patch.object(kd.time,'monotonic',side_effect=lambda:next(ticks)):
   watch=SimpleNamespace(latch=latch,poll_kernel=Mock(side_effect=OSError('journal failed')))
   kd.failed_owner(child,P,watch,ValueError('initial fault'),9)
   assert events[:3]==['latch','receipt','stop'] and events[-1]=='receipt'
   assert child.poll.call_count>=3 and watch.poll_kernel.call_count>=1
   assert close.call_count==int(write_error)
   if stalled:assert child.poll.call_count<12
  rows.append(dict(case=label,passed=True,cooperative_stop=True,bounded_drain=True))
 # Ensure post-Popen bookkeeping is protected too, the failure that caused the
 # original ENOSPC teardown escape. This is additional structural coverage.
 tree=ast.parse((P/'draft_window.py').read_text())
 guarded=[n for n in ast.walk(tree) if isinstance(n,ast.Try) and any(isinstance(h.type,ast.Name) and h.type.id=='Exception' for h in n.handlers)]
 assert any('children.json' in ast.unparse(n.body) and 'failed_owner(child' in ast.unparse(n.handlers) for n in guarded)
 # Retained CPU captures keep their executed hash under a hash-bound relink proof.
 import tempfile
 with tempfile.TemporaryDirectory(dir=P/'build') as tmp:
  root=Path(tmp);proof={'passed':True,'model_binary_mapping':{'gnu-host':{'executed_sha256':'old','current_sha256':'new'}}}
  blob=root/'proof.json';blob.write_text(json.dumps(proof));binding=dict(proof,path='proof.json',sha256=kd.sha(blob))
  build={'artifacts_sha256':{'gnu-host/own-rt-iq3':'new'},'model_gate_carry_forward':binding}
  with patch.object(kd,'P',root):
   assert kd.reference_binary(build)=='old'
   for mutation in ('blob','current','mapping'):
    candidate=json.loads(json.dumps(build))
    if mutation=='blob':candidate['model_gate_carry_forward']['sha256']='wrong'
    elif mutation=='current':candidate['artifacts_sha256']['gnu-host/own-rt-iq3']='wrong'
    else:candidate['model_gate_carry_forward']['model_binary_mapping']['gnu-host']['executed_sha256']='wrong'
    try:kd.reference_binary(candidate)
    except ValueError:pass
    else:raise AssertionError('accepted wrong relink '+mutation)
   assert kd.reference_binary({'artifacts_sha256':{'gnu-host/own-rt-iq3':'same'}})=='same'
  rows.append(dict(case='hash-bound-relink-reference-and-tamper-refusal',passed=True))
 result=dict(passed=True,device_executed=False,gates=len(rows)+1,rows=rows,post_launch_bookkeeping_guarded=True,source_sha256={name:hashlib.sha256((P/name).read_bytes()).hexdigest() for name in ('draft_window.py','test_draft_window_cleanup.py')})
 (P/'draft-window-cleanup-gates.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result))
if __name__=='__main__':main()
