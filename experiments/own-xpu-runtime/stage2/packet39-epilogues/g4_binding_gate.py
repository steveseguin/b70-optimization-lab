"""Build/run only CPU executables; validate the shared full-size G4 bindings."""
import hashlib,json,os,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
SOURCES=['g4_binding_gate.cpp','g4_fixture.hpp','case_runner.hpp','fused.hpp','timing.cpp']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 results=[]
 for label,cc in [('gcc','/usr/bin/g++'),('icpx','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=P/'build'/('g4-binding-'+label)
  command=['nice','-n','19','ionice','-c','3',cc,'-std=c++20','-O2','-ffp-contract=off','-fno-fast-math',str(P/'g4_binding_gate.cpp'),'-o',str(binary)]
  subprocess.run(command,check=True)
  # A host ELF may not load an accelerator runtime, even if no kernel is called.
  dynamic=subprocess.check_output(['nice','-n','19','ionice','-c','3','readelf','-d',str(binary)],text=True)
  assert not any(name in dynamic.lower() for name in ['libsycl','libze_loader','libur_loader','libopencl'])
  r=subprocess.run(['nice','-n','19','ionice','-c','3',str(binary)],check=True,capture_output=True,text=True)
  data=json.loads(r.stdout);assert data['passed'] and data['case_count']==12
  data.update(compiler=label,binary_sha256=sha(binary),compile_command=command)
  results.append(data)
 record=dict(passed=True,device_executed=False,device_discovery=False,affinity=sorted(os.sched_getaffinity(0)),sources={n:sha(P/n) for n in SOURCES},runs=results,scope='Exact shared G4 allocations/bindings and real fused.hpp validation on CPU. Full weight extents reserved; weight payload not populated or computed. Includes continuation and infrastructure failure injection.')
 (P/'g4-binding-gate.json').write_text(json.dumps(record,indent=2)+'\n')
 print('G4 host bindings PASS: 12/12 cases with both compilers; continuation and infrastructure gates passed')
if __name__=='__main__':main()
