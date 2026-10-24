#!/usr/bin/env python3
"""Read-only closed local evidence audit. Never imports operational modules."""
from pathlib import Path
import hashlib,json,statistics,gzip,collections,stat
R=Path('/home/steve/llm-optimizations')
P=R/'experiments/own-xpu-runtime/gsq-rco-iq3s/expert-iq3xxs-block/micro'
S=Path('/home/steve/own-xpu-runtime-results/gsq-iq3xxs-block-micro-a')
D=Path(__file__).resolve().parent
index={}
def digest(p):
 p=Path(p); p=p if p.is_absolute() else R/p
 assert not p.is_symlink(),str(p)
 with p.open('rb') as f:
  import os
  before=os.fstat(f.fileno());assert stat.S_ISREG(before.st_mode)
  h=hashlib.sha256()
  while b:=f.read(1024*1024):h.update(b)
  after=os.fstat(f.fileno())
 assert (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)
 index[str(p)]={'path':str(p),'bytes':before.st_size,'sha256':h.hexdigest()}
 return h.hexdigest()
def read(p):digest(p);return json.loads(Path(p).read_text())
def checkpins(m):
 for p,h in m.items():assert digest(p)==h,p
ad=read(S/'admission.json');term=read(S/'terminal.json');mon=read(S/'monitor.json');result=read(S/'result/result.json')
manifest=read(P/'manifest.json');build=read(P/'evidence/native-build.json')
checkpins(ad['plan']['source_sha256'])
for group in ('source_sha256','objects_reused','dependencies'):checkpins(build[group])
assert digest(build['binary'])==build['binary_sha256']==ad['binary_sha256']
assert digest(P/'evidence/native-build.json')==ad['proof_sha256']
assert digest(P/'once.py')==ad['monitor_sha256']
checkpins(manifest['authority'])
plan_path=Path('/home/steve/own-xpu-runtime-results/gsq-iq3xxs-block-micro-a.plan.json')
assert digest(plan_path)=='38c8cc86c52f220fce53cb7267b4c1053c93722efe1f48337bbbc74a8e7e24eb'
assert read(plan_path)==ad['plan']
assert (manifest['device_bytes'],manifest['transfer_bytes'],manifest['pinned_bytes'])==(963610200,965690280,1048576)
for c in manifest['cases']:
 assert digest(c['sparse_weights']['path'])==c['sparse_weights']['sha256']
 for f in c['fixtures'].values():assert digest(f['path'])==f['sha256'] and Path(f['path']).stat().st_size==f['bytes']
for name in ('independent-review.json',):
 d=read(P/'evidence'/name);assert d['passed'];checkpins(d['source_sha256'])
assert term['passed'] is False and term['result']==result and not term['single_term_attempted'] and term['first_error'] is None
assert not term['observed_native_target_fd'] and term['target_descriptors_empty']
assert term['qualification_limit']=='Native target FD not observed; short-run physical identity is not independently attested.'
assert term['status']['MainPID']=='0' and term['status']['ActiveState']=='inactive'
assert result['schema']=='gsq.iq3xxs-block.native-micro.v1'
assert result['passed'] and result['safe_to_exit'] and result['card']==0 and result['profiling'] and not result['model_executed']
assert result['completed_exact_pairs']==84 and result['attempted_kernel_submissions']==168
assert result['device_bytes']==963610200 and result['transfer_bytes']==965690280
assert not result['error'] and not result['cleanup_error']
t=result['teardown'];assert t['safe_to_exit'] and t['exit_code']==0 and t['idle_marker_complete'] and t['in_flight']==t['live_bytes']==0 and not t['error']
before=ad['before'];native=term['native_identity'];seen=0;active=0
allowed={(x['pid'],before['holders'][str(x['pid'])]['start_ticks'],x['node']) for x in before['inventory']['holders']}
for snap,state in [(before,None)]+[(x['snapshot'],x['state']) for x in mon['samples']]+[(term['after'],None)]:
 assert snap['known_fault_baseline_matches'] and snap['kernel']['faults']==before['kernel']['faults']
 assert snap['boot']==before['boot'] and snap['units']==before['units'] and snap['queue']==before['queue'] and not snap['identity_races']
 assert snap['root_free_bytes']>=27000000000 and snap['memory']['MemAvailable']>=8*1024**3
 inv=snap['inventory'];assert not inv['errors'] and inv['metadata_only'] and inv['device_opens']==0
 for h in inv['holders']:
  identity=(h['pid'],snap['holders'][str(h['pid'])]['start_ticks']);node=snap['drm'][h['node']]
  assert node['bdf']!='0000:47:00.0'
  if identity==tuple(native):assert node['bdf']=='0000:23:00.0';seen+=1
  else:assert (*identity,h['node']) in allowed
 if state and state['ActiveState']=='active':
  active+=1
  for k,v in ad['plan']['safe_properties'].items():assert state[k]==v
assert seen==0 and active>=1
assert all(x['observation_complete'] and x['first_error'] is None for x in mon['samples'])
assert not mon['single_term_attempted'] and mon['first_error'] is None
assert not any(term['after']['drm'][h['node']]['bdf']=='0000:23:00.0' for h in term['after']['inventory']['holders'])
raw=S/'result/samples.jsonl';digest(raw);rows=[json.loads(x) for x in raw.read_text().splitlines()];assert len(rows)==84
previous=0
for row,expect in zip(rows,manifest['schedule']):
 case=manifest['cases'][expect['case']]
 assert (row['warmup'],row['cycle'],row['layer'],row['order'])==(expect['warmup'],expect['cycle'],case['layer'],''.join(expect['order']))
 assert row['exact'] and row['A_sha256']==row['B_sha256']==row['expected_sha256']==case['fixtures']['expected']['sha256']
 assert row['label']==case['label']
 assert row['A_status_sha256']==row['B_status_sha256']==row['expected_status_sha256']==case['fixtures']['status']['sha256']
 assert case['fixtures']['expected']['bytes']==12800 and case['fixtures']['status']['bytes']==40
 first,second=row['order']
 assert previous<row[first+'_start_ns']<row[first+'_end_ns']<row[second+'_start_ns']<row[second+'_end_ns']
 previous=row[second+'_end_ns']
 assert row['A_end_ns']-row['A_start_ns']>0 and row['B_end_ns']-row['B_start_ns']>0
measured=[r for r in rows if not r['warmup']];assert len(measured)==72 and len(rows)-len(measured)==12
joint=collections.Counter((r['layer'],i%3,r['order']) for i,r in enumerate(measured));assert len(joint)==18 and set(joint.values())=={4}
def stats(v):return dict(count=len(v),mean=statistics.mean(v),median=statistics.median(v),minimum=min(v),maximum=max(v))
def aggregate(rs):
 a=[r['A_end_ns']-r['A_start_ns'] for r in rs];b=[r['B_end_ns']-r['B_start_ns'] for r in rs]
 return dict(pairs=len(rs),A_ns=stats(a),B_ns=stats(b),B_over_A_paired=stats([y/x for x,y in zip(a,b)]),B_over_A_sum=sum(b)/sum(a),A_over_B_sum=sum(a)/sum(b))
summary={'all':aggregate(measured),'by_case':{str(layer):{'all_orders':aggregate([r for r in measured if r['layer']==layer]),**{order:aggregate([r for r in measured if r['layer']==layer and r['order']==order]) for order in ('AB','BA')}} for layer in (0,22,46)},'by_order':{order:aggregate([r for r in measured if r['order']==order]) for order in ('AB','BA')}}
# Retain all small raw run files except regenerable native compiler caches (index those too).
raw_paths=sorted(p for p in S.rglob('*') if p.is_file())
assert len(raw_paths)<=2000 and sum(p.stat().st_size for p in raw_paths)<=64*1024**2
for p in raw_paths:digest(p)
for name in ('admission.json','terminal.json','monitor.json','result/result.json','result/samples.jsonl'):
 p=S/name;dst=D/('raw-'+name.replace('/','-'))
 with dst.open('xb') as f:f.write(p.read_bytes())
with (D/'artifact-index.jsonl.gz').open('xb') as out:
 with gzip.GzipFile(fileobj=out,mode='wb',mtime=0) as z:
  for item in sorted(index.values(),key=lambda x:x['path']):z.write((json.dumps(item,sort_keys=True)+'\n').encode())
receipt=dict(schema='ownrt.gsq.iq3xxs-block-micro-independent-device-review.v1',passed=False,audit_passed=True,native_kernel_result_passed=True,coordinator_passed=False,qualification_complete=False,qualification_limit=term['qualification_limit'],exact_output_and_status_pairs=84,exact_pairs=84,measured_pairs=72,excluded_warmup_pairs=12,kernel_submissions=168,native_identity=native,observed_target_bdf=None,intended_target_bdf='0000:23:00.0',observed_contact_samples=seen,active_unit_safe_property_samples=active,physical_drain=True,unchanged_vision_and_fault_baseline=True,cooperative_signals=0,safe_native_teardown=True,terminal_duration_seconds=term['duration'],binary_sha256=ad['binary_sha256'],native_build_sha256=ad['proof_sha256'],source_pins_rehashed=len(index),statistics=summary,source_sha256={str(Path(__file__).relative_to(R)):digest(__file__)},artifact_index_sha256=hashlib.sha256((D/'artifact-index.jsonl.gz').read_bytes()).hexdigest(),limitations=['One continuously owned device and three fixed saved real projection inputs; repeated isolated kernel event latency, not end-to-end model throughput or a speed record','Twelve warmup pairs excluded by preregistration; all72 measured pairs retained with no outlier filter; each case/position/order combination four observations','No original model/header/bundle reread by auditor: local copied sparse slices and saved fixtures rehashed; compiled reader authenticates these before Device construction; no full-tensor hash claim','Output and status equality is recorded full-byte native comparison plus exact per-arm SHA against rehashed saved baseline output/status fixtures; successful runtime did not emit separate full output blobs','Final unit is collected: final show fields are default not-found values, not original safe-property or exit-code evidence. One active sample proves safe properties; native teardown proves safe exit and passive metadata proves physical drain, but no sample observed the native target descriptor','Coordinator remains failed: no positive independent physical BDF ownership attestation. A later full Engine qualification can independently attest its own owner/device and exact results; it cannot retrospectively make this micro passed or prove where these timestamps were measured','No new device, service, kernel, inventory or model operation by auditor'])
with (D/'review.json').open('x') as f:json.dump(receipt,f,indent=2,ensure_ascii=False);f.write('\n')
print(json.dumps({'audit_passed':True,'passed':False,'receipt_sha256':hashlib.sha256((D/'review.json').read_bytes()).hexdigest(),'measured':72,'B_over_A':{k:v['all_orders']['B_over_A_sum'] for k,v in summary['by_case'].items()}}))
