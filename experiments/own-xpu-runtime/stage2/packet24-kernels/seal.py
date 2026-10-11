#!/usr/bin/env python3
"""Bind final CPU receipts, precise compiled objects and untouched source closure."""
import hashlib,json,os,shlex,subprocess
from pathlib import Path
from math_gate import check,closure
from queue_gate import check as queue_check
from reuse import main as reuse
P=Path(__file__).resolve().parent;B=P/'build';ROOT=P.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def save(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 carry=reuse();host=sha(B/'host/own-rt-iq3');math=check();queue=queue_check()
 integration=read(P/'integration-gates.json');assert integration['passed'] and integration['cases']==312 and integration['binary_sha256']==host
 eight=read(P/'real-eight.json');assert eight['passed'] and eight['kernels']=='v2' and eight['binary_sha256']==host and eight['layer_matches']==384 and len(eight['tokens'])==8 and eight['maxrss_kib']<8*1024**2
 fixture=read(P/'fixture-gates.json');assert fixture['passed'] and len(fixture['rows'])==16
 for r in fixture['rows']:assert sha(B/r['compiler']/r['component'])==r['binary_sha256']
 san=read(P/'sanitizer-mini.json');assert san['passed'] and san['runs']==32 and sha(B/'asan/own-rt-iq3')==san['binary_sha256']
 guards=read(P/'sanitizer-unit.json');assert guards['passed']
 entry=read(P/'entry-smoke.json');assert entry['passed'] and all(x['returncode']==x['expected_returncode'] for x in entry['checks'])
 units=read(P/'unit-tests.json');assert units['passed']
 failures=read(P/'failure-tests.json');assert failures['passed'] and failures['parameter_cache_event_order_controls']==1
 sizes=read(P/'kernel-sizes.json');assert sizes['passed'] and sizes['max_after']<=1024 and sizes['negative_1025_rejected']
 for script,name in [('test_window.py','window-tests.json'),('k2_test.py','k2-summary-tests.json')]:
  r=subprocess.run(['python','-B',str(P/script)],capture_output=True,text=True);assert r.returncode==0,(script,r.stderr);save(name,dict(passed=True,device_executed=False,stdout=r.stdout,stderr=r.stderr))
 flags=['-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt']
 links={str(x.relative_to(B)):x.read_text() for x in (B/'device').rglob('link.txt')};assert len(links)==5
 assert all(all(f in shlex.split(v) for f in flags) for v in links.values())
 sets=[{x for x in shlex.split(v) if 'packet23-programs.dir/' in x and x.endswith('.o')} for v in links.values()]
 assert sets[0] and all(x==sets[0] for x in sets)
 objects={x:sha(B/'device'/x) for x in sorted(sets[0])}
 assert all(all(f in shlex.split(r['command']) for f in flags) for r in read(B/'device/compile_commands.json'))
 # CPU model and fixture compile/link precision flags, plus real entry shims.
 cpu_entry_symbols={}
 for tag in ['host','icpx-host']:
  commands=read(B/tag/'compile_commands.json')
  for name,entry_symbol in [('own-rt-iq3','packet23_model_entry'),('fused-fixtures','packet23_gemv_fixture_entry'),('nongemv-fixtures','packet23_nongemv_fixture_entry'),('k2-fixtures','packet24_k2_entry')]:
   binary=B/tag/name
   if not binary.exists():continue
   link=B/tag/'CMakeFiles'/(name+'.dir')/'link.txt';assert all(f in shlex.split(link.read_text()) for f in flags[:2])
   relevant=[r for r in commands if '/'+name+'.dir/' in r['command']]
   assert relevant and all(all(f in shlex.split(r['command']) for f in flags[:2]) for r in relevant)
   sym=subprocess.check_output(['nm','-C',str(binary)],text=True);assert entry_symbol+'(' in sym
   cpu_entry_symbols[tag+'/'+name]=dict(entry=entry_symbol,success_exit_checked=True)
 ng=next(r for r in fixture['rows'] if r['component']=='nongemv-fixtures')
 root=B # find exact sealed extra outputs retained from fixture process receipts
 extra_dir=next(d for d in B.glob('fixture-runs-*') if (d/'host-nongemv-fixtures-v1-0/kernel-fixture.json').exists())/'host-nongemv-fixtures-v1-0'
 # Choose a run matching the final combined output, not an older fixture edition.
 matches=[d/'host-nongemv-fixtures-v1-0' for d in B.glob('fixture-runs-*') if (d/'host-nongemv-fixtures-v1-0/output.bin').exists() and sha(d/'host-nongemv-fixtures-v1-0/output.bin')==fixture['outputs']['nongemv-fixtures']]
 assert matches;extra_dir=matches[-1]
 counts={}
 for prefix in ['kernel','route']:
  r=read(extra_dir/(prefix+'-fixture.json'));assert r['passed'];counts[prefix]=r
 assert counts['kernel']['fixtures']==92 and counts['kernel']['pairwise_checks']==276 and counts['route']['version_checks']==30
 cpu=dict(passed=True,device_executed=False,binary_sha256=host,integration_cases=312,units=units,entry_tests=entry,sanitizer_runs=32,fixture_processes=16,
          fixture_gates_sha256=sha(P/'fixture-gates.json'),sanitizer_mini_sha256=sha(P/'sanitizer-mini.json'),sanitizer_unit_sha256=sha(P/'sanitizer-unit.json'),window_tests_sha256=sha(P/'window-tests.json'),
          real_model=dict(v2=dict(passed=True,kernels='v2',token_matches=8,tokens=eight['tokens'],layer_matches=384,layer_total=384),v1_carryover=carry['original_real_model_receipts']),
          extra_eight_token_oracle_sha256=sha(P/'real-eight.json'),carryover_sha256=sha(P/'carryover-proof.json'))
 save('cpu-tests.json',cpu)
 binaries=[B/'host/own-rt-iq3',B/'asan/own-rt-iq3',B/'host/k2-fixtures',*[B/'device'/n for n in ['own-rt-iq3','jit-smoke','k2-fixtures']],*[B/t/n for t in ['host','icpx-host','device'] for n in ['fused-fixtures','nongemv-fixtures']]]
 artifacts={str(x.relative_to(B)):sha(x) for x in binaries}
 paths=set(closure())|set(P.glob('*.py'))|{P/'CMakeLists.txt',P/'rope.bf16',P/'kernel_guard.hpp',P/'source-proof.json',P/'carryover-proof.json',P/'tree-review.json',P/'race-review.json',P/'k2-review.json'}
 paths|=set((B/'input').glob('*'))|set((B/'fusion-fixtures').glob('*'))|set((B/'k2-input').glob('*'))
 build=dict(schema='own-runtime.iq3.packet24.build.v1',passed=True,device_executed=False,device_qualified=False,arithmetic='iq3-p17-detmath-v2',max_compile_jobs=2,numeric_threads=2,artifacts_sha256=artifacts,sources={str(x.relative_to(ROOT)):sha(x) for x in sorted(paths) if x.is_file()},cpu_tests_sha256=sha(P/'cpu-tests.json'),input_sha256=sha(B/'input/input.json'),k2_input_sha256=sha(B/'k2-input/input-receipt.json'),fused_fixture_host_sha256=fixture['outputs']['fused-fixtures'],nongemv_fixture_host_sha256=fixture['outputs']['nongemv-fixtures'],precision_flags=flags,device_link_commands=links,shared_kernel_objects_sha256=objects,jit_smoke_same_objects=True,kernel_capture_sizes=sizes,platform_math_gate=math,queue_isolation_gate=queue,cpu_entry_symbols=cpu_entry_symbols,
            gate_counts=dict(integration=312,fixture_processes=16,direct_kernel_fixtures=92,direct_kernel_pairwise_checks=276,route_edge_fixtures=15,route_version_checks=30,randomized_asan_mini=32,window_protocol=66,math_tree_symbolic=26,k0_mock_exits=3))
 for prefix in ['kernel','route']:
  build[prefix+'_fixture_host_sha256']=sha(extra_dir/(prefix+'-output.bin'))
  keys=['fixtures','inherited','odd_width_cases','pairwise_checks'] if prefix=='kernel' else ['fixtures','version_checks','raw_v1_v2_checks']
  build[prefix+'_fixture_counts']={k:counts[prefix][k] for k in keys}
 save('build-receipt.json',build);print(json.dumps(dict(artifacts=artifacts,gates=build['gate_counts']),indent=2))
if __name__=='__main__':main()
