"""Fresh new-chain startup on packet137's hash-verified CPU backend fixture.

No compile, model payload or device access. Execute the argv from real entry
probes, including banked KD's host-reference projection, with only backend and
weight payloads mocked. Legacy shared K fixtures retain their unchanged proofs.
"""
import json,os,resource,subprocess,sys,tempfile
from pathlib import Path
from source_decision import O,P,ROOT,sha,save
sys.path.insert(0,str(P))
UP=P.with_name('packet137-token-input')
FIXTURE=UP/'v5/build/full-shape/fixture'
def sources():
 return {str(f.relative_to(ROOT)):sha(f) for f in (Path(__file__),P/'selection.json',P/'bundle_selection.py',P/'kd_reference.py',P/'chain_pipeline.py',P/'window.py',P/'memory-plan.json',UP/'v5/evidence/full-shape.json',FIXTURE)}
def verify():
 row=json.loads((O/'evidence/native-startup.json').read_text());assert row['passed'] and row['device_executed'] is False and row['sources']==sources()
 from argument_gate import WINDOWS
 assert [r['window'] for r in row['windows']]==list(WINDOWS)
 assert all(r['passed'] for r in row['windows'])
 assert row['max_child_rss_kib']<4*1024*1024
 for window in row['windows']:
  assert sha(O/'evidence'/('arguments-'+window['window']+'.log'))==window['argument_log_sha256']
  if window.get('reused_unchanged'):
   assert sha(ROOT/window['receipt'])==window['receipt_sha256']
  for run in window.get('runs',[]):
   assert all(sha(ROOT/n)==h for n,h in run['input_metadata'].items())
 assert row['fresh_native_startups']>=15 and row['shared_fixtures_reused']==['K0','K1a','K1b','K2']
 return row

def main(only=None):
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 import shutil
 assert shutil.disk_usage('/').free>=25_000_000_000
 proof=json.loads((UP/'v5/evidence/full-shape.json').read_text());assert proof['passed'] and proof['device_executed'] is False and sha(FIXTURE)==proof['binary_sha256']
 from argument_gate import WINDOWS
 rows=[];count=0
 for name in WINDOWS:
  if only and name!=only:continue
  text=(O/'evidence'/('arguments-'+name+'.log')).read_text()
  argument=json.loads(next(x.removeprefix('ARGUMENT_RESULT=') for x in text.splitlines() if x.startswith('ARGUMENT_RESULT=')))
  assert argument['passed'] and argument['native_exec_intercepted']
  if name in ('K0','K1a','K1b','K2'):
   rows.append(dict(window=name,argument_log_sha256=sha(O/'evidence'/('arguments-'+name+'.log')),passed=True,reused_unchanged=True,fresh_native_run=False,receipt=str((UP/'v5/evidence/legacy-windows.json').relative_to(ROOT)),receipt_sha256=sha(UP/'v5/evidence/legacy-windows.json')));continue
  runs=[]
  for index,item in enumerate(argument['argv']):
   with tempfile.TemporaryDirectory(prefix='p139-native-startup-') as tmp:
    tmp=Path(tmp);selection=P/'selection.json'
    if name=='KD':
     from kd_reference import prepare
     selection,binding=prepare(selection,sha(selection),tmp)
     selected=json.loads(selection.read_text())
     assert selected['choices']['miss']=='banks-batch' and selected['choices']['token_input']=='both'
    cmd=list(item['argv']);start=next(i for i,v in enumerate(cmd) if Path(v).name=='own-rt-iq3');cmd=cmd[start:];cmd[0]=str(FIXTURE);cmd.insert(1,'--startup109')
    if '--authorized-device-window' in cmd:cmd.remove('--authorized-device-window')
    for flag,value in (('--selection',selection),('--selection-sha256',sha(selection)),('--dispatch',P/'dispatch-speed6.json'),('--output',tmp/'run')):
     if flag in cmd:cmd[cmd.index(flag)+1]=str(value)
    input_metadata={}
    for flag in ('--plan','--identity'):
     if flag in cmd:
      original=Path(cmd[cmd.index(flag)+1])
      source=original if original.is_file() else P.parent/'suite-inputs-20261012'/original.parent.name/original.name
      assert source.is_file(),str(source)
      cmd[cmd.index(flag)+1]=str(source)
      input_metadata[str(source.relative_to(ROOT))]=sha(source)
    if '--native-nice' in cmd:cmd[cmd.index('--native-nice')+1]='19'
    cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180,env=dict(os.environ,OMP_NUM_THREADS='2'))
    assert cp.returncode==0,(name,index,cp.stderr[-4000:])
    result=json.loads((tmp/'run/result.json').read_text());assert result['passed']
    files={f.name:sha(f) for f in (tmp/'run').iterdir() if f.is_file()}
    runs.append(dict(passed=True,index=index,command=cmd,result=result,artifact_hashes=files,selection=json.loads(selection.read_text()),original_argv=item['argv'],input_metadata=input_metadata))
    count+=1
  rows.append(dict(window=name,argument_log_sha256=sha(O/'evidence'/('arguments-'+name+'.log')),passed=True,runs=runs,fresh_native_run=True));print(name,'real production startup PASS',flush=True)
 if not only:
  save(O/'evidence/native-startup.json',dict(passed=True,device_executed=False,model_payload_read=False,compiled=False,fresh_native_startups=count,shared_fixtures_reused=['K0','K1a','K1b','K2'],windows=rows,sources=sources(),max_child_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,scope='Fresh actual new-chain argv and KD banked/token-input reference selection. Only numerical backend/payloads mocked; legacy shared K fixtures reused explicitly.'))
  verify()
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 main(sys.argv[1] if len(sys.argv)>1 else None)
