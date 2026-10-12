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
 names=['resident-host-gates.json','canary-host-gates.json','owner-gates.json','fixture-gates.json','mini-gnu-host.json','mini-icpx-host.json','mini-asan.json',
  'state-machine-tests.json','review-controller-tests.json','review-native-faults.json','kernel-sizes.json',
  'window-tests.json','identity-tree-tests.json','entry-codes.json','validation-gates.json',
  'expert-down-review-gates.json','rollback-inventory.json','real-campaign.json','real-campaign-icpx-host.json']
 names += ['real-'+mode+'.json' for mode in ('none','ngram','hit','miss')]
 names += ['real-icpx-host-'+mode+'.json' for mode in ('none','ngram','hit','miss')]
 gates={name:json.loads((P/name).read_text()) for name in names}
 assert all(v.get('passed') for v in gates.values())
 archived=gates['fixture-gates.json']['full_receipts'];blob=P/archived['path']
 assert sha(blob)==archived['compressed_sha256']
 raw=gzip.decompress(blob.read_bytes());assert hashlib.sha256(raw).hexdigest()==archived['uncompressed_sha256']
 assert json.loads(raw)['output_sha256']==gates['fixture-gates.json']['output_sha256']
 entries=('own-rt-iq3','nongemv-fixtures','k2-fixtures','jit-smoke','authority-tests','owner-retirement-tests','chain-tests','queue-tests','lifetime-tests')
 binaries={str(x.relative_to(B)):sha(x) for mode in ('gnu-host','icpx-host','asan','device') for x in (B/mode).iterdir() if x.name in entries}
 for compiler in ('gnu-host','icpx-host','asan'):
  assert gates['mini-'+compiler+'.json']['binary_sha256']==binaries[compiler+'/own-rt-iq3']
 for compiler in ('gnu-host','icpx-host'):
  for mode in ('none','ngram','hit','miss'):
   row=gates['real-'+('' if compiler=='gnu-host' else compiler+'-')+mode+'.json']
   assert row['token_matches']==8 and row['layer_matches']==row['layer_total']==384
   assert row['binary_sha256']==binaries[compiler+'/own-rt-iq3']
 assert gates['review-native-faults.json']['binary_sha256']==binaries['gnu-host/own-rt-iq3']
 for row in gates['fixture-gates.json']['rows']:assert row['binary_sha256']==binaries[row['compiler']+'/nongemv-fixtures']
 for row in gates['validation-gates.json']['checks']:
  if 'entry' in row:assert row['binary_sha256']==binaries[row['compiler']+'/'+row['entry']]
 for row in gates['owner-gates.json']['rows']:assert row['binary_sha256']==binaries[row['compiler']+'/'+row['name']]
 host_flags=['-fno-fast-math','-ffp-contract=off'];precision={};links={}
 flags=host_flags+['-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt']
 for mode in ('gnu-host','icpx-host','asan','device'):
  cc=json.loads((B/mode/'compile_commands.json').read_text())
  ll={str(x.relative_to(B)):x.read_text() for x in (B/mode).rglob('link.txt')}
  required=flags if mode=='device' else host_flags
  assert cc and all(all(f in x['command'].split() for f in required) for x in cc)
  assert ll and all(all(f in v.split() for f in required) for v in ll.values())
  precision[mode]=dict(compile_count=len(cc),link_count=len(ll),flags=required,compile_commands_sha256=sha(B/mode/'compile_commands.json'))
  links.update(ll)
 from math_gate import check
 from queue_gate import check as queue_check
 math=check();queue=queue_check()
 identity=json.loads((P/'review-identity-sources.json').read_text())
 for row in identity['rows']:assert row['identical'] and sha(P/row['path'])==row['packet29_sha256']
 cpu=dict(passed=True,device_executed=False,real_model_device_qualified=False,
  mini_cases={c:gates['mini-'+c+'.json']['cases'] for c in ('gnu-host','icpx-host','asan')},
  real_model={c:{m:dict(tokens=8,fixtures=384) for m in ('none','ngram','hit','miss')} for c in ('gnu-host','icpx-host')},
  owner_suites=gates['owner-gates.json']['suites'],window_tests=gates['window-tests.json']['tests'],
  fixture_processes=len(gates['fixture-gates.json']['rows']),fixture_coverage={k:gates['fixture-gates.json']['rows'][0]['receipt'][k] for k in ('fixtures','source_fixtures','gemv_checks','small_gemv_checks','adapter_only_checks')},
  kernel_capture_count=gates['kernel-sizes.json']['kernel_classes'],maximum_capture_bytes=gates['kernel-sizes.json']['max_after'],
  entry_negative_checks=len(gates['entry-codes.json']['checks']),validation_checks=len(gates['validation-gates.json']['checks']),
  symbolic_reduction_checks=gates['identity-tree-tests.json']['checks'],arithmetic_source_files_unchanged=len(identity['rows']),
  receipts={n:sha(P/n) for n in names})
 (P/'cpu-tests.json').write_text(json.dumps(cpu,indent=2)+'\n')
 receipt=dict(schema='own-runtime.iq3.packet32.build.v1',passed=True,device_executed=False,real_model_device_qualified=False,
  process_model='two native ranks, single-device context/queue each, host byte IPC',source_anchor='04e99e40e6',
  max_compile_jobs=2,numeric_threads=2,aggregate_anonymous_memory_limit_bytes=10*1024**3,
  observed_campaign_peak_anonymous_bytes=max(gates[n]['peak_packet_anonymous_bytes'] for n in ('real-campaign.json','real-campaign-icpx-host.json')),
  artifacts_sha256=binaries,cpu_tests_sha256=sha(P/'cpu-tests.json'),nongemv_fixture_host_sha256=gates['fixture-gates.json']['output_sha256'],
  input_sha256=sha(B/'input/input.json'),sources=sources(),arithmetic='iq3-p17-detmath-v2',precision=precision,
  link_commands=links,math_gate=math,queue_gate=queue,gate_receipts={n:sha(P/n) for n in names})
 (P/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 (P/'BINARY-HASHES.md').write_text('# Final binary SHA-256\n\nNo native device binary was executed. Build trees are ignored and retained for the coordinator.\n\n| Binary | SHA-256 |\n| --- | --- |\n'+''.join('| `'+n+'` | `'+h+'` |\n' for n,h in sorted(binaries.items())))
def main():
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','gnu-host','icpx-host','asan','device','cheap','real','seal','all']);a=p.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 B.mkdir(exist_ok=True);(B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 if a.stage in ('prepare','all'):prepare()
 if a.stage in ('gnu-host','icpx-host','asan','device'):configure(a.stage)
 if a.stage=='all':
  for mode in ('gnu-host','icpx-host','asan','device'):configure(mode)
 if a.stage in ('cheap','all'):
  for script in ('cpu_gates.py','fixture_gate.py','validation_gate.py','entry_codes.py','test_window.py',
                 'identity_tree_test.py','capture_gate.py','expert_down_review_gate.py','test_state_machine.py','run_fault_gate.py','canary_host_gate.py'):
   run([PY,'-B',P/script],script+'.log')
  run([PY,'-B',P/'test_controller_review.py','--output',P/'review-controller-tests.json'],'review-controller.log')
  for mode in ('gnu-host','icpx-host','asan'):
   env=os.environ
   if mode=='asan':env['ASAN_OPTIONS']='detect_leaks=1:abort_on_error=1';env['UBSAN_OPTIONS']='halt_on_error=1:print_stacktrace=1'
   run([PY,'-B',P/'gates.py','mini',mode],'mini-'+mode+'.log',bounded=mode!='asan')
  run([PY,'-B',P/'resident_host_gate.py'],'resident-host.log',bounded=False)
 if a.stage in ('real','all'):
  for compiler in ('gnu-host','icpx-host'):run([PY,'-B',P/'real_campaign.py',compiler],'real-campaign-'+compiler+'.log')
  run([PY,'-B',P/'audit_rollback.py'],'rollback-audit.log')
 if a.stage in ('seal','all'):seal()
if __name__=='__main__':main()
