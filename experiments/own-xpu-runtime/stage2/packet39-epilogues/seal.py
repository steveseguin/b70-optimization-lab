"""Bind preparation evidence and native binaries. Never execute a device binary."""
import hashlib,json,os,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(name):return json.loads((P/name).read_text())
def command(args):return ['nice','-n','19','ionice','-c','3','env','OMP_NUM_THREADS=2',*args]
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 native={n:sha(P/'build'/n) for n in ('p39-k0','p39-timing')}
 assert len(set(native.values()))==1
 for n,h in native.items():
  build=read(n+'-build.json');assert build['binary_sha256']==h and build['returncode']==0 and build['device_executed'] is False
 binding=read('g4-binding-gate.json');assert binding['passed'] and not binding['device_executed']
 for n,h in binding['sources'].items():assert sha(P/n)==h
 assert len(binding['runs'])==2 and all(r['case_count']==12 and r['continuation_attempted']==12 and r['continuation_failures']==2 and r['infrastructure_stopped_at']==3 for r in binding['runs'])
 timing=read('p39-timing-build.json');assert timing['source_sha256']==sha(P/'timing.cpp')
 expected=['-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt','-fsycl']
 assert all(x in timing['argv'] and x in timing['compile_and_link_precision'] for x in expected)
 cpu=read('cpu-gates.json');assert cpu['finite_and_control_passed'] and cpu['finite_fresh_process_and_compiler_determinism']
 for n,h in cpu['sources'].items():assert sha(P/n)==h
 binaries={n:sha(P/'build'/('cpu-'+n)) for n in cpu['compilers']}
 assert all(binaries[n]==v['binary_sha256'] for n,v in cpu['compilers'].items())
 host=read('real-eight.json');assert host['passed'] and host['layer_matches']==384 and len(host['tokens'])==8 and not host['device_executed']
 assert sha(P/'build/host-gate/own-rt-iq3-host')==host['binary_sha256']
 math=read('math-gate.json');assert math['passed']
 source={str(Path(os.path.relpath(ROOT/n,P))):h for n,h in math['sources'].items()}
 for n,h in source.items():assert sha(P/n)==h
 modules=read('candidate-modules.json');native_blob=(P/'build/p39-timing').read_bytes()
 for r in modules:
  spv=(P/r['module']).read_bytes();assert sha(P/r['module'])==r['sha256'];assert native_blob[r['binary_offset']:r['binary_offset']+len(spv)]==spv
 assert read('protocol-tests.json')['passed']
 assembly=read('assembly-review.json');assert assembly['codegen_sha256']==sha(P/'codegen.json')
 independent=read('review-assembly-details.json');assert independent['source_codegen_sha256']==sha(P/'codegen.json')
 for pair in independent['independent_loop_opcode_review']:
  for arm in ('baseline','fused'):assert sha(P/pair[arm+'_asm'])==pair[arm+'_asm_sha256']
 retain=read('offline-retention.json');assert retain['all_member_bytes_verified'] and sha(P/retain['archive'])==retain['archive_sha256']
 identity=read('identity-review.json');harness=read('harness-review.json')
 assert not identity['device_executed'] and not harness['device_executed']
 for r in identity['sources']:assert sha(P/r['path'])==r['sha256']
 assert harness['native_sha256']==native and harness['eligible_launches_removed_per_token']==assembly['eligible_launches_removed_per_token']
 assert len(harness['cases'])==12 and harness['prospective_byte_checks']==84
 for n,h in harness['reviewed_source_sha256'].items():assert sha(P/n)==h
 # Sealing source and evidence also prevents edits to the dispatch acceptance map
 # or wrapper between preparation and the coordinator window. Exclude this seal
 # and the generated hash listing to avoid self-reference.
 for f in sorted(P.rglob('*')):
  if f.is_file() and not set(f.relative_to(P).parts)&{'build','__pycache__'} and f.name not in ('build-receipt.json','BINARY-HASHES.md'):
   source[str(f.relative_to(P))]=sha(f)
 versions={}
 for name,cmd in [('g++',['g++','--version']),('icpx',['/opt/intel/oneapi/compiler/2026.0/bin/icpx','--version']),('ocloc',['ocloc','--version'])]:
  r=subprocess.run(command(cmd),capture_output=True,text=True);versions[name]={'returncode':r.returncode,'text':r.stdout+r.stderr}
 receipt=dict(schema='packet39.build.v1',device_executed=False,device_discovery=False,preparation_complete=True,device_qualified=False,performance_claim=False,arithmetic_identity='v2; finite qualified CPU scope; nonfinite diagnostics unqualified',native_binary_sha256=native,cpu_binary_sha256=binaries,host_binary_sha256=host['binary_sha256'],source_sha256=source,compiler_versions=versions,precision_compile_and_link=read('p39-timing-build.json')['compile_and_link_precision'],cpu_gate_counts={k:cpu[k] for k in ('total_fixtures','finite_and_control_observable_comparisons','total_guard_rejections','total_nonfinite_comparisons','nonfinite_qualified','passed')},real_model={'tokens':8,'layers':host['layer_matches'],'passed':host['passed']},offline={'kernels':len(read('codegen.json')['kernels']),'admitted_cases':sum(r['accepted'] for r in assembly['classes'].values()),'candidate_launches_removed_per_token':assembly['eligible_launches_removed_per_token']},g4_binding_gate_sha256=sha(P/'g4-binding-gate.json'),g4_binding_cases=12,wrapper_mock_groups=read('protocol-tests.json'),coordinator_gates_pending=['K0','G4 84 byte gates and 200 timings/arm/class','full-model native oracle and fresh-window repeats'],affinity=sorted(os.sched_getaffinity(0)),git_base=subprocess.check_output(command(['git','rev-parse','HEAD']),text=True).strip())
 (P/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 rows=[*[(n,h) for n,h in native.items()],*[(f'cpu-{n}',h) for n,h in binaries.items()],('host-gate/own-rt-iq3-host',host['binary_sha256'])]
 (P/'BINARY-HASHES.md').write_text('# Prepared binary SHA-256\n\nAll executables are under ignored `build/`. Native K0/G4 were compiled only, never run. Host fixture/model binaries ran CPU-only.\n\n| Binary | SHA-256 |\n| --- | --- |\n'+''.join(f'| `{n}` | `{h}` |\n' for n,h in rows)+'\nRebuild procedures and source pins are in [INTEGRATE.md](INTEGRATE.md) and [build-receipt.json](build-receipt.json).\n')
 print('sealed',len(source),'sources/evidence; native',native['p39-timing'])
if __name__=='__main__':main()
