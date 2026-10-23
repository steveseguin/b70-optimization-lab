"""CPU rehearsal at production shape (no device, no model):
  1. GNU host twin: full banks (512 experts), all 384 real routes, both kernels -> exactness fixtures;
  2. Intel host twin verifies every fixture byte; GNU and Intel byte rows must be identical;
  3. alias self-test (no-load variant == production on 16-row expert-0 routes) on both twins;
  4. the real device ELF with the real proposal argv under the shared Landlock preparation sandbox
     (ENTRY_PREPARE_OUTPUT): parses the real route file, exercises both generators, exits before any device API;
  5. parser refusal cases (always sandboxed and in preparation mode).
Writes evidence/fixtures.json, evidence/cpu-host-*.jsonl and evidence/cpu-rehearsal.json.
"""
import importlib.util,json,os,subprocess,sys,tempfile,time
from pathlib import Path
from build_engine import P,ROOT,P162,BUILD,EV,LINEAGE,limits,sha,rel,read,save,parent
sys.path.insert(0,str(P.parents[1]/'ops'));import launch_env
FIX=BUILD/'fixtures';REAL=P162/'build/micro-inputs';ROUTES=LINEAGE/'routes-p100b.json'
HOST_ARGS=['--rank','0','--routes',str(ROUTES),'--real-rows',str(REAL),'--mode','host','--cold-repeats','1','--warm-repeats','2','--passes','1']
def env(threads='8'):e=launch_env.environment();e['OMP_NUM_THREADS']=threads;return e
def rows(path):return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
def host(binary,extra,out):
 t=time.monotonic()
 with (EV/(out+'.jsonl')).open('w') as o,(EV/(out+'.stderr')).open('w') as e:
  r=subprocess.run([str(binary),*HOST_ARGS,*extra],env=env(),stdin=subprocess.DEVNULL,stdout=o,stderr=e)
 assert r.returncode==0,out+' failed: '+(EV/(out+'.stderr')).read_text()[:400]
 return dict(stream=rel(EV/(out+'.jsonl')),stream_sha256=sha(EV/(out+'.jsonl')),seconds=round(time.monotonic()-t,1))
def check_stream(path):
 r=rows(path);end=r[-1];assert end['kind']=='summary' and end['passed'] and end['cpu_only'] and end['route_count']==384 and end['real_shapes'] and end['mode']=='host'
 b=[x for x in r if x['kind']=='bytes'];exact=[x for x in b if x['exactness_claim']];noload=[x for x in b if not x['exactness_claim']]
 assert len(exact)==2*384+2+2 and all(x['bytes_equal'] for x in exact),'exactness rows'
 assert len(noload)==2 and all(not x['bytes_equal'] for x in noload),'no-load outputs must differ from production on a full route'
 alias={x['kernel']:x for x in r if x['kind']=='alias_selftest'};assert set(alias)=={'gateup','down'} and all(x['bytes_equal'] and x['rows_per_route']==16 for x in alias.values()),'alias self-test'
 return dict(exact_rows=len(exact),noload_rows=len(noload),alias_selftest={k:v['bytes_equal'] for k,v in alias.items()},samples=sum(x['kind']=='sample' for x in r))
def main():
 limits();EV.mkdir(exist_ok=True)
 build=read(EV/'build.json');modes={r['mode']:r for r in build['records']}
 if FIX.exists():
  for f in FIX.iterdir():f.unlink()
 FIX.mkdir(exist_ok=True)
 gnu=host(ROOT/modes['gnu-host']['path'],['--fixtures-out',str(FIX)],'cpu-host-gnu');intel=host(ROOT/modes['intel-host']['path'],['--fixtures',str(FIX)],'cpu-host-intel')
 g=check_stream(EV/'cpu-host-gnu.jsonl');i=check_stream(EV/'cpu-host-intel.jsonl')
 gb=[x for x in rows(EV/'cpu-host-gnu.jsonl') if x['kind']=='bytes'];ib=[x for x in rows(EV/'cpu-host-intel.jsonl') if x['kind']=='bytes'];assert gb==ib,'GNU and Intel byte rows differ'
 files={rel(f):sha(f) for f in sorted(FIX.iterdir())};assert set(Path(k).name for k in files)=={'gateup-cold.bin','down-cold.bin','gateup-warm.bin','down-warm.bin','gateup-real-layer0.bin','gateup-real-layer24.bin'}
 save(EV/'fixtures.json',dict(passed=True,device_executed=False,schema='packet192.fixtures.v1',generator='GNU host twin (OWN_RT_HOST_ONLY run of the same kernels)',generator_sha256=modes['gnu-host']['sha256'],verifier_sha256=modes['intel-host']['sha256'],
  routes_sha256=sha(ROUTES),real_rows=[parent('packet162b layer0 rows',REAL/'layer0.bin'),parent('packet162b layer24 rows',REAL/'layer24.bin')],files=files,gnu=g,intel=i,gnu_intel_byte_rows_identical=True))
 # device ELF, real argv, preparation mode under the shared Landlock sandbox (reads only the routes json)
 spec=importlib.util.spec_from_file_location('p192_rehearse_entry',P.parents[1]/'ops/rehearse_entry.py');sandbox=importlib.util.module_from_spec(spec);spec.loader.exec_module(sandbox)
 import run_micro;native=run_micro.native_command();binary=Path(native[0]);assert sha(binary)==modes['device']['sha256']
 help_=subprocess.run([str(binary),'--help'],env=env('2'),stdin=subprocess.DEVNULL,capture_output=True,text=True);assert help_.returncode==0 and 'usage' in help_.stdout
 flags=[x for x in native[1:] if x.startswith('--')];assert all(x in help_.stdout for x in flags),'help lists every real flag'
 cases=[]
 def probe(label,argv,expect_rc,expect_text,extra_metadata=()):
  with tempfile.TemporaryDirectory(prefix='p192-prepare-') as d:
   scratch=Path(d).resolve();e=dict(env('2'),ENTRY_PREPARE_OUTPUT=str(scratch))
   cp=subprocess.run(argv,env=e,stdin=subprocess.DEVNULL,capture_output=True,text=True,cwd=ROOT,preexec_fn=lambda:sandbox.prepare_restrict(binary,[ROUTES.resolve(),*extra_metadata],scratch))
   receipt=json.loads((scratch/'prepare.json').read_text()) if (scratch/'prepare.json').is_file() else None
  ok=cp.returncode==expect_rc and expect_text in (cp.stdout+cp.stderr);assert ok,(label,cp.returncode,cp.stdout[-300:],cp.stderr[-300:])
  cases.append(dict(case=label,returncode=cp.returncode,expected_returncode=expect_rc,passed=True,prepare_receipt=receipt));return receipt
 receipt=probe('exact real argv (preparation path)',native,0,'PASS CPU preparation before first device call')
 assert receipt and receipt['routes']==384 and receipt['planned_device_peak_bytes']<=run_micro.DEVICE_BYTES_UPPER_BOUND
 probe('no coordinator admission',[x for x in native if x!='--coordinator-admitted-device-window'],1,'device mode requires coordinator admission')
 probe('wrong rank',[native[0],'--rank','1',*native[3:]],1,'rank must be zero')
 probe('unknown option',native+['--unknown','1'],1,'unknown option')
 probe('missing argument',native+['--passes'],1,'missing argument')
 probe('non-numeric repeats',[x if x!='20' else '20x' for x in native],1,'numeric option')
 with tempfile.NamedTemporaryFile('w',suffix='.json',delete=False,dir=str(EV)) as f:f.write('{"routes":[[1,2,3]]}');bad=Path(f.name)
 try:probe('truncated routes file',[native[0],'--rank','0','--routes',str(bad),*native[5:]],1,'route arity',extra_metadata=[bad.resolve()])
 finally:bad.unlink()
 save(EV/'cpu-rehearsal.json',dict(passed=True,device_executed=False,model_reads=False,production_shape=dict(experts=512,routes=384,gateup='640x2560 IQ2_S E1 x2 streams',down='2560x640 IQ4_NL tile16'),
  gnu=dict(gnu,**g),intel=dict(intel,**i),gnu_intel_byte_rows_identical=True,fixtures_sha256=sha(EV/'fixtures.json'),native_sha256=modes['device']['sha256'],native_command=native,
  help_flags_listed=flags,preparation_probe_cases=cases,sandbox='ops/rehearse_entry.prepare_restrict (Landlock): binary, toolchain, routes json, scratch; no /dev'))
 print(json.dumps(dict(passed=True,gnu_seconds=gnu['seconds'],intel_seconds=intel['seconds'],cases=len(cases),planned_device_peak_bytes=receipt['planned_device_peak_bytes'])))
if __name__=='__main__':main()
