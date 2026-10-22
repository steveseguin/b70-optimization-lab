"""Run all eleven true chain entries under their exact closed launch env."""
import json,os,resource,subprocess,sys,tempfile,shutil
from pathlib import Path
from chain_adapter import P,O,ROOT,sha
from confirm136 import LIBRARIES

def main():
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2)
 assert shutil.disk_usage('/').free>=27_000_000_000
 from launch_identity import verify,UNIT
 env=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2',LD_LIBRARY_PATH=LIBRARIES)
 verify('0::/user.slice/user@1000.service/app.slice/'+UNIT,env)
 for group,e in [('0::/user@1000.service/wrong.service',env),('0::/user@1000.service/'+UNIT,dict(env,PYTHONDONTWRITEBYTECODE='1'))]:
  try:verify(group,e)
  except AssertionError:pass
  else:raise AssertionError('bad launch identity admitted')
 from argument_gate import WINDOWS
 rows=[]
 for name in WINDOWS:
  # Replay the actual shell handoff; substitute only its Python target with
  # this CPU interceptor, which calls the real chain_entry inside the sandbox.
  shell=(P/'coordinator_windows.sh').read_text()
  target='"$HERE/../../ops/packet190-orchestration/chain_entry.py" queue --authorized-device-window'
  assert shell.count(target)==1
  shell=shell.replace(target,'"'+str(O/'entry190.py')+'" --probe')
  with tempfile.TemporaryDirectory(prefix='packet190-shell-entry-') as tmp:
   wrapper=Path(tmp)/'coordinator_windows.sh';wrapper.write_text(shell)
   cp=subprocess.run(['/usr/bin/bash',str(wrapper),name],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
  (O/'evidence'/('entry190-'+name+'.log')).write_text(cp.stdout+cp.stderr)
  assert cp.returncode==0,name+': '+cp.stderr[-2500:]
  rows.append(json.loads(next(l.removeprefix('ENTRY190=') for l in cp.stdout.splitlines() if l.startswith('ENTRY190='))))
  print(name,'real-entry PASS',flush=True)
 sources={str(f.relative_to(ROOT)):sha(f) for f in [*P.glob('*.py'),O/'chain_entry.py',O/'chain_adapter.py',O/'argument_gate.py',O/'launch_identity.py',Path(__file__),O/'device-entry.sh',P/'coordinator_windows.sh'] if '/oracle/' not in str(f)}
 (O/'evidence/entry190.json').write_text(json.dumps(dict(passed=True,device_executed=False,unit=UNIT,lane='A',windows=rows,negative_unit_and_environment=True,actual_shell_handoff=True,sources=sources),indent=2)+'\n')
if __name__=='__main__':
 if '--probe' in sys.argv:
  resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2)
  from argument_gate import probe
  print('ENTRY190='+json.dumps(probe(sys.argv[-1],entry=True)))
 else:main()
