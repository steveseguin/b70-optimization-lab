#!/usr/bin/env python3
"""Serial CPU rebuild/requalification for the K1a HC repair; never enters a device binary."""
import argparse,json,os,subprocess,sys,time,unittest
from pathlib import Path
from storage import admit,digest
from cpu_gates import host
P=Path(__file__).resolve().parent;E=P/'evidence/hc-activation-fix';PREFIX=['nice','-n','19','ionice','-c','3']
def run(name,args):
 admit(10_000_000);start=time.time();log=E/(name+'.log')
 print('START',name,flush=True)
 with log.open('w') as out:r=subprocess.run(PREFIX+list(map(str,args)),cwd=P,stdout=out,stderr=subprocess.STDOUT,env={**os.environ,'OMP_NUM_THREADS':'2'})
 row=dict(stage=name,exit_code=r.returncode,seconds=time.time()-start,command=PREFIX+list(map(str,args)),log=str(log.relative_to(P)),log_sha256=digest(log),device_executed=False)
 (E/(name+'.json')).write_text(json.dumps(row,indent=2)+'\n')
 if r.returncode:raise RuntimeError('CPU stage failed: '+str(log))
 print('PASS',name,round(row['seconds'],2),flush=True)
def py(name,*args):run(name,[sys.executable,'-B',*args])
def units(name,modules,source_names,**extra):
 admit(1_000_000);suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(m) for m in modules)
 with (E/(name+'.log')).open('w') as log:r=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
 row=dict(passed=r.wasSuccessful(),device_executed=False,checks=r.testsRun,errors=len(r.errors),failures=len(r.failures),modules=modules,source_sha256={n:digest(P/n) for n in source_names},**extra)
 (P/(name+'.json')).write_text(json.dumps(row,indent=2)+'\n');assert r.wasSuccessful(),name
 print('PASS',name,r.testsRun,flush=True)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('phase',choices=('builds','gates','models','final'));a=ap.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2';E.mkdir(exist_ok=True,parents=True)
 if a.phase=='builds':
  for mode in ('gnu-host','icpx-host','asan','device'):
   py('build-'+mode,'build.py',mode,'--jobs','2')
   py('cleanup-'+mode,'cleanup_objects.py')
   (E/('cleanup-'+mode+'-objects.json')).write_bytes((P/'object-cleanup-receipt.json').read_bytes())
 elif a.phase=='gates':
  for script in ('capacity_selection_gate.py','capacity_fixture_gate.py','asan_fixture_gate.py','p39_merged_fixture_gate.py','cpu_gates.py','wrapper_cpu_gate.py','test_memory_plan.py'):
   py(script[:-3],script)
  modules=['test_p45_kernels','test_k2_selection','test_p38_k2','test_k2_admission']
  old=json.loads((P/'p45-kernel-tests.json').read_text())
  units('p45-kernel-tests',modules,list(old['source_sha256']),schema='packet45.kernel-tests.v1')
  units('merged-campaign-completion-gates',['test_merged_gate_completion'],['cpu_merged_gate.py','test_merged_gate_completion.py'],tests=2,assertions=7,rank_processes_started=0)
  for suffix,tail in [('test','cpu'),('asan','asan'),('tsan-llvm22','tsan')]:
   binary=P/'build'/('native-controller-'+suffix);host(binary)
   py('native-controller-'+tail,'native_controller_gate.py','--binary',binary,'--output',P/('native-controller-'+tail+'.json'))
   binary=P/'build'/('native-mailbox-fault-'+suffix);host(binary)
   name='native-mailbox-faults'+('' if suffix=='test' else '-'+tail)
   run(name,[binary]);raw=(E/(name+'.log')).read_text();r=json.loads(raw);r.update(binary_sha256=digest(binary),device_executed=False,source_sha256={n:digest(P/n) for n in ('native_controller.hpp','native_controller_test.cpp','native_mailbox_fault_test.cpp')})
   (P/(name+'.json')).write_text(json.dumps(r,indent=2)+'\n')
 elif a.phase=='models':
  py('cpu-merged','cpu_merged_gate.py')
  py('cpu-real','cpu_real_gate.py')
  py('capacity-draft','capacity_draft_gate.py','--run')
 elif a.phase=='final':
  for script in ('test_real_cross_placement_gate.py','real_cross_placement_gate.py','test_seal45_bindings.py'):
   py(script[:-3],script)
  py('seal','build.py','seal')
  py('window-admission','test_window_seal_admission.py')
  py('detached-binding','-c','import seal45; print(seal45.verify_window_admission())')
  py('merge-inventory','merge_inventory.py')
if __name__=='__main__':main()
