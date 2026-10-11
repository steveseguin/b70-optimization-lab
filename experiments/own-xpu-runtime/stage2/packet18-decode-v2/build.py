#!/usr/bin/env python3
"""CPU gates and compile-only SYCL preparation. Never executes a device binary."""
import argparse, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
BUILD=HERE/'build'
PY='/home/steve/.venvs/vllm-xpu/bin/python'
COMPILER='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def source_hashes():
  folders=[HERE,*[HERE.parent/n for n in ('packet2','packet3','packet4','packet6-kopt','packet7-kopt2','packet8-kopt3','packet9-kopt4','packet10-kopt5','packet19-depcheck')],HERE.parents[1]/'stage1/packet3-prep/src']
  paths=[]
  for folder in folders:
   paths.extend(p for p in folder.rglob('*') if p.is_file() and 'build' not in p.relative_to(folder).parts and p.suffix in ('.cpp','.hpp','.py'))
  paths.extend([HERE/'rope.bf16',HERE/'source-provenance.json',HERE/'integration-provenance.json',HERE.parent/'packet17-detmath/detmath.hpp',HERE.parent/'packet17-detmath/arithmetic.json',HERE/'CMakeLists.txt',HERE/'receipt.schema.json',ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle/tokenizer.py',ROOT/'experiments/own-xpu-runtime/stage1/packet1b/loaders/headers.py',ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/admission-receipt.json',ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json'])
  return {str(p.relative_to(ROOT)):sha(p) for p in sorted(set(paths))}

def main():
 p=argparse.ArgumentParser();p.add_argument('--keep-build',action='store_true');p.add_argument('--reuse-real-gates',action='store_true');p.add_argument('--reuse-sanitizer-gates',action='store_true');a=p.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 assert 'idle' in subprocess.check_output(['ionice','-p',str(os.getpid())],text=True,timeout=2)
 assert not BUILD.is_symlink()
 if any(BUILD.rglob('window.json')) or (BUILD/'FAULT.json').exists():raise SystemExit('preserve coordinator windows/fault evidence before rebuilding')
 (BUILD/'tmp').mkdir(parents=True,exist_ok=True)
 os.environ['TMPDIR']=str(BUILD/'tmp')
 r=dict(schema='own-runtime.iq3.packet18.build.v1',passed=False,device_executed=False,max_compile_jobs=2,numeric_threads=2,commands=[])
 def run(cmd,timeout=1200):
  cmd=list(map(str,cmd));v=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=timeout)
  r['commands'].append(dict(argv=cmd,returncode=v.returncode,stdout=v.stdout,stderr=v.stderr))
  print('PASS' if not v.returncode else 'FAIL', ' '.join(cmd),flush=True)
  if v.returncode:raise RuntimeError(v.stderr+v.stdout)
  return v.stdout
 before_sources=source_hashes()
 r['sources_before_build']=before_sources
 from math_gate import check
 r['platform_math_gate']=check()
 from queue_gate import check as queue_check
 r['queue_isolation_gate']=queue_check()
 provenance=json.loads((HERE/'source-provenance.json').read_text())
 assert all(sha(ROOT/name)==digest for name,digest in provenance.items()), 'read-only source provenance changed'
 r['original_source_hashes_verified']=provenance
 authority=json.loads((HERE.parent/'packet17-detmath/arithmetic.json').read_text())
 assert authority['arithmetic']=='iq3-p17-detmath-v2' and authority['rope_sha256']==sha(HERE/'rope.bf16'), 'arithmetic/table authority changed'
 try:
  run([COMPILER,'--version'])
  for mode,compiler,host in [('host','/usr/bin/g++','ON'),('device',COMPILER,'OFF')]:
   run(['cmake','-S',HERE,'-B',BUILD/mode,f'-DCMAKE_CXX_COMPILER={compiler}',f'-DOWN_RT_HOST_ONLY={host}'])
   run(['cmake','--build',BUILD/mode,'-j2'])
  flags=['-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt']
  links=list((BUILD/'device').rglob('link.txt'));assert links, 'generated device link.txt missing'
  r['device_link_commands']={str(p.relative_to(BUILD)):p.read_text() for p in links}
  for text in r['device_link_commands'].values():assert all(flag in text.split() for flag in flags), 'missing precision option on device link'
  compile_commands=json.loads((BUILD/'device/compile_commands.json').read_text())
  assert all(Path(row['file']).resolve() in {ROOT/name for name in r['platform_math_gate']['files']} for row in compile_commands), 'device translation unit bypasses math grep'
  assert all(all(flag in row['command'].split() for flag in flags) for row in compile_commands), 'missing device compile precision option'
  r['device_ldd']=run(['ldd',BUILD/'device/own-rt-iq3'])
  assert 'not found' not in r['device_ldd'], 'device shared library missing (loader-only check)'
  dynamic=run(['readelf','-d',BUILD/'host/own-rt-iq3'])
  assert not any(x in dynamic.lower() for x in ('libsycl','libze_loader','libur_loader','libopencl'))
  units={name:run([BUILD/'host'/name]) for name in ('authority-tests','owner-retirement-tests','chain-tests','queue-tests')}
  inp=BUILD/'input'
  if not inp.exists():run([PY,'-B',HERE/'prepare.py','--output',inp])
  for mode in ('core','parallel'):
   run([PY,'-B',HERE/'test.py','--binary',BUILD/'host/own-rt-iq3','--scratch',BUILD/f'tests-{mode}-{time.time_ns()}','--input',inp,'--receipt',HERE/f'cpu-mini-{mode}.json','--nongemv',mode])
  canary_path=BUILD/f'canary-cpu-{time.time_ns()}'
  run([BUILD/'host/own-rt-iq3','--canary','--cards','2','--card','0','--memory','resident','--seconds','30','--output',canary_path])
  r['canary_cpu_mock']=json.loads((canary_path/'receipt.json').read_text())
  assert r['canary_cpu_mock']['passed'] and not r['canary_cpu_mock']['device_executed']
  run([PY,'-B',HERE/'test_mismatch.py'])
  run([PY,'-B',HERE/'test_window.py'])
  run([PY,'-B',HERE/'census.py'])
  if not a.reuse_sanitizer_gates:
   run([PY,'-B',HERE/'depcheck_build.py','--source',HERE,'--tag','sanitized'])
   run([PY,'-B',HERE/'guard_tests.py'])
   run([PY,'-B',HERE/'sanitizer_gate.py','all'],10950)
  for dispatch in ('frozen','r5'):
   gate=HERE/f'cpu-real-{dispatch}.json'
   if a.reuse_real_gates:
    data=json.loads(gate.read_text());assert data['passed'] and data['binary_sha256']==sha(BUILD/'host/own-rt-iq3'), 'real CPU gate requires current binary'
    from cpu_gate import ORACLE
    assert len(data['tokens'])>=(64 if dispatch=='frozen' else 8) and data['tokens']==json.loads((ORACLE/'result.json').read_text())['tokens'][:len(data['tokens'])], 'real CPU coverage/token binding'
    assert json.loads((ORACLE/'input.json').read_text())['tokens']==json.loads((inp/'input.json').read_text())['tokens'], 'real CPU prompt binding'
    assert data['layer_matches']==data['layer_total']==384 and all(row['oracle_sha256']==sha(ORACLE/f"step{row['step']}"/f"layer-{row['layer']:02}.bf16") and row['sha256']==row['oracle_sha256'] for row in data['layers']), 'real CPU fixture binding'
    assert '--oracle' in data['argv'] and str(ORACLE)==data['argv'][data['argv'].index('--oracle')+1], 'real CPU oracle path'
   else:
    run([PY,'-B',HERE/'cpu_gate.py','--gemv',dispatch,'--max-new',str(64 if dispatch=='frozen' else 8),'--output',BUILD/f'real-{dispatch}-{time.time_ns()}'],10950)
  gates={mode:json.loads((HERE/f'cpu-real-{mode}.json').read_text()) for mode in ('frozen','r5')}
  sanitizer_names=['sanitizer-mini.json','sanitizer-integration.json','sanitizer-real-short.json','sanitizer-real-full.json','sanitizer-unit.json']
  sanitizer={name:json.loads((HERE/name).read_text()) for name in sanitizer_names}
  assert all(row['passed'] and row['device_executed'] is False for row in sanitizer.values()), 'sanitizer gate missing/failed'
  assert sanitizer['sanitizer-mini.json']['runs']==16 and sanitizer['sanitizer-mini.json']['seeds']==[0,1,17,73]
  assert len(sanitizer['sanitizer-integration.json']['runs'])==8 and all(len(row['result']['tests'])==13 for row in sanitizer['sanitizer-integration.json']['runs'])
  assert sanitizer['sanitizer-real-short.json']['seeds']==[0,1,17,73] and sanitizer['sanitizer-real-short.json']['fixtures']==96
  assert sanitizer['sanitizer-real-full.json']['positions']==87 and sanitizer['sanitizer-real-full.json']['layer_matches']==48
  tests=sanitizer['sanitizer-unit.json']['tests']
  assert len(tests)==3 and all(row['returncode']==0 for row in tests) and '33/33' in tests[0]['stdout']

  sb=json.loads((BUILD/'sanitized/build.json').read_text())
  assert sha(Path(sb['binary']))==sb['sha256'], 'sanitizer binary changed'
  assert all(sha(Path(name))==digest for name,digest in sb['sources'].items()), 'sanitizer source manifest changed'
  assert all(json.loads((HERE/f'sanitizer-real-short-{seed}.json').read_text())['binary_sha256']==sb['sha256'] for seed in (0,1,17,73))
  assert json.loads((HERE/'sanitizer-real-full.json').read_text())['positions']==87
  r['sanitizer']={'receipts':{name:sha(HERE/name) for name in sanitizer_names},'binary_sha256':sb['sha256'],'build_manifest_sha256':sha(BUILD/'sanitized/build.json'),'violations':0}
  cpu=dict(schema='own-runtime.iq3.packet18.cpu-tests.v1',passed=True,device_executed=False,binary_sha256=sha(BUILD/'host/own-rt-iq3'),integration={mode:json.loads((HERE/f'cpu-mini-{mode}.json').read_text()) for mode in ('core','parallel')},units=units,window_protocol_tests=36,mismatch_rejections=json.loads((HERE/'cpu-mismatch-rejection.json').read_text()),real_model={m:{k:gates[m][k] for k in ('passed','layer_matches','layer_total','token_matches','tokens','first_differing_layer','missing_fixtures','wall_seconds')} for m in gates})
  (HERE/'cpu-tests.json').write_text(json.dumps(cpu,indent=2)+'\n')
  assert source_hashes()==before_sources, 'source changed during build/gates'
  r.update(passed=True,real_model_qualified=False,artifacts_sha256={str(p.relative_to(BUILD)):sha(p) for p in (BUILD/'host/own-rt-iq3',BUILD/'device/own-rt-iq3')},cpu_tests_sha256=sha(HERE/'cpu-tests.json'),census_sha256=sha(HERE/'census.json'),input_sha256=sha(inp/'input.json'))
  shutil.copyfile(inp/'input.json',HERE/'input-receipt.json')
 finally:
  r['sources']=source_hashes()
  r['arithmetic']='iq3-p17-detmath-v2'
  r['arithmetic_sources']={n:h for n,h in r['sources'].items() if n.endswith(('.hpp','.cpp'))}
  if r['passed']:
   for child in BUILD.iterdir():
    if child.is_dir() and (child.name.startswith(('tests-','real-','plan-')) or child.name in ('profile-cpu','tmp')):shutil.rmtree(child)
   extra=BUILD/'input/one.txt'
   if extra.exists():extra.unlink()
   if a.keep_build:
    # Keep coordinator executables/inputs, remove reconstructible compiler scratch.
    for mode in ('host','device'):
     for item in (BUILD/mode).iterdir():
      if item.name in ('own-rt-iq3','compile_commands.json','libmath_bridge.so'):continue
      if item.is_dir():shutil.rmtree(item)
      else:item.unlink()
   else:shutil.rmtree(BUILD)
  r['build_directory_removed']=not BUILD.exists()
  (HERE/'build-receipt.json').write_text(json.dumps(r,indent=2)+'\n')
if __name__=='__main__':main()
