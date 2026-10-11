#!/usr/bin/env python3
"""CPU gates and compile-only device preparation. Device executables NEVER run here."""
import argparse,hashlib,json,os,re,shlex,shutil,struct,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build'
PY='/home/steve/.venvs/vllm-xpu/bin/python';IC='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def save(name,v):(P/name).write_text(json.dumps(v,indent=2)+'\n')
def run(args):
 args=list(map(str,args));print('RUN',' '.join(args),flush=True)
 subprocess.run(args,check=True,cwd=ROOT)
def sources():
 from math_gate import closure
 paths=set(closure())
 for folder in (P,P.parent/'packet19-depcheck'):
  paths.update(x for x in folder.rglob('*') if x.is_file() and 'build' not in x.relative_to(folder).parts and x.suffix in ('.cpp','.hpp','.py','.md'))
 paths.update([P/'CMakeLists.txt',P/'rope.bf16',P/'source-provenance.json',P/'sanitizer-provenance.json',P/'prototype/prototype-provenance.json',P/'receipt.schema.json'])
 paths.update(x for x in (B/'fusion-fixtures').iterdir() if x.is_file())
 return {str(x.relative_to(ROOT)):sha(x) for x in sorted(paths)}
def prepare():
 if not (B/'input').exists():run([PY,'-B',P/'prepare.py','--output',B/'input'])
 if not (B/'fusion-fixtures').exists():run([PY,'-B',P/'prototype/fixtures.py','--output',B/'fusion-fixtures'])
 values=struct.unpack('<262144H',(P/'rope.bf16').read_bytes())
 (B/'fusion-rope.hpp').write_text('#pragma once\nnamespace rope_constants { inline constexpr int positions=4096; inline constexpr uint16_t table[]={'+','.join(map(str,values))+'};}\n')
def compile_sources():
 from math_gate import closure
 return {str(x):sha(x) for x in sorted(set(closure()) | set(P.glob('*.cpp')) | set(P.glob('*.hpp')) | {P/'CMakeLists.txt',P.parent/'packet4/owner_test.cpp'})}
def compiled_artifacts():
 return [B/'host/own-rt-iq3',B/'device/own-rt-iq3',B/'host/libmath_bridge.so',*[B/'host'/name for name in ('authority-tests','owner-retirement-tests','chain-tests','queue-tests')],*[B/tag/name for tag in ('host','icpx-host','device') for name in ('fused-fixtures','nongemv-fixtures')]]
def compile_all():
 prepare()
 before=compile_sources()
 for tag,compiler,host in [('host','/usr/bin/g++','ON'),('icpx-host',IC,'ON'),('device',IC,'OFF')]:
  run(['cmake','-S',P,'-B',B/tag,'-DCMAKE_CXX_COMPILER='+compiler,'-DOWN_RT_HOST_ONLY='+host])
  args=['cmake','--build',B/tag,'-j2']
  if tag=='icpx-host':args+=['--target','fused-fixtures','nongemv-fixtures']
  run(args)
 cached=read(B/'sanitized/build.json') if (B/'sanitized/build.json').exists() else None
 if not cached or not Path(cached['binary']).exists() or sha(Path(cached['binary']))!=cached['sha256'] or any(not Path(path).is_file() or sha(Path(path))!=h for path,h in cached['sources'].items()):
  run([PY,'-B',P/'depcheck_build.py','--source',P,'--tag','sanitized'])
 assert before==compile_sources(), 'source changed during build'
 (B/'compile-receipt.json').write_text(json.dumps(dict(sources=before,artifacts={str(x):sha(x) for x in compiled_artifacts()}),indent=2)+'\n')
def gates():
 run([B/'host/own-rt-iq3','--canary','--memory','resident','--cards','2','--card','0','--seconds','600','--output',B/'cpu-canary'])
 c=read(B/'cpu-canary/receipt.json');assert c['passed'] and not c['device_executed'];c['binary_sha256']=sha(B/'host/own-rt-iq3');save('cpu-canary.json',c)
 for name in ('authority-tests','owner-retirement-tests','chain-tests','queue-tests'):
  run([B/'host'/name])
 for mode in ('core','parallel'):
  run([PY,'-B',P/'test.py','--binary',B/'host/own-rt-iq3','--scratch',B/f'mini-{mode}-{time.time_ns()}','--input',B/'input','--receipt',P/f'cpu-mini-{mode}.json','--nongemv',mode])
 run([PY,'-B',P/'control_gate.py']);run([PY,'-B',P/'fixture_gate.py'])
 run([PY,'-B',P/'guard_tests.py']);run([PY,'-B',P/'sanitizer_gate.py','all'])
 for gemv,n in [('frozen',64),('r5',8)]:run([PY,'-B',P/'cpu_gate.py','--gemv',gemv,'--cards','2','--max-new',n,'--output',B/f'real-{gemv}-{time.time_ns()}'])
 run([PY,'-B',P/'measure_census.py']);run([PY,'-B',P/'test_mismatch.py'])
def seal():
 from math_gate import check
 from queue_gate import check as queues
 math=check();queue=queues();host=sha(B/'host/own-rt-iq3')
 compiled=read(B/'compile-receipt.json');assert compiled['sources']==compile_sources()
 assert compiled['artifacts']=={str(x):sha(x) for x in compiled_artifacts()}
 for name,digest in read(P/'source-provenance.json')['sha256'].items():assert sha(ROOT/name)==digest,'sealed source changed '+name
 real={m:read(P/f'cpu-real-{m}.json') for m in ('frozen','r5')}
 for m,n in [('frozen',64),('r5',8)]:
  r=real[m];assert r['passed'] and r['binary_sha256']==host and r['layer_matches']==r['layer_total']==384 and r['token_matches']>=n and not r['device_executed']
  assert all(sha(Path(path))==digest for path,digest in r['bindings'].items())
 token_launches={}
 for mode,r in real.items():
  out=Path(r['argv'][r['argv'].index('--output')+1])
  timing=[json.loads(x) for x in (out/'timings.jsonl').read_text().splitlines()]
  prefill=[json.loads(x) for x in (out/'prefill-timings.jsonl').read_text().splitlines()]
  assert len(timing)==len(r['tokens']) and all(x['kernel_submissions']<= (926 if mode=='frozen' else 876) for x in timing)
  token_launches[mode]=dict(binary_sha256=host,device_executed=False,generated=timing,prefill_positions=len(prefill),prefill_launch_counts=sorted({x['kernel_submissions'] for x in prefill}),timings_sha256=sha(out/'timings.jsonl'),prefill_timings_sha256=sha(out/'prefill-timings.jsonl'))
 save('cpu-token-launches.json',dict(passed=True,device_executed=False,rows=token_launches))
 mini={m:read(P/f'cpu-mini-{m}.json') for m in ('core','parallel')}
 assert all(r['passed'] and r['binary_sha256']==host and len(r['tests'])==13 for r in mini.values())
 canary=read(P/'cpu-canary.json');assert canary['passed'] and not canary['device_executed'] and canary['binary_sha256']==host
 mismatch=read(P/'cpu-mismatch-rejection.json');assert mismatch['passed'] and mismatch['binary_sha256']==host
 control=read(P/'cpu-control.json');assert control['passed'] and control['binary_sha256']==host and len(control['control_comparisons'])==6
 p18=read(P.parent/'packet18-decode-v2/build-receipt.json')
 assert control['baseline_sha256']==p18['artifacts_sha256']['host/own-rt-iq3']==sha(P.parent/'packet18-decode-v2/build/host/own-rt-iq3')
 fixture=read(P/'fixture-gates.json');assert fixture['passed'] and len(fixture['rows'])==8
 assert fixture['fixture_inputs']=={x.name:sha(x) for x in (B/'fusion-fixtures').iterdir() if x.is_file()}
 for row in fixture['rows']:assert row['binary_sha256']==sha(B/row['compiler']/row['component'])
 san_names=['sanitizer-mini.json','sanitizer-integration.json','sanitizer-real-short.json','sanitizer-real-full.json','sanitizer-unit.json']
 san={n:read(P/n) for n in san_names};assert all(r['passed'] and not r['device_executed'] for r in san.values())
 assert san['sanitizer-mini.json']['runs']==16 and san['sanitizer-mini.json']['seeds']==[0,1,17,73]
 assert len(san['sanitizer-integration.json']['runs'])==8
 assert san['sanitizer-real-short.json']['positions']==2 and san['sanitizer-real-short.json']['fixtures']==96 and san['sanitizer-real-short.json']['control_binary_sha256']==p18['artifacts_sha256']['host/own-rt-iq3']
 assert san['sanitizer-real-short.json']['seeds']==[0,1,17,73] and san['sanitizer-real-full.json']['positions']==87 and san['sanitizer-real-full.json']['layer_matches']==48
 sb=read(B/'sanitized/build.json');assert sha(Path(sb['binary']))==sb['sha256']
 assert all(sha(Path(path))==h for path,h in sb['sources'].items()),'sanitizer sources changed'
 for mode in ('core','parallel'):
  for cards in (1,2):
   for seed in (0,1,17,73):
    r=read(P/f'sanitizer-mini-{mode}-{cards}-{seed}.json')
    assert r['passed'] and not r['sanitizer']['violations'] and r['binary_sha256']==sb['sha256'] and r['source_manifest_sha256']==sha(B/'sanitized/build.json')
 for r in san['sanitizer-integration.json']['runs']:
  assert r['result']['passed'] and r['result']['binary_sha256']==sb['sha256'] and len(r['result']['tests'])==13
  assert all(not t['sanitizer']['violations'] for t in r['result']['tests'])
 for suffix in ['real-full',*[f'real-short-{s}' for s in (0,1,17,73)]]:assert read(P/f'sanitizer-{suffix}.json')['binary_sha256']==sb['sha256']
 census=read(P/'launch-census-measured.json');assert census['passed']
 for k,r in census['rows'].items():assert r['binary_sha256']==host
 assert census['rows']['frozen-on']['launches']<=926 and census['rows']['r5-on']['launches']<=876
 # Original independent memory plan plus explicit 1 MiB descriptor admission
 # reserve per owner. Measured allocator bytes remain in launch-census receipt.
 run([PY,'-B',P/'census.py'])
 mem=read(P/'census.json')
 for r in mem.values():
  r['fused_descriptor_reserve_bytes_per_card']=1048576
  r['owned_peak_bytes_per_card']=[x+1048576 for x in r['owned_peak_bytes_per_card']]
  assert all(x<30*1024**3 for x in r['owned_peak_bytes_per_card'])
 save('census.json',mem)
 flags=['-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt']
 links={str(x.relative_to(B)):x.read_text() for x in (B/'device').rglob('link.txt')};assert len(links)==3
 assert all(all(f in shlex.split(line) for f in flags) for line in links.values())
 commands=read(B/'device/compile_commands.json');assert all(all(f in shlex.split(row['command']) for f in flags) for row in commands)
 assert all(Path(row['file']).resolve() in {ROOT/x for x in math['files']} for row in commands)
 units={}
 for name in ('authority-tests','owner-retirement-tests','chain-tests','queue-tests'):units[name]=subprocess.check_output([str(B/'host'/name)],text=True)
 windows=subprocess.run([PY,'-B',str(P/'test_window.py')],capture_output=True,text=True,check=True)
 save('window-tests.json',dict(passed=True,device_executed=False,stdout=windows.stdout,stderr=windows.stderr))
 cpu=dict(passed=True,device_executed=False,binary_sha256=host,real_model=real,integration=mini,control=control,canary=canary,mismatch=mismatch,units=units,sanitizer={n:sha(P/n) for n in san_names},fixtures_sha256=sha(P/'fixture-gates.json'),launch_census_sha256=sha(P/'launch-census-measured.json'),token_launches_sha256=sha(P/'cpu-token-launches.json'))
 save('cpu-tests.json',cpu)
 artifacts={str(x.relative_to(B)):sha(x) for x in [B/'host/own-rt-iq3',B/'sanitized/depcheck-runtime',*[B/tag/name for tag in ('host','icpx-host','device') for name in ('fused-fixtures','nongemv-fixtures')],B/'device/own-rt-iq3']}
 deps={}
 for name in ('own-rt-iq3','fused-fixtures','nongemv-fixtures'):
  deps[name]=subprocess.check_output(['readelf','-d',str(B/'device'/name)],text=True);assert 'libsycl' in deps[name]
 save('build-receipt.json',dict(schema='own-runtime.iq3.packet21.build.v1',passed=True,device_executed=False,device_qualified=False,fault_halt_boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),arithmetic='iq3-p17-detmath-v2',max_compile_jobs=2,numeric_threads=2,compiler_versions={name:subprocess.check_output([compiler,'--version'],text=True).splitlines()[0] for name,compiler in [('GNU','g++'),('Intel',IC)]},artifacts_sha256=artifacts,compile_receipt_sha256=sha(B/'compile-receipt.json'),compile_sources_before_and_after=compiled['sources'],compile_artifacts=compiled['artifacts'],sources=sources(),cpu_tests_sha256=sha(P/'cpu-tests.json'),census_sha256=sha(P/'census.json'),input_sha256=sha(B/'input/input.json'),fused_fixture_host_sha256=fixture['outputs']['fused-fixtures'],nongemv_fixture_host_sha256=fixture['outputs']['nongemv-fixtures'],platform_math_gate=math,queue_isolation_gate=queue,device_link_commands=links,device_dynamic_sections=deps))
 print('SEALED CPU gates; no device ran',flush=True)
def main():
 a=argparse.ArgumentParser();a.add_argument('--phase',choices=['build','gates','seal','all'],default='all');args=a.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 assert 'idle' in subprocess.check_output(['ionice','-p',str(os.getpid())],text=True)
 if (B/'FAULT.json').exists() or list(B.rglob('window.json')):raise RuntimeError('preserve coordinator evidence; cannot rebuild')
 (B/'tmp').mkdir(parents=True,exist_ok=True);os.environ['TMPDIR']=str(B/'tmp');os.environ['OPENBLAS_NUM_THREADS']='2'
 if args.phase in ('all','build'):compile_all()
 if args.phase in ('all','gates'):gates()
 if args.phase in ('all','seal'):seal()
if __name__=='__main__':main()
