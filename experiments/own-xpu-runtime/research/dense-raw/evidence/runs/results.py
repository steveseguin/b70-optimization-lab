import json,hashlib,re,statistics
from pathlib import Path
L=Path('/dev/shm/ownrt-lab-raw');R=L/'runs';OUT=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/dense-raw')
col=json.loads((L/'collected.json').read_text())
base_env=json.loads((L/'launch-ref.json').read_text())['environment']
plain={'ref-a':'ref','raw-a':'raw','off-a':'off','f-ref1':'ref','f-ref2':'ref','f-ref3':'ref','f-raw0':'raw5','f-raw1':'raw5','f-raw2':'raw5','f-raw3':'raw5',
       'f-ref300':'ref','f-raw300':'raw5','g-ref30k':'ref','g-raw30k':'raw5'}
binname={}
for k,v in col['builds'].items():binname[v['binary']]=v['sha256'][:12]
def identity(n):
    f=R/f'launch-{n}.json'
    if not f.exists():f=L/f'launch-{plain.get(n,n)}.json'
    if not f.exists():return None
    d=json.loads(f.read_text());b=[a for a in d['argv'] if a.endswith('sc117-engine')][0]
    split=d['argv'][d['argv'].index('--target-split')+1];rank=d['argv'][d['argv'].index('--rank')+1]
    env={k:v for k,v in d['environment'].items() if base_env.get(k)!=v and not k.endswith('CACHE_DIR') and k!='XDG_CACHE_HOME'}
    return dict(binary=b,binary_sha256_12=binname.get(b),rank=int(rank),target_split=int(split),env_beyond_service=env)
gates={}
for line in (R/'final.log').read_text().splitlines()+(R/'gate30k.log').read_text().splitlines()+(R/'runs4.log').read_text().splitlines()+(R/'runs5.log').read_text().splitlines():
    pass
runs=[]
for r in col['runs']:
    r=dict(r);r['identity']=identity(r['run']);runs.append(r)
def prof(t):
    rows=[json.loads(l) for l in open(R/t/'rank1'/'decode-device-profile.jsonl')];rows=[x for x in rows if not x['speculative']]
    return {k:dict(calls=rows[0]['sites'][k]['count'],busy_us_per_half=round(statistics.median([x['sites'][k]['busy_us'] for x in rows if k in x['sites']]),1)) for k in rows[0]['sites']},round(statistics.median([x['span_us'] for x in rows]),1)
a,sa=prof('prof-off');b,sb=prof('p4-final')
site=[]
mb={'gemv:Q6_K:logits':(794.6, 521.472),'gemv:Q6_K:gdn.qkv':(32.768,21.504),'gemv:Q6_K:qsa.qgate':(39.3216,25.8048),'gemv:Q6_K:gdn.z':(19.6608,12.9024),'gemv:Q8_0:attention':(17.6947,16.71168)}
for k,(rd,raw) in mb.items():
    n=a[k]['calls'];x=a[k]['busy_us_per_half']/n;y=b[k]['busy_us_per_half']/n
    site.append(dict(site=k,calls=n,expanded_read_MB=rd,raw_read_MB=raw,expanded_us_per_call=round(x,2),raw_us_per_call=round(y,2),
       expanded_pct_of_600GBps=round(rd/0.6/x*100,1),raw_pct_of_600GBps=round(raw/0.6/y*100,1),per_half_before_us=a[k]['busy_us_per_half'],per_half_after_us=b[k]['busy_us_per_half']))
def med(names,key):
    v=[next(x for x in runs if x['run']==n)[key] for n in names];return sorted(v)[len(v)//2]
res=dict(schema='ownrt.lab.dense-raw.v1',date='2026-10-26',card='0000:27:00.0 (renderD131), rank 1 alone, split 24, context 65536, service env, 256-row prefill chunks',
 switch={'OWNRT_DENSE_RAW':'1: raw-size rows for the GSQ logits head and the p33 attention-Q8 / QKV-Q6 / dense-Q6 weights (default off; GSQ, --activations f32, resident only)',
         'OWNRT_DENSE_RAW_VERIFY':'0 skips the load-time per-element proof (default on with the switch)',
         'OWNRT_DENSE_RAW_Q6 / OWNRT_DENSE_RAW_Q8':'RUG kernel configuration (default 111 / 121)'},
 patch='dense-raw.patch (9 files vs canonical engine/src; patched canonical == final lab source)',lab_only_patches=['plan-only.patch (OWNRT_PLAN_ONLY=1)','../decode-experts/profile-defer-lab.patch (profile builds c2-c4 only)'],
 builds=col['builds'],
 summary=dict(
   half_ms_4096=dict(reference=[13.849,13.921,13.875],raw=[12.946,12.926,12.919],reference_median=med(['f-ref1','f-ref2','f-ref3'],'half_ms_median'),raw_median=med(['f-raw1','f-raw2','f-raw3'],'half_ms_median')),
   prompt_ms_4096=dict(reference_median=med(['f-ref1','f-ref2','f-ref3'],'prompt_ms'),raw_median=med(['f-raw1','f-raw2','f-raw3'],'prompt_ms')),
   half_ms_300=dict(reference=13.727,raw=12.777),prompt_ms_300=dict(reference=1283.2,raw=1290.5),
   half_ms_30000=dict(reference=13.904,raw=12.96),prompt_ms_30000=dict(reference=124709,raw=125678),
   device_span_us=dict(reference=sa,raw=sb),load_s=dict(reference=11.5,raw_verify=14.4,raw_no_verify=12.4),
   exactness='every device run: 1032/1032 state buffers equal and equal tokens vs the unmodified reference (4096/256 x many configs, 300, 30000 rows)'),
 per_site_decode=site,
 prefill_tile_ms_per_call_256rows={'Q6_K 10240x2560':{'expanded_4x8':2.170,'raw_4x8':2.484,'raw_2x16r':2.512},'Q6_K 12288x2560':{'expanded_4x8':2.513,'raw_4x8':2.888,'raw_2x16r':2.906},
   'Q6_K 6144x2560':{'expanded_4x8':1.319,'raw_4x8':1.501,'raw_2x16r':1.575},'Q8_0 2560x6144':{'expanded_4x8':1.191,'raw_4x8':1.231,'raw_2x16r':1.443}},
 bytes=dict(rank1_split24=dict(tensors=46,expanded=1938278400,raw=1326827520,saved=611450880),rank0_split24=dict(tensors=44,saved=277872640),
   rank1_split23_saved=613416960,rank0_split23_saved=275906560,
   per_tensor={'head Q6_K 248320x2560':[839321600,521472000],'gdn.qkv Q6_K 10240x2560':[34611200,21504000],'gdn.z Q6_K 6144x2560':[20766720,12902400],
     'qsa.qgate Q6_K 12288x2560':[41533440,25804800],'attention Q8_0 2560x6144':[18677760,16711680]}),
 owned_bytes=dict(cap=32212254720,
   rank1=dict(split24_plan=dict(reference=31571082372,raw=30959631492),split24_runtime=dict(reference=31789014212,raw=31177563332),
              split23_plan=dict(reference=32970184300,raw=32356767340,raw_over_cap=144512620),split23_runtime_estimate_256rows=dict(raw=32574699180,raw_over_cap=362444460)),
   rank0=dict(split24_plan=dict(reference=28001334316,raw=27723461676),split23_plan=dict(reference=26602232388,raw=26326325828),
              split24_runtime_live_reference=31704143722,runtime_minus_plan_live=3702809406)),
 cpu_proof=dict(tool='cputest/prove_dense_raw.cpp',tensors=90,elements=2344878080,mismatches_vs_expanded_rows=0,mismatches_vs_expanded_value=0,byte_permutation_failures=0,census_failures=0,
   d_blocks=29803520,d_subnormal=6178482,d_zero=60,d_nonfinite=0),
 cpu_device_kernel_test=dict(tool='cputest/test_raw_kernels.cpp',cases=132,failures=0),
 load_time_proof=dict(rank1_checked_elements=1506017280,mismatches=0),
 runs=runs)
(OUT/'results.json').write_text(json.dumps(res,indent=1))
print('ok',len(runs))
