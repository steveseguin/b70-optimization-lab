"""Packet194 engine-dispatch exactness gate (CPU only): native/diet_fixture.cpp linked against the packet's own gnu-host objects
(the real p49d::expert dispatch of the rebuilt p49d_expert_submit TU), on GNU and Intel host twins, with packet162b's real
layer-0/layer-24 rows (read in place, digest-recorded) and synthetic scenario banks. See the fixture header."""
import json,os,resource,subprocess,sys,time
from pathlib import Path
from p194_v5_build_engine import P,LOCAL,ROOT,B,STAGE,CHECKED,sha,save,limits,run
OUT=B/'diet-fixture';INTEL='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
REAL=STAGE/'packet162-iq2-lookup/build/micro-inputs'
MODES=(('GNU','/usr/bin/g++'),('Intel',INTEL))
def main():
 limits();OUT.mkdir(parents=True,exist_ok=True)
 prior=json.loads((P/'engine-commands.json').read_text())
 args=list(next(r['command'] for r in prior if r['name']=='gnu-host-entry-main'));args=args[1:args.index('-o')];i=args.index('-c');del args[i:i+2]
 rows=[]
 for compiler,cxx in MODES:
  spell=(lambda xs:['-qopenmp' if x=='-fopenmp' else x for x in xs]) if compiler=='Intel' else (lambda xs:xs)
  obj=OUT/(compiler+'.o');binary=OUT/('fixture-'+compiler)
  run([cxx,*spell(args),'-c',P/'native/diet_fixture.cpp','-o',obj],'diet-fixture-'+compiler+'-compile')
  link=list(next(r['command'] for r in prior if r['name']=='gnu-host-link'))
  link=[str(obj) if x.endswith('/entry-main.o') else x for x in link if not x.endswith('own-rt-iq3-entry.cpp.o')]
  link=spell(link);link[0]=cxx;link[link.index('-o')+1]=str(binary)
  if compiler=='Intel':link+=['-no-pie','-Wl,-rpath,/opt/intel/oneapi/compiler/2026.0/lib']
  run(link,'diet-fixture-'+compiler+'-link')
  dest=OUT/('run-'+compiler)
  if dest.exists():
   import shutil;shutil.rmtree(dest)
  env=dict(os.environ,OMP_NUM_THREADS='4',LD_LIBRARY_PATH='/opt/intel/oneapi/compiler/2026.0/lib')
  log=P/'evidence'/f'diet-fixture-{compiler}.log';t=time.monotonic()
  with log.open('w') as stream:r=subprocess.run([str(binary),'--output',str(dest),'--real-rows',str(REAL)],env=env,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,timeout=1800)
  assert r.returncode==0,log.read_text()[-3000:]
  result=json.loads((dest/'result.json').read_text());cases=[json.loads(l) for l in (dest/'cases.jsonl').read_text().splitlines() if l.strip()]
  assert result['passed'] and result['strata']==len(cases)==8+3+3 and result['refusals']==6 and all(c['record_equals_production'] and c['other_bytes']==0 for c in cases),result
  assert all(c['bytes_equal'] for c in cases if not c['nan_stratum']),'non-NaN stratum differs'
  payload=[dict(bank=c['bank'],scenario=c['scenario'],different_words=c['different_words'],nan_vs_nan_words=c['nan_vs_nan_words']) for c in cases if not c['bytes_equal']]
  assert all(c['payload_order_only'] for c in cases if not c['bytes_equal']),payload
  rows.append(dict(compiler=compiler,binary_sha256=sha(binary),seconds=round(time.monotonic()-t,1),result=result,cases=cases,payload_order_rows=payload,cases_sha256=sha(dest/'cases.jsonl')))
  print('diet fixture',compiler,'PASS',result['strata'],'strata',result['byte_equal_strata'],'byte-equal',result['payload_order_only_strata'],'payload-order-only',flush=True)
 # GNU and Intel agree on every byte-equal verdict outside the NaN strata; the diet output digests agree across twins on finite strata
 g={(c['bank'],c['scenario']):c for c in rows[0]['cases']};i={(c['bank'],c['scenario']):c for c in rows[1]['cases']}
 assert set(g)==set(i) and all(g[k]['y_sha256']==i[k]['y_sha256'] for k in g if not g[k]['nan_stratum']),'GNU and Intel diet outputs differ on a finite stratum'
 assert all(g[k]['status']==i[k]['status'] for k in g),'status words differ between twins'
 real=[dict(name='packet162b real gate/up rows (read in place, provenance, never a pin)',parent_relpath=str(f.relative_to(ROOT)),parent_digest=sha(f)) for f in sorted(REAL.glob('*.bin'))]
 save(P/'evidence/diet-fixture.json',dict(passed=True,device_executed=False,model_read=False,parents=real,
  scope='engine-dispatch exactness of expert_gateup=diet (p193diet::GateUp, Arm 13) vs production (the record kernel) through the real p49d::expert with the record selection strings, on GNU and Intel host twins: packet162b real layer-0/24 rows (normal, partial routes, NaN inputs), synthetic exp-halfcache banks (normal, invalid expert, inactive, error-preset, partial routes, NaN/Inf/subnormal inputs); six-argument production == five-argument record dispatch on every stratum; refusals for a non-halfcache layout and an unknown value',
  runs=rows,twins_agree_on_finite_strata=True,
  sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'diet_fixture_gate.py',P/'native/diet_fixture.cpp',CHECKED/'p49d_expert_submit.cpp',CHECKED/'p193_diet.hpp',CHECKED/'p90_expert.hpp',B/'gnu-host/p49d_expert_submit.o')}))
 limits()
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
