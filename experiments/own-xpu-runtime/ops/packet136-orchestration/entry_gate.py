"""Real confirm entry through CPU admission/oracle to both intercepted rank commands."""
import json,subprocess,sys
from pathlib import Path
from unittest.mock import patch
from source_decision import O,P,ROOT,sha,save
sys.path.insert(0,str(P))
def probe(index):
 import confirm136
 from bootstrap import install
 install()
 import common,smoke_screen,run_screen,smoke_validation,compare136
 from arguments136 import probe as native_probe
 screen=smoke_screen if index==-1 else run_screen.screen
 calls=[]
 def bridge(argv):
  args=screen.parser().parse_args(argv)
  assert args.authorized_device_window and not args.plan and args.lane=='A'
  assert args.output==confirm136.output(index)
  expected=confirm136.view('candidate' if index==-1 else confirm136.ORDER[index])
  assert args.lineage==expected and args.seal==expected/'screen-seal.json'
  identity=common.sealed(args);calls.append(dict(argv=argv,seal_sha256=identity['seal_sha256']))
  return native_probe(index=index)
 with patch.object(smoke_validation,'require_smoke'),patch.object(compare136,'load'),patch.object(screen,'main',side_effect=bridge):
  result=confirm136.main(['--index',str(index),'--output',str(confirm136.output(index)),'--fault-review','/synthetic/CPU-review.json','--authorized-device-window'])
 assert len(calls)==1 and result['native_exec_intercepted'] and len(result['argv'])==2
 result.update(entry='confirm136.main',entry_calls=calls,readiness_verified=True,real_complete_oracle=True,service_wrapper_synthetic=True,predecessors_synthetic=index>=0)
 return result
def sources():
 from source_gate136 import verify_sources
 return verify_sources({str(f.relative_to(ROOT)):sha(f) for f in [O/'entry_gate.py',O/'verify_cpu.py',O/'cpu-tests.json',P/'confirm136.py',P/'arguments136.py',P/'compare136.py',P/'source_gate136.py']})
def verify():
 row=json.loads((O/'evidence/confirm-entries.json').read_text())
 assert row['passed'] and row['device_executed'] is False and row['sources']==sources()
 assert [r['index'] for r in row['windows']]==list(range(-1,5))
 assert all(r['native_exec_intercepted'] and len(r['argv'])==2 for r in row['windows'])
 return row
def main():
 rows=[]
 for i in range(-1,5):
  cp=subprocess.run([sys.executable,'-B',str(O/'entry_gate.py'),'--probe',str(i)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=240)
  (O/'evidence'/f'confirm-entry-{i}.log').write_text(cp.stdout+cp.stderr)
  assert cp.returncode==0,cp.stdout[-1000:]+cp.stderr[-4000:]
  rows.append(json.loads(next(x.removeprefix('ENTRY_RESULT=') for x in cp.stdout.splitlines() if x.startswith('ENTRY_RESULT='))))
  print('confirm entry',i,'reaches both intercepted native calls',flush=True)
 save(O/'evidence/confirm-entries.json',dict(passed=True,device_executed=False,windows=rows,sources=sources()));verify()
if __name__=='__main__':
 if '--probe' in sys.argv:print('ENTRY_RESULT='+json.dumps(probe(int(sys.argv[-1]))))
 else:main()
