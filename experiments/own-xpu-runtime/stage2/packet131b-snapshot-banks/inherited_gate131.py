"""Replay packet124c's extended Python gate without writing its frozen tree.

The eleven-window legacy chain is unchanged and is not a new packet131 device
entry. Its complete Python paths/queue validators are replayed here; new bank
choices are covered by startup131 and the six actual packet131 screen entries.
"""
import json,subprocess,sys
from build131 import P,ROOT,BASE,sha,save,cpu_main
def main():
 ops=P.parents[1]/'ops/packet124c-orchestration';gate=ops/'argument_gate.py'
 names=('K0','K1a','K1b','K2','W0p','KD','W2m','WS','WSs','WS128x','WS128','old-k2','k2-replay','old-oracle','real-oracle','queue')
 rows=[]
 for name in names:
  cmd=[sys.executable,'-B',str(P/'queue_replay131.py')] if name=='queue' else [sys.executable,'-B',str(gate),'--probe',name]
  cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=240)
  log=P/'evidence'/('inherited-'+name+'.log');log.write_text(cp.stdout+cp.stderr)
  if name=='old-k2':
   assert cp.returncode and 'selection must name exactly route/recurrence/hc' in cp.stderr
   result=dict(expected_refusal=True)
  else:
   assert cp.returncode==0,cp.stderr[-3500:]+cp.stdout[-500:]
   result=json.loads(next(s.removeprefix('ARGUMENT_RESULT=') for s in cp.stdout.splitlines() if s.startswith('ARGUMENT_RESULT=')))
   assert result['passed']
  rows.append(dict(probe=name,command=cmd,returncode=cp.returncode,result=result,log=str(log.relative_to(ROOT)),log_sha256=sha(log)))
  print(name,'complete inherited gate PASS',flush=True)
 sources={};same=[]
 for f in BASE.glob('*.py'):
  local=P/f.name
  if local.is_file() and sha(local)==sha(f):
   same.append(f.name);sources[str(f.relative_to(ROOT))]=sha(f);sources[str(local.relative_to(ROOT))]=sha(local)
 for name in ('window.py','queue_runner.py','shared_oracle.py','p49_dispatch.py','check_inputs.py','chain103.py'):
  assert name in same,'inherited Python path changed: '+name
 for f in [P/'inherited_gate131.py',P/'queue_replay131.py',*ops.glob('*.py')]:sources[str(f.relative_to(ROOT))]=sha(f)
 save(P/'evidence/inherited-gate131.json',dict(passed=True,device_executed=False,frozen_tree_written=False,unchanged_python_files=same,sources=sources,runs=rows,scope='Replay unchanged packet124c chain paths, real oracle subprocess and queue validators. New-choice startup and actual packet131 screen argv are separate required gates.'))
if __name__=='__main__':cpu_main();main()
