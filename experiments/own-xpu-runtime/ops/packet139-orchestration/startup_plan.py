"""Plan through every real chain startup path; never execute a native process."""
import json,subprocess,sys
from source_decision import O,P

def environment():
 import shlex
 from confirm136 import LIBRARIES
 tokens=shlex.split((O/'device-entry.sh').read_text().replace('\\\n',' '));begin=tokens.index('env');end=tokens.index('python3',begin)
 env=dict(t.split('=',1) for t in tokens[begin+2:end])
 assert env==dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2',LD_LIBRARY_PATH=LIBRARIES)
 return env

def verify_startup_paths():
 from argument_gate import WINDOWS
 rows=[]
 for name in WINDOWS:
  cp=subprocess.run([sys.executable,'-B',str(O/'argument_gate.py'),'--probe',name],env=environment(),stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
  if cp.returncode:raise ValueError('real '+name+' startup refused: '+cp.stderr[-4000:])
  row=json.loads(next(x.removeprefix('ARGUMENT_RESULT=') for x in cp.stdout.splitlines() if x.startswith('ARGUMENT_RESULT=')))
  assert row['native_exec_intercepted'] and row['startup']['reservation']['window']==name
  rows.append(row)
 return rows
