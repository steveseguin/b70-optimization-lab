#!/usr/bin/env python3
"""Fresh-process and persistent-request exactness using tiny synthetic weights."""
import hashlib,json,os,subprocess,tempfile
from pathlib import Path
P=Path(__file__).resolve().parent

def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 binary=P/'build/gnu-host/own-rt-iq3';runs=[]
 with tempfile.TemporaryDirectory(prefix='p58-reset-',dir=P/'build') as tmp:
  t=Path(tmp);a=t/'a.tokens';b=t/'b.tokens';a.write_text('2 5 3 7 1\n');b.write_text('7 2 8 3 2\n')
  suite=t/'suite.tsv';suite.write_text(f'a {a}\nb {b}\n')
  env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'}
  base=[str(binary),'--mini','--pipeline-mini','--memory','resident','--context','32','--tokens','8','--retain-steps','1-8']
  for name,extra in [('fresh1',['--input',str(b)]),('fresh2',['--input',str(b)]),('suite',['--suite-inputs',str(suite)])]:
   out=t/name;r=subprocess.run(base+extra+['--output',str(out)],env=env,text=True,capture_output=True,timeout=60)
   if r.returncode:raise RuntimeError(name+': '+r.stdout+r.stderr)
   runs.append({'name':name,'exit_code':r.returncode})
  def result(dir):
   receipt=json.loads((dir/'receipt.json').read_text());assert receipt['passed'];return receipt['tokens']
  def hashes(dir):return [(p.relative_to(dir).as_posix(),hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(dir.glob('step*/*')) if p.is_file()]
  expected=result(t/'fresh1');expected_hashes=hashes(t/'fresh1');assert expected_hashes
  assert result(t/'fresh2')==expected==result(t/'suite/b')
  assert hashes(t/'fresh2')==expected_hashes==hashes(t/'suite/b')
  receipt={'schema':'packet58.request-reset-cpu.v1','passed':True,'device_executed':False,'synthetic_only':True,'runs':runs,'tokens':expected,'compared_fixture_files':len(expected_hashes),'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'comparison':'same prompt after different prompt equals two fresh processes, token IDs and all retained layer bytes'}
 (P/'request-reset-cpu.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':main()
