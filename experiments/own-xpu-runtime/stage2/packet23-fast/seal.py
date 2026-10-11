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
 reuse();host=sha(B/'host/own-rt-iq3');math=check();queue=queue_check()
 mini={f'{t}-{m}':read(P/f'cpu-mini-{t}-{m}.json') for t in ('token','drain','launch') for m in ('core','parallel')}
 assert all(r['passed'] and r['binary_sha256']==host and len(r['tests'])==13 for r in mini.values())
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
 cpu=dict(passed=True,device_executed=False,binary_sha256=host,integration=mini,units=units,real_model=real,real_model_evidence='carried from packet21 under carryover-proof.json, original binary hashes retained',carryover_sha256=sha(P/'carryover-proof.json'),streaming_sha256=sha(P/'streaming-real.json'),sanitizer={n:sha(P/n) for n in san},fixtures_sha256=sha(P/'fixture-gates.json'),window_tests_sha256=sha(P/'window-tests.json'))
 save('cpu-tests.json',cpu)
 flags=['-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt']
 links={str(x.relative_to(B)):x.read_text() for x in (B/'device').rglob('link.txt')};assert len(links)==3
 assert all(all(f in shlex.split(v) for f in flags) for v in links.values())
 commands=read(B/'device/compile_commands.json');assert all(all(f in shlex.split(r['command']) for f in flags) for r in commands)
 for tag in ('host','icpx-host'):
  for name in ('own-rt-iq3','fused-fixtures','nongemv-fixtures'):
   path=B/tag/'CMakeFiles'/f'{name}.dir/link.txt'
   if path.exists():assert all(f in shlex.split(path.read_text()) for f in flags[:2])
 # Every compiled source has been rebuilt since its last edit.
 for tag in ('host','device'):
  binary=B/tag/'own-rt-iq3'
  assert all(binary.stat().st_mtime>=x.stat().st_mtime for x in closure())
 artifacts={str(x.relative_to(B)):sha(x) for x in [B/'host/own-rt-iq3',B/'device/own-rt-iq3',B/'sanitized/depcheck-runtime',*[B/tag/n for tag in ('host','icpx-host','device') for n in ('fused-fixtures','nongemv-fixtures')]]}
 paths=set(closure())|set(P.glob('*.py'))|{P/'CMakeLists.txt',P/'rope.bf16',P/'carryover-proof.json'}
 paths|=set((B/'input').glob('*'))|set((B/'fusion-fixtures').glob('*'))
 paths={x for x in paths if x.is_file()}
 census=read(S/'census.json');save('census.json',census)
 save('build-receipt.json',dict(schema='own-runtime.iq3.packet23.build.v1',passed=True,device_executed=False,device_qualified=False,arithmetic='iq3-p17-detmath-v2',max_compile_jobs=2,numeric_threads=2,artifacts_sha256=artifacts,sources={str(x.relative_to(ROOT)):sha(x) for x in sorted(paths)},cpu_tests_sha256=sha(P/'cpu-tests.json'),input_sha256=sha(B/'input/input.json'),census_sha256=sha(P/'census.json'),fused_fixture_host_sha256=fixture['outputs']['fused-fixtures'],nongemv_fixture_host_sha256=fixture['outputs']['nongemv-fixtures'],platform_math_gate=math,queue_isolation_gate=queue,precision_flags=flags,device_link_commands=links,carryover_proof_sha256=sha(P/'carryover-proof.json'),submission_benchmark_sha256=sha(P/'submission-benchmark.json')))
 print('SEALED',json.dumps(artifacts),flush=True)
if __name__=='__main__':main()
