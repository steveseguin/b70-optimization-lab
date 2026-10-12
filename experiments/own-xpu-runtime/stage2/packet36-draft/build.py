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
 if not (P/"mtp-manifest.tsv").exists():run([PY,"-B",P/"prepare_mtp.py"],"prepare-mtp.log")
 if not (B/'input').exists():run([PY,'-B',P/'prepare.py','--output',B/'input'],'prepare.log')
 if not (B/'fusion-fixtures').exists():run([PY,'-B',P/'prototype/fixtures.py','--output',B/'fusion-fixtures'],'prepare-fixtures.log')
 values=struct.unpack('<262144H',(P/'rope.bf16').read_bytes())
 (B/'fusion-rope.hpp').write_text('#pragma once\nnamespace rope_constants { inline constexpr int positions=4096; inline constexpr uint16_t table[]={'+','.join(map(str,values))+'};}\n')
def seal():
 from seal import main
 main()
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
                 'identity_tree_test.py','draft_auth_gate.py','capture_gate.py','expert_down_review_gate.py','test_state_machine.py','test_mtp_controller.py','run_fault_gate.py','canary_host_gate.py'):
   run([PY,'-B',P/script],script+'.log')
  run([PY,'-B',P/'test_controller_review.py','--output',P/'review-controller-tests.json'],'review-controller.log')
  for mode in ('gnu-host','icpx-host','asan'):
   env=os.environ
   if mode=='asan':env['ASAN_OPTIONS']='detect_leaks=1:abort_on_error=1';env['UBSAN_OPTIONS']='halt_on_error=1:print_stacktrace=1'
   run([PY,'-B',P/'gates.py','mini',mode],'mini-'+mode+'.log',bounded=mode!='asan')
   run([PY,'-B',P/'mtp_gates.py',mode],'mtp-mini-'+mode+'.log',bounded=mode!='asan')
  run([PY,'-B',P/'resident_host_gate.py'],'resident-host.log',bounded=False)
 if a.stage in ('real','all'):
  for compiler in ('gnu-host','icpx-host'):run([PY,'-B',P/'real_campaign.py',compiler],'real-campaign-'+compiler+'.log',bounded=False)
  run([PY,'-B',P/'audit_rollback.py'],'rollback-audit.log')
 if a.stage=='all':
  q=P.parent/'packet31-mtp-acceptance'
  missing=not (q/'build/matmul.so').exists()
  if missing:run([PY,'-B',P/'reference_reproduce.py','prepare'],'reference-prepare.log',bounded=False)
  for name in ('incident-retrospective','code-review','customer-email','benchmark-analysis'):
   if missing and not (B/('captured-'+name)).exists():
    # Regenerate only a missing target capture, never write packet31.
    # prepare_target's prompt list is widened for this requested name below.
    run([PY,'-B',P/'reference_reproduce.py','prepare-input',name],'reference-input-'+name+'.log',bounded=False)
    run([PY,'-B',P/'reference_reproduce.py','target',name],'reference-target-'+name+'.log',bounded=False)
   run([PY,'-B',P/'capture_cpu.py',name],'capture-final-'+name+'.log',bounded=False)
   if missing:run([PY,'-B',P/'reference_reproduce.py','reference',name],'reference-samples-'+name+'.log',bounded=False)
   run([PY,'-B',P/'compare_draft.py',name],'agreement-final-'+name+'.log',bounded=False)
 if a.stage=='all':run([PY,'-B',P/'pipeline_draft_agreement.py'],'pipeline-draft-agreement.log')
 if a.stage in ('seal','all'):seal()
if __name__=='__main__':main()
