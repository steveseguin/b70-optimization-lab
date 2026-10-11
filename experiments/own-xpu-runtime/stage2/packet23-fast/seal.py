#!/usr/bin/env python3
import json,hashlib,shlex,subprocess,os
from pathlib import Path
from math_gate import check,closure
from queue_gate import check as queue_check
from reuse import main as reuse
P=Path(__file__).resolve().parent;B=P/'build';ROOT=P.parents[3];S=P.with_name('packet21-fused')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def save(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 reuse();assert read(P/'kernel-sizes.json')['passed'];assert read(P/'failure-tests.json')['passed'] and read(P/'failure-tests.json').get('parameter_cache_event_order_controls')==1;host=sha(B/'host/own-rt-iq3');math=check();queue=queue_check()
 mini={f'{t}-{m}':read(P/f'cpu-mini-{t}-{m}.json') for t in ('token','drain','launch') for m in ('core','parallel')}
 assert all(r['passed'] and r['binary_sha256']==host and len(r['tests'])==13 for r in mini.values())
 eight=read(P/'real-eight.json');assert eight['passed'] and eight['layer_matches']==384 and len(eight['tokens'])==8
 assert read(P/'real-eight-reuse.json')['final_main_sha256']==sha(P/'main.cpp')
 stream=read(P/'streaming-real.json');assert stream['passed'] and stream['rows'][1]['binary_sha256']==host and stream['layer_matches']==144
 fixture=read(P/'fixture-gates.json');assert fixture['passed'] and len(fixture['rows'])==8
 for r in fixture['rows']:assert sha(B/r['compiler']/r['component'])==r['binary_sha256']
 san={n:read(P/n) for n in ('sanitizer-mini.json','sanitizer-integration.json','sanitizer-unit.json')}
 assert all(r['passed'] for r in san.values()) and san['sanitizer-mini.json']['runs']==16 and len(san['sanitizer-integration.json']['runs'])==8
 sb=read(B/'sanitized/build.json');assert sha(Path(sb['binary']))==sb['sha256']
 assert all(sha(Path(f))==h for f,h in sb['sources'].items())
 units={}
 for n in ('authority-tests','owner-retirement-tests','chain-tests','queue-tests','lifetime-tests'):
  units[n]=subprocess.check_output([str(B/'host'/n)],text=True)
 window=subprocess.run(['python','-B',str(P/'test_window.py')],capture_output=True,text=True,check=True)
 save('window-tests.json',dict(passed=True,device_executed=False,stdout=window.stdout,stderr=window.stderr))
 real={m:read(S/f'cpu-real-{m}.json') for m in ('frozen','r5')}
 cpu=dict(extra_eight_token_oracle_sha256=sha(P/'real-eight.json'),extra_eight_source_proof_sha256=sha(P/'real-eight-reuse.json'),kernel_capture_sizes_sha256=sha(P/'kernel-sizes.json'),failure_tests_sha256=sha(P/'failure-tests.json'),passed=True,device_executed=False,binary_sha256=host,integration=mini,units=units,real_model=real,real_model_evidence='carried from packet21 under carryover-proof.json, original binary hashes retained',carryover_sha256=sha(P/'carryover-proof.json'),streaming_sha256=sha(P/'streaming-real.json'),sanitizer={n:sha(P/n) for n in san},fixtures_sha256=sha(P/'fixture-gates.json'),window_tests_sha256=sha(P/'window-tests.json'))
 save('cpu-tests.json',cpu)
 flags=['-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt']
 links={str(x.relative_to(B)):x.read_text() for x in (B/'device').rglob('link.txt')};assert len(links)==4
 assert all(all(f in shlex.split(v) for f in flags) for v in links.values())
 object_sets=[{x for x in shlex.split(v) if 'packet23-programs.dir/' in x and x.endswith('.o')} for v in links.values()]
 assert object_sets[0] and all(x==object_sets[0] for x in object_sets)
 shared_kernel_objects={x:sha(B/'device'/x) for x in sorted(object_sets[0])}

 commands=read(B/'device/compile_commands.json');assert all(all(f in shlex.split(r['command']) for f in flags) for r in commands)
 for tag in ('host','icpx-host'):
  for name in ('own-rt-iq3','fused-fixtures','nongemv-fixtures'):
   path=B/tag/'CMakeFiles'/f'{name}.dir/link.txt'
   if path.exists():assert all(f in shlex.split(path.read_text()) for f in flags[:2])
 # Check actual compiler dependency files, separately for each target. A fixture
 # source is not a dependency of the CPU main executable.
 checked_objects=0
 for tag in ('host','icpx-host','device'):
  for entry in read(B/tag/'compile_commands.json'):
   words=shlex.split(entry['command']);obj=Path(entry['directory'])/words[words.index('-o')+1]
   if not obj.exists():
    assert tag=='icpx-host' and 'fixtures.dir' not in str(obj)
    continue
   assert obj.stat().st_mtime>=Path(entry['file']).stat().st_mtime,(obj,entry['file'])
   dep=obj.with_suffix(obj.suffix+'.d')
   if dep.exists():
    dependencies=shlex.split(dep.read_text().split(':',1)[1].replace('\\\n',' '))
    for name in dependencies:
     f=Path(name)
     if f.is_file() and f.is_relative_to(ROOT):assert obj.stat().st_mtime>=f.stat().st_mtime,(obj,f)
   checked_objects+=1
 artifacts={str(x.relative_to(B)):sha(x) for x in [B/'host/own-rt-iq3',B/'host/failure-tests',B/'device/own-rt-iq3',B/'device/jit-smoke',B/'sanitized/depcheck-runtime',*[B/tag/n for tag in ('host','icpx-host','device') for n in ('fused-fixtures','nongemv-fixtures')]]}
 paths=set(closure())|set(P.glob('*.py'))|{P/'CMakeLists.txt',P/'rope.bf16',P/'carryover-proof.json',P/'kernel_guard.hpp',P/'failure_test.cpp',P/'jit_smoke.cpp',P/'kernel-sizes.json',P/'failure-tests.json',P/'real-eight.json',P/'real-eight-reuse.json',P/'real-eight-final-plumbing.patch'}
 paths|=set((B/'input').glob('*'))|set((B/'fusion-fixtures').glob('*'))
 paths={x for x in paths if x.is_file()}
 census=read(S/'census.json');save('census.json',census)
 save('build-receipt.json',dict(schema='own-runtime.iq3.packet23.build.v1',passed=True,device_executed=False,device_qualified=False,arithmetic='iq3-p17-detmath-v2',kernel_capture_sizes=read(P/'kernel-sizes.json'),jit_smoke_same_objects=True,shared_kernel_objects_sha256=shared_kernel_objects,compiler_dependency_objects_checked=checked_objects,max_compile_jobs=2,numeric_threads=2,artifacts_sha256=artifacts,sources={str(x.relative_to(ROOT)):sha(x) for x in sorted(paths)},cpu_tests_sha256=sha(P/'cpu-tests.json'),input_sha256=sha(B/'input/input.json'),census_sha256=sha(P/'census.json'),fused_fixture_host_sha256=fixture['outputs']['fused-fixtures'],nongemv_fixture_host_sha256=fixture['outputs']['nongemv-fixtures'],platform_math_gate=math,queue_isolation_gate=queue,precision_flags=flags,device_link_commands=links,carryover_proof_sha256=sha(P/'carryover-proof.json'),submission_benchmark_sha256=sha(P/'submission-benchmark.json')))
 print('SEALED',json.dumps(artifacts),flush=True)
if __name__=='__main__':main()
