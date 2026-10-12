#!/usr/bin/env python3
"""CPU gates and native compilation only. No device entry is ever executed."""
import argparse,hashlib,json,os,resource,struct,subprocess,time,gzip
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build';ROOT=P.parents[3]
PY='/home/steve/.venvs/vllm-xpu/bin/python';IC='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args,log,bounded=True):
 with (B/log).open('w') as out:
  def limit():
   old=resource.getrlimit(resource.RLIMIT_AS)[1];cap=min(8*1024**3,old) if old!=resource.RLIM_INFINITY else 8*1024**3
   resource.setrlimit(resource.RLIMIT_AS,(cap,cap))
  r=subprocess.run(list(map(str,args)),stdout=out,stderr=subprocess.STDOUT,preexec_fn=limit if bounded else None)
 if r.returncode:raise RuntimeError(str(B/log))
 print(log,'PASS',flush=True)
def configure(mode):
 host=mode!='device';compiler=IC if mode in ('device','icpx-host') else '/usr/bin/g++'
 cmd=['cmake','-S',P,'-B',B/mode,'-DCMAKE_CXX_COMPILER='+compiler,'-DOWN_RT_HOST_ONLY='+('ON' if host else 'OFF'),'-DOWN_RT_SANITIZE='+('ON' if mode=='asan' else 'OFF')]
 run(cmd,'configure-'+mode+'.log');run(['cmake','--build',B/mode,'-j1'],'build-'+mode+'.log')
def sources():
 from math_gate import closure
 paths=set(closure())|set((P/'prototype').rglob('*.py'))|{x for x in P.iterdir() if x.suffix in ('.cpp','.hpp','.py') or x.name in ('CMakeLists.txt','rope.bf16','dispatch-default.json','dispatch-all-new.json','k2-class-registry.json','kernel-registry.json','dispatch-merged-example.json')}
 return {str(x.relative_to(ROOT)):sha(x) for x in sorted(paths)}
def prepare():
 if not (B/'input').exists():run([PY,'-B',P/'prepare.py','--output',B/'input'],'prepare.log')
 if not (B/'fusion-fixtures').exists():run([PY,'-B',P/'prototype/fixtures.py','--output',B/'fusion-fixtures'],'prepare-fixtures.log')
 values=struct.unpack('<262144H',(P/'rope.bf16').read_bytes())
 (B/'fusion-rope.hpp').write_text('#pragma once\nnamespace rope_constants { inline constexpr int positions=4096; inline constexpr uint16_t table[]={'+','.join(map(str,values))+'};}\n')
def seal():
 gates={name:json.loads((P/name).read_text()) for name in ('integration-gates.json','fixture-gates.json','sanitizer-mini.json','real-eight.json','host-issue-benchmark.json','entry-smoke.json','kernel-sizes.json','carryover-proof.json','copy-budget.json','window-tests.json','identity-tree-tests.json','entry-codes.json','validation-gates.json','priority-gates.json','expert-down-review-gates.json')}
 assert all(v.get('passed') for v in gates.values())
 archived=gates['fixture-gates.json']['full_receipts'];blob=P/archived['path']
 assert sha(blob)==archived['compressed_sha256']
 original=gzip.decompress(blob.read_bytes());assert hashlib.sha256(original).hexdigest()==archived['uncompressed_sha256']
 assert json.loads(original)['output_sha256']==gates['fixture-gates.json']['output_sha256']
 real=gates['real-eight.json'];assert real['layer_matches']==384 and len(real['tokens'])==8
 binaries={str(x.relative_to(B)):sha(x) for mode in ('host','icpx-host','asan','device') for x in (B/mode).iterdir() if x.name in ('own-rt-iq3','nongemv-fixtures','k2-fixtures','jit-smoke')}
 assert real['binary_sha256']==binaries['host/own-rt-iq3']
 assert gates['integration-gates.json']['binary_sha256']==binaries['host/own-rt-iq3']
 assert gates['copy-budget.json']['binary_sha256']==binaries['host/own-rt-iq3']
 assert gates['sanitizer-mini.json']['binary_sha256']==binaries['asan/own-rt-iq3']
 for row in gates['validation-gates.json']['checks']:
  if 'entry' in row:assert row['binary_sha256']==binaries[row['compiler']+'/'+row['entry']]
 for row in gates['fixture-gates.json']['rows']:assert row['binary_sha256']==binaries[row['compiler']+'/nongemv-fixtures']
 host_flags=['-fno-fast-math','-ffp-contract=off']
 host_precision={}
 for mode in ('host','icpx-host','asan'):
  cc=json.loads((B/mode/'compile_commands.json').read_text());ll={str(x.relative_to(B)):x.read_text() for x in (B/mode).rglob('link.txt')}
  assert cc and all(all(f in x['command'].split() for f in host_flags) for x in cc)
  assert ll and all(all(f in v.split() for f in host_flags) for v in ll.values())
  host_precision[mode]=dict(compile_count=len(cc),link_count=len(ll),flags=host_flags,compile_commands_sha256=sha(B/mode/'compile_commands.json'))
 flags=['-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt']
 commands=json.loads((B/'device/compile_commands.json').read_text())
 assert all(all(f in x['command'].split() for f in flags) for x in commands)
 links={str(x.relative_to(B)):x.read_text() for x in (B/'device').rglob('link.txt') if '.dir' in str(x)}
 assert links and all(all(f in v.split() for f in flags) for v in links.values())
 from math_gate import check
 from queue_gate import check as queue_check
 math=check();queue=queue_check()
 cpu=dict(passed=True,device_executed=False,binary_sha256=binaries['host/own-rt-iq3'],unit_suites=len(gates['integration-gates.json']['units']),integration_cases=gates['integration-gates.json']['cases'],fixture_coverage={k:gates['fixture-gates.json']['rows'][0]['receipt'][k] for k in ('fixtures','source_fixtures','gemv_checks','small_gemv_checks','adapter_only_checks')},window_tests=gates['window-tests.json']['tests'],symbolic_tree_checks=gates['identity-tree-tests.json']['checks'],copy_budget_rows=len(gates['copy-budget.json']['rows']),literal_all_copy_budget_passed=False,kernel_capture_count=gates['kernel-sizes.json']['kernel_classes'],maximum_capture_bytes=gates['kernel-sizes.json']['max_after'],entry_negative_checks=len(gates['entry-codes.json']['checks']),entry_mock_checks=len(gates['entry-smoke.json']['checks']),expert_down_finite_checks_per_process=gates['expert-down-review-gates.json']['checks_per_process'],expert_down_finite_processes=gates['expert-down-review-gates.json']['processes'],nonfinite_gemv_qualified=False,expert_down_full_nonfinite_diagnostic_passed=gates['expert-down-review-gates.json']['diagnostic_passed'],fixture_processes=len(gates['fixture-gates.json']['rows']),sanitizer_runs=len(gates['sanitizer-mini.json']['runs']),real_model={'all_new':dict(passed=True,layer_matches=384,layer_total=384,token_matches=8,tokens=real['tokens'])},extra_eight_token_oracle_sha256=sha(P/'real-eight.json'),receipts={n:sha(P/n) for n in gates})
 (P/'cpu-tests.json').write_text(json.dumps(cpu,indent=2)+'\n')
 receipt=dict(schema='own-runtime.iq3.packet29.build.v1',passed=True,device_executed=False,real_model_device_qualified=False,literal_all_copy_budget_passed=False,max_compile_jobs=2,numeric_threads=2,host_memory_limit_bytes=8*1024**3,artifacts_sha256=binaries,cpu_tests_sha256=sha(P/'cpu-tests.json'),nongemv_fixture_host_sha256=gates['fixture-gates.json']['output_sha256'],input_sha256=sha(B/'input/input.json'),census_sha256=sha(P/'census.json'),sources=sources(),arithmetic='iq3-p17-detmath-v2',host_precision=host_precision,precise_compile_flags=flags,device_link_commands=links,math_gate=math,queue_gate=queue,gate_receipts={n:sha(P/n) for n in gates})
 (P/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
def main():
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','host','icpx-host','asan','device','cheap','real','seal','all']);a=p.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 B.mkdir(exist_ok=True);(B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 # ASan reserves a large virtual address shadow; only compilation/ordinary CPU
 # gates use RLIMIT_AS. The tiny sanitizer processes have a separate RSS watcher.
 if a.stage not in ('cheap','all'):
  old=resource.getrlimit(resource.RLIMIT_AS)[1];cap=min(8*1024**3,old) if old!=resource.RLIM_INFINITY else 8*1024**3;resource.setrlimit(resource.RLIMIT_AS,(cap,cap))
 if a.stage in ('prepare','all'):prepare()
 if a.stage in ('host','icpx-host','asan','device'):configure(a.stage)
 if a.stage=='all':
  for mode in ('host','icpx-host','asan','device'):configure(mode)
 if a.stage in ('cheap','all'):
  for script in ('cpu_gates.py','copy_budget.py','fixture_gate.py','validation_gate.py','sanitizer_gate.py','test_window.py','entry_smoke_test.py','entry_codes.py','census.py','identity_tree_test.py','host_benchmark.py','capture_gate.py','carryover.py','priority_gate.py','expert_down_review_gate.py'):
   run([PY,'-B',P/script],script+'.log',bounded=script!='sanitizer_gate.py')
 if a.stage in ('real','all'):run([PY,'-B',P/'real_eight_gate.py'],'real-eight.log')
 if a.stage in ('seal','all'):seal()
if __name__=='__main__':main()
