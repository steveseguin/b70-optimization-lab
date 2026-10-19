"""Every actual queue native flag is supported by the built executable's --help."""
import json,subprocess,sys
from pathlib import Path
from build_engine import P,sha,save
from launch_env import environment

def main():
 row=json.loads((P/'screen/evidence/argument-gate.json').read_text());checks=[]
 for r in row['records']:
  argv=r['observations'][-1]['argv'];start=2 if argv[:2]==['ionice','-c3'] else 0
  binary=P/'build/device'/Path(argv[start]).name;assert binary.name in ('own-rt-iq3','p58-cache-fixtures')
  cp=subprocess.run([str(binary),'--help'],stdin=subprocess.DEVNULL,capture_output=True,text=True,env=environment());assert cp.returncode==0
  flags=[a for a in argv[start+1:] if a.startswith('--')]
  assert set(flags)<=set(cp.stdout.split()),(flags,cp.stdout)
  checks.append(dict(candidate=r['candidate'],window=r['window'],flags=flags,binary_sha256=sha(binary),passed=True))
 save(P/'evidence/flags.json',dict(passed=True,device_executed=False,checks=checks))
 print('PASS every real native argument checked against built --help')
if __name__=='__main__':main()
