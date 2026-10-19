"""Focused CPU repair checks; never launches a device binary."""
import argparse,contextlib,importlib,json,os,subprocess,time,unittest
from pathlib import Path
from cpu_gates import host
from seal import sha
from storage import admit,discard
P=Path(__file__).resolve().parent;E=P/'evidence/20261012-k2-repair'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['unit','resident']);a=ap.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 if a.phase=='unit':
  for mods,name in [(['test_p38_k2','test_k2_selection','test_k2_admission'],'p38-k2-selection-tests.json'),(['test_k2_selection'],'k2-selection-tests.json'),(['test_k2_admission'],'k2-admission-tests.json'),(['test_window'],'window-tests.json')]:
   suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(m) for m in mods)
   with (E/('tests-'+name+'.log')).open('w') as f,contextlib.redirect_stdout(f),contextlib.redirect_stderr(f):r=unittest.TextTestRunner(stream=f,verbosity=2).run(suite)
   assert r.wasSuccessful(),name
   sources=[m+'.py' for m in mods]+(['k2_summary.py','k2-class-registry.json'] if 'k2' in name else ['window.py'])
   row=dict(passed=True,device_executed=False,tests=r.testsRun,command='nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B -m unittest '+' '.join(mods),sources_sha256={s:sha(P/s) for s in sources})
   (P/name).write_text(json.dumps(row,indent=2)+'\n');print(name,r.testsRun,'PASS',flush=True)
 else:
  rows=[]
  for compiler in ('gnu-host','icpx-host','asan'):
   binary=P/'build'/compiler/'k2-fixtures';host(binary);admit(10000000)
   out=P/'build'/('repair-resident-'+compiler+'-'+str(time.time_ns()));start=time.monotonic()
   cmd=['nice','-n','19','ionice','-c','3',str(binary),'--qsa-resident-smoke','--output',str(out)]
   with (E/('resident-'+compiler+'.log')).open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
   row=json.loads((out/'receipt.json').read_text());assert row['passed'] and row['resident_qsa_checks']==144 and not row['device_executed']
   row.update(compiler=compiler,binary_sha256=sha(binary),elapsed_seconds=time.monotonic()-start,output_sha256=sha(out/'output.bin'),command=cmd)
   row['scratch_archive']=discard(out);rows.append(row);print(compiler,'resident 144 PASS',flush=True)
  assert len({r['output_sha256'] for r in rows})==1
  (P/'resident-qsa-gates.json').write_text(json.dumps(dict(passed=True,device_executed=False,checks=432,rows=rows,sources_sha256={n:sha(P/n) for n in ('fixture_driver.cpp','repair_gates.py')}),indent=2)+'\n')
if __name__=='__main__':main()
