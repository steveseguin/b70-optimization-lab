"""CPU rehearsal at production shape (no device, no model):
  1. GNU host twin: full banks (512 experts, 820-B one-card rows, halfcache table, indirect identity slots), all 384
     real routes, production -> exactness fixtures; the candidate compared byte for byte against production on every
     stratum (cold 384 routes, warm indirect + direct, permuted slot tables (reverse, shuffled) x 8 routes with the
     direct-permuted cross-check, packet162b real rows re-laid out into the 820-B layout, packet162b NaN/invalid
     fixtures f0/f1/f2 x valid/invalid, the non-finite-half bank) and the random-block stress proof
     (--stress 10000 rows = 100,000 IQ2_S blocks per profile, table and computed decode, FP32 chain bits);
  2. Intel host twin verifies every fixture byte and repeats every comparison; GNU and Intel rows identical outside
     the NaN-only strata (where payload order may differ between twins; never canonicalised);
  3. the real device ELF with the real proposal argv under the shared Landlock preparation sandbox
     (ENTRY_PREPARE_OUTPUT): parses the real route file, exercises the generators, exits before any device API;
  4. parser refusal cases (always sandboxed and in preparation mode).
Writes evidence/fixtures.json, evidence/cpu-host-*.jsonl and evidence/cpu-rehearsal.json.
"""
import importlib.util,json,os,subprocess,sys,tempfile,time
from pathlib import Path
from build_engine import P,ROOT,P162,BUILD,EV,LINEAGE,limits,sha,rel,read,save,parent
sys.path.insert(0,str(P.parents[1]/'ops'));import launch_env
FIX=BUILD/'fixtures';REAL=P162/'build/micro-inputs';ROUTES=LINEAGE/'routes-p100b.json';STRESS=10000
HOST_ARGS=['--rank','0','--routes',str(ROUTES),'--real-rows',str(REAL),'--mode','host','--cold-repeats','1','--warm-repeats','2','--passes','2','--stress',str(STRESS)]
FILES={'gateup-cold.bin','gateup-warm.bin','gateup-warm-direct.bin','gateup-fx.bin','gateup-exc.bin','gateup-slots.bin','gateup-real-layer0.bin','gateup-real-layer24.bin'}
CANDIDATE='p58-diet';NAN_STRATA={'fixture-f2-valid','fixture-f2-invalid','exceptional'}   # NaN by construction: compared by is-NaN per word (nan_claim)
CLAIMED_STRATA=('cold','warm','warm-direct','slots-reverse','slots-shuffled','warm-real-layer0','warm-real-layer24','fixture-f0-valid','fixture-f0-invalid','fixture-f1-valid','fixture-f1-invalid')
def env(threads='2'):e=launch_env.environment();e['OMP_NUM_THREADS']=threads;return e
def rows(path):return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
def host(binary,extra,out):
 t=time.monotonic()
 with (EV/(out+'.jsonl')).open('w') as o,(EV/(out+'.stderr')).open('w') as e:
  r=subprocess.run([str(binary),*HOST_ARGS,*extra],env=env(),stdin=subprocess.DEVNULL,stdout=o,stderr=e)
 assert r.returncode==0,out+' failed: '+(EV/(out+'.stderr')).read_text()[:400]
 return dict(stream=rel(EV/(out+'.jsonl')),stream_sha256=sha(EV/(out+'.jsonl')),seconds=round(time.monotonic()-t,1))
def check_stream(path):
 r=rows(path);end=r[-1];assert end['kind']=='summary' and end['passed'] and end['cpu_only'] and end['route_count']==384 and end['real_shapes'] and end['mode']=='host' and end['schema']=='packet58dm.diet.v1' and end['stress_rows']==STRESS and end['candidates']==[CANDIDATE]
 b=[x for x in r if x['kind']=='bytes'];claimed=[x for x in b if x['exactness_claim']];nan=[x for x in b if x['nan_claim']]
 assert all((x['exactness_claim']!=x['nan_claim']) for x in b),'every bytes row is exactly one of exactness/nan claim'
 assert all(x['stratum'] in NAN_STRATA for x in nan) and all(x['stratum'] in CLAIMED_STRATA for x in claimed),'stratum labels'
 unequal=[x for x in claimed if not x['bytes_equal']];assert not unequal,'exactness rows differ: '+str(unequal[:3])
 nan_bad=[x for x in nan if not x['nan_equal']];assert not nan_bad,'NaN-only strata: value difference or status/error byte: '+str(nan_bad[:3])
 nan_payload=[x for x in nan if not x['bytes_equal']]
 per={}
 for x in b:per[x['candidate']+'/'+x['against']]=per.get(x['candidate']+'/'+x['against'],0)+1
 # production vs fixture: 384 cold + warm + warm-direct + 16 slots + 2 real + 6 fixtures + exceptional = 411; candidate: 411 x (production, fixture);
 # production cross-checks: warm-direct vs indirect (1) and slots vs direct-permuted (16)
 assert per=={'production/fixture':411,CANDIDATE+'/production':411,CANDIDATE+'/fixture':411,'production/indirect':1,'production/direct-permuted':16},per
 st={x['profile']:x for x in r if x['kind']=='stress'};assert set(st)=={'mixed','finite'},'stress rows'
 for prof,x in st.items():
  assert x['passed'] and x['value_mismatches']==0 and x['nocache_value_mismatches']==0 and x['table_vs_half_value_mismatches']==0 and x['rows']==STRESS and x['blocks']>=100000 and x['candidate']==CANDIDATE,'stress value mismatch: '+str(x)
  if prof=='mixed':assert x['exceptional_blocks']>0,'mixed stress must contain exception tiles'
  else:assert x['exceptional_blocks']==0 and x['fp32_mismatches']==0 and x['nocache_fp32_mismatches']==0 and x['table_vs_half_mismatches']==0,'finite stress must be bit-identical: '+str(x)
 return dict(bytes_rows=len(b),exact_rows=len(claimed),byte_equal_rows=len(claimed)-len(unequal),nan_rows=len(nan),nan_equal_rows=len(nan)-len(nan_bad),
  nan_payload_order_rows=[dict(candidate=x['candidate'],stratum=x['stratum'],against=x['against'],different_words=x['different_words'],nan_vs_nan_words=x['nan_vs_nan_words']) for x in nan_payload],per_candidate_against=per,
  stress={k:dict(rows=v['rows'],blocks=v['blocks'],exceptional_blocks=v['exceptional_blocks'],chains_compared=v['chains_compared'],fp32_mismatches=v['fp32_mismatches'],nan_vs_nan_mismatches=v['nan_vs_nan_mismatches'],value_mismatches=v['value_mismatches'],nocache_fp32_mismatches=v['nocache_fp32_mismatches'],nocache_value_mismatches=v['nocache_value_mismatches'],table_vs_half_mismatches=v['table_vs_half_mismatches'],table_vs_half_nan_vs_nan=v['table_vs_half_nan_vs_nan'],table_vs_half_value_mismatches=v['table_vs_half_value_mismatches']) for k,v in st.items()},samples=sum(x['kind']=='sample' for x in r))
def main():
 limits();EV.mkdir(exist_ok=True)
 build=read(EV/'build.json');modes={r['mode']:r for r in build['records']}
 if FIX.exists():
  for f in FIX.iterdir():f.unlink()
 FIX.mkdir(exist_ok=True)
 gnu=host(ROOT/modes['gnu-host']['path'],['--fixtures-out',str(FIX)],'cpu-host-gnu');intel=host(ROOT/modes['intel-host']['path'],['--fixtures',str(FIX)],'cpu-host-intel')
 g=check_stream(EV/'cpu-host-gnu.jsonl');i=check_stream(EV/'cpu-host-intel.jsonl')
 key=lambda x:(x['kind']=='bytes' and x['stratum'] not in NAN_STRATA) or (x['kind']=='stress' and x['profile']=='finite')
 gb=[x for x in rows(EV/'cpu-host-gnu.jsonl') if key(x)];ib=[x for x in rows(EV/'cpu-host-intel.jsonl') if key(x)];assert gb==ib,'GNU and Intel byte/stress rows differ outside the NaN-only strata'
 files={rel(f):sha(f) for f in sorted(FIX.iterdir())};assert set(Path(k).name for k in files)==FILES
 save(EV/'fixtures.json',dict(passed=True,device_executed=False,schema='packet58dm.fixtures.v1',generator='GNU host twin (OWN_RT_HOST_ONLY run of the pinned production one-card kernel)',generator_sha256=modes['gnu-host']['sha256'],verifier_sha256=modes['intel-host']['sha256'],
  routes_sha256=sha(ROUTES),real_rows=[parent('packet162b layer0 rows',REAL/'layer0.bin'),parent('packet162b layer24 rows',REAL/'layer24.bin')],files=files,gnu=g,intel=i,gnu_intel_byte_rows_identical=True,
  gnu_intel_identity_scope='every row outside the NaN-only strata (f2, exceptional); those rows are per-twin and may be payload-order-only (both sides NaN in every differing word, no status/error byte)',
  exactness_domain='candidate byte-identical to production on GNU and Intel for every exactness stratum; the NaN-only strata are compared by is-NaN per word (nan_claim) and never by bytes'))
 spec=importlib.util.spec_from_file_location('p58dm_rehearse_entry',P.parents[1]/'ops/rehearse_entry.py');sandbox=importlib.util.module_from_spec(spec);spec.loader.exec_module(sandbox)
 import run_micro;native=run_micro.native_command();binary=Path(native[0]);assert sha(binary)==modes['device']['sha256']
 help_=subprocess.run([str(binary),'--help'],env=env('2'),stdin=subprocess.DEVNULL,capture_output=True,text=True);assert help_.returncode==0 and 'usage' in help_.stdout
 flags=[x for x in native[1:] if x.startswith('--')];assert all(x in help_.stdout for x in flags),'help lists every real flag'
 cases=[]
 def probe(label,argv,expect_rc,expect_text,extra_metadata=()):
  with tempfile.TemporaryDirectory(prefix='p58dm-prepare-') as d:
   scratch=Path(d).resolve();e=dict(env('2'),ENTRY_PREPARE_OUTPUT=str(scratch))
   cp=subprocess.run(argv,env=e,stdin=subprocess.DEVNULL,capture_output=True,text=True,cwd=ROOT,preexec_fn=lambda:sandbox.prepare_restrict(binary,[ROUTES.resolve(),*extra_metadata],scratch))
   receipt=json.loads((scratch/'prepare.json').read_text()) if (scratch/'prepare.json').is_file() else None
  ok=cp.returncode==expect_rc and expect_text in (cp.stdout+cp.stderr);assert ok,(label,cp.returncode,cp.stdout[-300:],cp.stderr[-300:])
  cases.append(dict(case=label,returncode=cp.returncode,expected_returncode=expect_rc,passed=True,prepare_receipt=receipt));return receipt
 receipt=probe('exact real argv (preparation path)',native,0,'PASS CPU preparation before first device call')
 assert receipt and receipt['routes']==384 and receipt['candidates']==1 and receipt['planned_device_peak_bytes']<=run_micro.DEVICE_BYTES_UPPER_BOUND
 probe('no coordinator admission',[x for x in native if x!='--coordinator-admitted-device-window'],1,'device mode requires coordinator admission')
 probe('wrong rank',[native[0],'--rank','1',*native[3:]],1,'rank must be zero')
 probe('unknown option',native+['--unknown','1'],1,'unknown option')
 probe('missing argument',native+['--passes'],1,'missing argument')
 probe('non-numeric repeats',[x if x!='20' else '20x' for x in native],1,'numeric option')
 probe('stress refused on device',native+['--stress','10'],1,'device mode requires coordinator admission')
 probe('one pass refused',[x if x!='2' else '1' for x in native],1,'two passes')
 with tempfile.NamedTemporaryFile('w',suffix='.json',delete=False,dir=str(EV)) as f:f.write('{"routes":[[1,2,3]]}');bad=Path(f.name)
 try:probe('truncated routes file',[native[0],'--rank','0','--routes',str(bad),*native[5:]],1,'route arity',extra_metadata=[bad.resolve()])
 finally:bad.unlink()
 save(EV/'cpu-rehearsal.json',dict(passed=True,device_executed=False,model_reads=False,production_shape=dict(experts=512,routes=384,gateup='640x2560 IQ2_S 820-B one-card rows x2 streams, halfcache table, indirect slots (+ direct and permuted-slot strata)'),candidates=[CANDIDATE],
  gnu=dict(gnu,**g),intel=dict(intel,**i),gnu_intel_byte_rows_identical=True,fixtures_sha256=sha(EV/'fixtures.json'),native_sha256=modes['device']['sha256'],native_command=native,
  help_flags_listed=flags,preparation_probe_cases=cases,sandbox='ops/rehearse_entry.prepare_restrict (Landlock): binary, toolchain, routes json, scratch; no /dev'))
 print(json.dumps(dict(passed=True,gnu_seconds=gnu['seconds'],intel_seconds=intel['seconds'],cases=len(cases),planned_device_peak_bytes=receipt['planned_device_peak_bytes'],stress=g['stress'],nan_payload_order_rows=dict(gnu=len(g['nan_payload_order_rows']),intel=len(i['nan_payload_order_rows'])))))
if __name__=='__main__':main()
