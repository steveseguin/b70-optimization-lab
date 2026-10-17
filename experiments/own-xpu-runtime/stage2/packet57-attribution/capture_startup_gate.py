"""Run the exact capture owner startup on one CPU mini owner; test failure cleanup."""
import base64,gzip,json,os,shutil,time
from pathlib import Path
import capture40 as capture
from cpu_gates import host
from storage import admit,verify_archive
P=capture.P;B=capture.B
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 admit(16_000_000);base=B/f'capture-startup-{time.time_ns()}';base.mkdir()
 binary=B/'gnu-host/own-rt-iq3';host(binary)
 stream=base/'streams.bf16';stream.write_bytes(bytes(128))
 table=base/'capture.tsv';table.write_text(''.join(f'{position} {token} 1 {stream.resolve()}\n' for position,token in enumerate((2,5,3))))
 rows=[]
 try:
  for fail in (False,True):
   root=base/('missing-receipt' if fail else 'success')
   command=['nice','-n','19','ionice','-c','3',str(binary),'--mini','--pipeline-mini','--draft-capture',str(table),'--rank','1','--context','256','--dispatch',str(P/'dispatch-p38.json'),'--output',str(root),'--seconds','300']
   if fail:command+=['--unknown-capture-startup-option']
   row=dict(passed=False,device_executed=False,output=str(root),command=command)
   caught=None
   try:capture.execute_owner(command,root,row,timeout=300)
   except RuntimeError as error:caught=str(error)
   assert not root.exists() and not root.with_name(root.name+'.log').exists(),'owner scratch/log not cleaned'
   archive=P/row['scratch_archive']['path'];verify_archive(archive)
   if fail:
    assert caught and 'without receipt.json' in caught and row['passed'] is False and row['returncode']!=0
    log_bytes=bytearray();collect=False
    with gzip.open(archive,'rt') as source:
     next(source)
     for line in source:
      item=json.loads(line)
      if item['kind']=='file':collect=item['path'].endswith('/capture.log')
      elif item['kind']=='chunk' and collect:log_bytes.extend(base64.b64decode(item['base64']))
      elif item['kind']=='end':collect=False
    assert b'unknown' in log_bytes.lower(),'startup failure log was not retained'
   else:
    assert caught is None and row['passed'] and row['returncode']==0 and len(row['fixture_sha256'])==26
    _,text=capture.archived_capture(row)
    assert len(text['draft-capture.jsonl'].splitlines())==3
   rows.append(dict(case='missing-receipt' if fail else 'exact-mini-startup',passed=True,owner_passed=row['passed'],archive=row['scratch_archive'],fixture_files=len(row.get('fixture_sha256',{})),failure=caught))
  existing=base/'foreign-output';existing.mkdir();marker=existing/'keep';marker.write_text('preserve')
  try:capture.execute_owner([],existing,{'passed':False})
  except AssertionError:pass
  else:raise AssertionError('preexisting output accepted')
  assert marker.read_text()=='preserve';rows.append(dict(case='preexisting-output-preserved',passed=True))
 finally:shutil.rmtree(base)
 capture.save(P/'capture-startup-gates.json',dict(passed=True,device_executed=False,cases=len(rows),rows=rows,binary_sha256=capture.digest(binary),source_sha256={name:capture.digest(P/name) for name in ('capture_startup_gate.py','capture40.py','main.cpp','mtp.hpp','dispatch-p38.json')},scope='Exact CPU mini capture startup, missing-receipt error and preserved startup log, archive-before-delete cleanup, and refusal to remove preexisting output'))
 print('capture startup and failure cleanup:3 gates PASS',flush=True)
if __name__=='__main__':main()
