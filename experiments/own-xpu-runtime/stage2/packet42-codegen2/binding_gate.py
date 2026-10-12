"""Host-only builds of the real native entries/validators and real chained owner.
No accelerator binary is executed. No SYCL discovery, queue or bundle is called.
The existing packet29 Cpu backend is extracted in validation-only mode; only
kernel execution is disabled. Native argument construction is not reimplemented.
"""
import hashlib,json,os,resource,shutil,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent
R=P.parent/'packet29-merged'
B=P/'build/binding-gate'
IC='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
PREFIX=['nice','-n','19','ionice','-c','3']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(cmd,log,env=None):
 with Path(log).open('w') as f:
  r=subprocess.run(PREFIX+list(map(str,cmd)),stdout=f,stderr=subprocess.STDOUT,env=env)
 if r.returncode:raise RuntimeError(str(log)+': '+Path(log).read_text()[-5000:])
def coverage_check(name,window,out,receipt):
 if window=='K0':return dict(bundle_boundary=True,compute_submissions=0,device_bundle_build=False)
 if name=='floor':
  rows=[json.loads(f.read_text()) for f in out.glob('g*-sg*.json')]
  assert len(rows)==1180 and all(r['passed'] and len(r['gpu_us'])==200 for r in rows)
  assert sum(r['burst']==1000 for r in rows)==4
  return dict(matrix_rows=1176,burst_rows=4,repetitions=200)
 if name=='gemv':
  rows=[json.loads(x) for x in (out/'events.jsonl').read_text().splitlines()]
  groups={}
  for r in rows:groups.setdefault((r['candidate'],r['timing_mode'],r['variant']),[]).append(r)
  assert {k[0] for k in groups}=={'p42.gate.packed','p42.down.select_vector','p42.down.bank_scalar','p42.dense.fourparts'}
  for key,rr in groups.items():
   assert {r['repetition'] for r in rr}==set(range(200))
   if key[1]=='rotated':assert {r['buffer_copy'] for r in rr}==set(range(8))
  return dict(event_rows=len(rows),candidate_mode_arms=len(groups),warmups=8,measurements=200,postflights=8,all_eight_rotation_banks=True)
 if name in ('parallel','route'):
  expected=800 if name=='parallel' else 400
  assert receipt['cases' if name=='parallel' else 'checks']==expected
  return dict(case_arm_repetitions=expected,repetitions=200)
 rows=json.loads((out/'summary.json').read_text())['rows']
 assert len(rows)==(129 if name=='tiny' else 70) and all(r['passed'] for r in rows)
 timed=[r for r in rows if r['timing_eligible']]
 assert len(timed)==(26 if name=='tiny' else 23) and all(len(r['candidate_gpu_us'])==len(r['control_gpu_us'])==200 for r in timed)
 return dict(rows=len(rows),timed_rows=len(timed),repetitions=200,scenarios=sum(len(r.get('byte_scenarios',[])) for r in rows))
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 if shutil.disk_usage('/').free<8_000_000_000:raise RuntimeError('root below 8GB')
 B.mkdir(parents=True,exist_ok=True);(B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 # Same host Backend used by packet29 validation gates. Preserve its source
 # verbatim except for suppressing the already-disabled HostOperation cast,
 # and adding a trace hook (no admission/extent/alias check is replaced).
 src=(R/'gemv_timing.cpp').read_text();start=src.index('struct Cpu:Backend {');end=src.index('\n};',start)+3
 cpu=src[start:end]
 cpu=cpu.replace('if(!fixture_validation::only)dynamic_cast<const HostOperation&>(op).run(p);','p42_binding_record(op,p);')
 backend='#include "owner.hpp"\n#include <cstring>\n#include <fstream>\n#include <cstdlib>\n#include <typeinfo>\nnamespace ownrt {\nnamespace fixture_validation { inline constexpr bool only=true; }\nstatic std::map<std::string,std::pair<size_t,size_t>> trace;\nstatic void p42_binding_record(const Operation& op,std::span<void*const> p) {\n auto& row=trace[typeid(op).name()];++row.first;row.second=p.size();\n}\n'+cpu+'\nstd::unique_ptr<Backend> make_sycl_device(size_t,bool) { return std::make_unique<Cpu>(); }\nstruct TraceWriter { ~TraceWriter() {\n const char* path=std::getenv("P42_BINDING_TRACE");if(!path)return;\n std::ofstream f(path);f<<"{\\"device_executed\\":false,\\"operations\\":{";\n bool comma=false;for(auto& [name,row]:trace){f<<(comma?",":"")<<quote(name)<<":["<<row.first<<","<<row.second<<"]";comma=true;}f<<"}}\\n";\n if(!f)std::abort();\n}} trace_writer;\n}\n'
 (B/'backend.cpp').write_text(backend)
 # All gate objects are compiled from source, never linked to device objects.
 # Plain C++ (-fno-sycl) retains native validators and SyclOperation types but
 # emits no device images. make_sycl_device resolves to the real Cpu above.
 flags=['-std=c++20','-O1','-fno-fast-math','-ffp-contract=off','-fno-sycl','-DP42_BINDING_GATE','-ffunction-sections','-fdata-sections']
 inc=['-I/opt/intel/oneapi/compiler/2026.0/include', '-I'+str(P)] + ['-I'+str(x) for x in [P,R,R/'../../stage1/packet3-prep/src',R/'../packet2/kernels',R/'../packet2/loader']]
 common=[R/x for x in ['owner.cpp','owner_retire.cpp','native.cpp','runtime_kernels.cpp','adapter.cpp','performance.cpp','p28/submit.cpp','expert_down.cpp','round2_submit.cpp','specialised_submit.cpp','p25_bridge.cpp','small_gemv.cpp']]
 common += [P.parent/x for x in ['packet2/kernels/device.cpp','packet6-kopt/kernels.cpp','packet7-kopt2/kernels.cpp','packet8-kopt3/kernels.cpp','packet9-kopt4/kernels.cpp','packet10-kopt5/kernels.cpp','packet33-codegen/p33_submit.cpp']]
 common += [P/x for x in ['expert_submit.cpp','parallel_submit.cpp','route42_submit.cpp']]+[B/'backend.cpp']
 entries={'floor':[P/'launch_floor.cpp'],'gemv':[P/'gemv_main.cpp',P/'build/gemv/gemv_generated.cpp'],'parallel':[P/'parallel_native.cpp'],'route':[P/'route42_native.cpp',P/'route42_timing.cpp'],'tiny':[P/'tiny_timing.cpp'],'extras':[P/'extras_timing.cpp']}
 commands=[];objects={}
 for source in dict.fromkeys(common+[s for ss in entries.values() for s in ss]+[P/'binding_negative.cpp']):
  obj=B/(str(len(objects))+'.o');cmd=[IC,*flags,*inc,'-MMD','-MF',obj.with_suffix('.d'),'-c',source,'-o',obj]
  deps=[source]
  if obj.with_suffix('.d').exists():
   deps += [Path(x) for x in obj.with_suffix('.d').read_text().replace('\\\n',' ').split()[1:] if Path(x).is_file()]
  identity=hashlib.sha256((' '.join(map(str,cmd))+''.join(sha(x) for x in deps)).encode()).hexdigest()
  stamp=obj.with_suffix('.key')
  # Explicit --reuse is only for local debugging; normal gate rebuilds all.
  if '--reuse' not in sys.argv or not obj.exists() or not stamp.exists() or stamp.read_text()!=identity:
   run(cmd,obj.with_suffix('.log'));stamp.write_text(identity)
  objects[source]=obj;commands.append(list(map(str,cmd)));print('host compiled',source.name,flush=True)
 binaries={}
 for name,sources in entries.items():
  binary=B/('host-'+name);cmd=[IC,*flags,*map(str,[objects[s] for s in common+sources]),'-Wl,--gc-sections','-Wl,-rpath,/opt/intel/oneapi/compiler/2026.0/lib','-L/opt/intel/oneapi/compiler/2026.0/lib','-lsycl','-lcrypto','-o',binary]
  run(cmd,B/(name+'-link.log'));commands.append(list(map(str,cmd)))
  symbols=subprocess.check_output(PREFIX+['nm',str(binary)],text=True)
  assert '__sycl_register_lib' not in symbols and '__sycl_offload' not in symbols
  assert 'zeInit' not in symbols and 'get_platforms' not in symbols
  sections=subprocess.check_output(PREFIX+['readelf','-SW',str(binary)],text=True)
  assert 'OFFLOAD' not in sections
  binaries[name]=binary
 negative=B/'host-negative'
 cmd=[IC,*flags,*map(str,[objects[s] for s in common]+[objects[P/'binding_negative.cpp']]),'-Wl,--gc-sections','-Wl,-rpath,/opt/intel/oneapi/compiler/2026.0/lib','-L/opt/intel/oneapi/compiler/2026.0/lib','-lsycl','-lcrypto','-o',negative]
 run(cmd,B/'negative-link.log');commands.append(list(map(str,cmd)))
 run([negative],B/'negative.json')
 negative_receipt=json.loads((B/'negative.json').read_text());assert negative_receipt['passed'] and negative_receipt['rejection_checks']==9
 results=[]
 for name,binary in binaries.items():
  for window in ['K0','T1' if name=='floor' else 'K2']:
   out=B/(window+'-'+name)
   if out.exists():shutil.rmtree(out) # regenerable CPU traversal output only
   out.mkdir();trace=out/'binding-trace.json'
   env=dict(os.environ,P42_BINDING_TRACE=str(trace))
   args=['--authorized-device-window','--card','2','--repetitions','200','--output',out]
   if window=='K0':args+=['--compile-smoke']
   run([binary,*args],out/'stdout.txt',env)
   receipt=json.loads((out/'receipt.json').read_text());assert receipt.get('infrastructure_passed') is True
   assert not receipt.get('failed_cases',0),receipt
   if 'reference_exact' in receipt:receipt['reference_exact']=False # no kernel arithmetic in this gate
   for f in out.glob('*fail*.json*'):assert not f.read_text().strip(),(f,f.read_text())
   operations=json.loads(trace.read_text())['operations'];assert all(n>0 for count,n in operations.values())
   if window=='K0':assert not operations
   else:assert operations
   coverage=coverage_check(name,window,out,receipt)
   results.append(dict(program=name,window=window,coverage=coverage,argv=list(map(str,[binary,*args])),receipt=receipt,operations=operations,submissions=sum(v[0] for v in operations.values()),binary_sha256=sha(binary)))
   print('host path PASS',name,window,results[-1]['submissions'],flush=True)
 inputs=set(objects)|{P/'binding_gate.py'}
 for dep in B.glob('*.d'):
  inputs.update(Path(x).resolve() for x in dep.read_text().replace('\\\n',' ').split()[1:] if x.startswith(str(P.parents[3])))
 report=dict(schema='packet42.real-owner-binding-gate.v1',passed=True,device_executed=False,device_discovery=False,kernel_arithmetic_executed=False,scope='six actual native main functions; K0 bundle call boundary; complete T1/K2 cases, warmups, repetitions, rotations and binding validators; real owner.cpp/owner_retire.cpp and packet29 Cpu validation backend',device_only_checks_mirrored=[],negative_controls=negative_receipt,commands=commands,source_sha256={str(s):sha(s) for s in inputs if s.is_file()},results=results)
 (P/'binding-gates.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
