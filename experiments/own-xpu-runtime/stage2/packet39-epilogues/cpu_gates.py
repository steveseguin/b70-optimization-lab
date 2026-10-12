#!/usr/bin/env python3
"""CPU-only, one process at a time, source-bound fresh-process identity gates."""
import hashlib,json,os,pathlib,subprocess
P=pathlib.Path(__file__).resolve().parent
B=P/'build';E=P/'cpu-evidence';B.mkdir(exist_ok=True);E.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
record={'schema':'packet39.cpu-identity.v1','device_ran':False,'sources':{},'compilers':{},'runs':[]}
for name in ['cpu_gate.cpp','fused.hpp'] :record['sources'][name]=sha(P/name)
for label,cc in [('gcc','/usr/bin/g++'),('icpx','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
 flags=['-std=c++20','-O2','-ffp-contract=off','-fno-fast-math','-fno-associative-math']
 if label=='icpx':flags+=['-fp-model=precise']
 obj=B/f'cpu-{label}.o';exe=B/f'cpu-{label}'
 commands=[[cc,*flags,'-c',str(P/'cpu_gate.cpp'),'-o',str(obj)],[cc,*flags,str(obj),'-o',str(exe)]]
 for index,cmd in enumerate(commands):
  result=subprocess.run(['nice','-n','19','ionice','-c','3',*cmd],capture_output=True,text=True,env=dict(os.environ,OMP_NUM_THREADS='2'))
  (E/f'{label}-{"compile" if index==0 else "link"}.log').write_text(result.stdout+result.stderr)
  if result.returncode:raise RuntimeError(f'{label} compile/link failed')
 record['compilers'][label]={'compiler':cc,'compiler_sha256':sha(pathlib.Path(cc)),'commands':commands,'binary_sha256':sha(exe)}
 for repeat in range(2):
  result=subprocess.run(['nice','-n','19','ionice','-c','3',str(exe)],capture_output=True,text=True,env=dict(os.environ,OMP_NUM_THREADS='2'))
  (E/f'{label}-{repeat}.stdout.json').write_text(result.stdout)
  (E/f'{label}-{repeat}.stderr.log').write_text(result.stderr)
  if result.returncode:raise RuntimeError(f'{label} CPU gate failed')
  data=json.loads(result.stdout);data.update(compiler=label,repeat=repeat);record['runs'].append(data)
record['finite_and_control_passed']=all(r['finite_and_control_passed'] for r in record['runs'])
record['passed']=all(r['passed'] for r in record['runs'])
record['finite_and_control_observable_comparisons']=sum(r['observable_comparisons'] for r in record['runs'])
record['finite_fresh_process_and_compiler_determinism']=len({r['finite_output_fnv64'] for r in record['runs']})==1
record['finite_and_control_passed']=record['finite_and_control_passed'] and record['finite_fresh_process_and_compiler_determinism']
record['total_fixtures']=sum(r['fixtures'] for r in record['runs'])
record['total_guard_rejections']=sum(r['guard_rejections'] for r in record['runs'])
record['total_nonfinite_comparisons']=sum(r['nonfinite_diagnostic_comparisons'] for r in record['runs'])
record['aggregate_per_class']={}
for run in record['runs']:
 for name,counts in run['classes'].items():
  row=record['aggregate_per_class'].setdefault(name,dict(finite_checks=0,nonfinite_checks=0,nonfinite_mismatches=0))
  for key,value in counts.items():row[key]+=value
record['nonfinite_qualified']=False
record['nonfinite_policy']='Exact bytes compared without NaN tolerance; valid-route poisoned arithmetic remains unqualified diagnostic as packet29. Invalid routes and sticky controls are required gates.'
record['math_grep']={'source_forbidden_intrinsics':[]}
for name in ['fused.hpp','fused_sycl.hpp']:
 text=(P/name).read_text()
 for bad in ['native::','fast::','sycl::exp','std::exp','fma(']:
  if bad in text:record['math_grep']['source_forbidden_intrinsics'].append([name,bad])
record['passed']=record['passed'] and not record['math_grep']['source_forbidden_intrinsics']
(P/'cpu-gates.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'passed':record['passed'],'comparisons':record['finite_and_control_observable_comparisons'],'runs':len(record['runs'])}))
