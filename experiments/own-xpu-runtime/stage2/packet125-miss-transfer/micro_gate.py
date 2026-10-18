"""Exact-byte completeness independent of speed; two owners required to qualify."""
import json,math,struct
from pathlib import Path
from build_engine import P,sha
MODES=('production','tile16','bcs_serial3','bcs_inflight3','bcs_contiguous','bcs_aligned','bcs_pipeline3')
def prerequisites(packet=P):
 from route_inputs import read_inputs
 read_inputs()
 row=json.loads((packet/'evidence/cpu-tests.json').read_text());assert row['passed'] is True
 for name,digest in row['sources'].items():assert sha(packet/name)==digest,name
 byte=json.loads((packet/'evidence/cpu-bytes.json').read_text());assert byte['passed'] is True
 assert byte['source_sha256']==sha(packet/'cpu_bytes.cpp') and byte['common_sha256']==sha(packet/'micro_common.hpp')
 assert all(r['passed'] and r['fresh_processes']==2 and r['result']['checks']==24 for r in byte['records'])
 assert json.loads((packet/'evidence/drain-check.json').read_text())['passed'] is True
 return {name:sha(packet/name) for name in ('evidence/route-inputs.json','evidence/cases.bin','evidence/cpu-tests.json','preregistration.json','evidence/cpu-bytes.json','evidence/accounting.json')}
def analyze(rows,owner=None):
 assert rows[-1]==dict(kind='summary',passed=True,drained=True,cases=384,samples=2688,model_loaded=False,diagnostic_only=True),'complete drained summary'
 assert sum(r.get('kind')=='summary' for r in rows)==1
 devices=[r for r in rows if r['kind']=='device'];allocs=[r for r in rows if r['kind']=='allocation'];assert len(devices)==len(allocs)==1
 assert devices[0]['copy_only_ordinal']>=0 and devices[0]['copy_queues_available']>0
 assert allocs[0]['pinned_bytes']<7*1024**3 and allocs[0]['scrub_bytes']==512*1024**2
 assert allocs[0]['aligned_mod64k']==0 and allocs[0]['compact_mod64k']==64
 cases=[struct.unpack_from('<33I',(P/'evidence/cases.bin').read_bytes(),i*132) for i in range(384)]
 samples={};order=[]
 for r in rows:
  if r['kind']!='sample':continue
  key=(r['view'],r['case']);assert key not in samples and key[0] in MODES and 0<=key[1]<384
  case=cases[key[1]];token,layer,mask=case[:3];n=mask.bit_count();size=(2329600 if layer==2 else 1971200)*n
  assert (r['token'],r['layer'],r['mask'],r['misses'],r['miss_bytes'])==(token,layer,mask,n,size)
  assert r['all_bytes_exact'] is True and r['diagnostic_only'] is True
  for k in ('wall_ns','route_readback_ns','serial_copy_wait_ns','copy_event_sum_ns','gate_ns','activation_ns','down_ns'):
   assert type(r[k]) in (float,int) and math.isfinite(r[k]) and r[k]>=0
  assert r['wall_ns']>0 and r['gate_ns']>0 and r['down_ns']>0
  copy=key[0].startswith('bcs_');assert r['delivered_bytes_checked']==(size if copy else 0)
  expected_copies=n*(1 if key[0] in ('bcs_contiguous','bcs_aligned') else 3) if copy else 0
  assert r['copy_events']==expected_copies
  samples[key]=r;order.append(key)
 assert len(samples)==384*len(MODES)
 if owner is not None:
  assert owner in (1,2)
  assert order==[(m,i) for i in range(384) for m in (MODES if owner==1 else MODES[::-1])], 'fresh process order changed'
 result={}
 for group,ids in [('all',list(range(384))),('post_initial',[i for i,c in enumerate(cases) if c[0]%64!=0])]:
  useful=sum(cases[i][2].bit_count()*(2329600 if cases[i][1]==2 else 1971200) for i in ids)
  base=sum(samples['production',i]['wall_ns'] for i in ids)
  result[group]={m:dict(useful_bytes=useful,wall_ns=sum(samples[m,i]['wall_ns'] for i in ids),useful_gb_s=useful/sum(samples[m,i]['wall_ns'] for i in ids),ratio=base/sum(samples[m,i]['wall_ns'] for i in ids)) for m in MODES}
 winners=[m for m in MODES[1:] if all(result[g][m]['ratio']>=1.5 for g in result)]
 return dict(passed=True,diagnostic_only=True,speed_qualified=winners,groups=result)
def evaluate(packet=P,repeat=None):
 reports=[];bindings=[];processes=set()
 for owner in (1,2):
  out=packet/f'evidence/micro-B-{owner}'
  if not (out/'window.json').exists():continue
  w=json.loads((out/'window.json').read_text());assert all(w.get(k) is True for k in ('passed','device_executed','drained','lease_released'))
  assert not w.get('stop_reasons') and not w.get('child_still_running')
  assert w['repeat']==owner and w['model_lifetimes']==0 and w['physical_cards']==[2]
  process=(w['pid'],w['process_start_ticks']);assert process not in processes;processes.add(process)
  assert w['identity']['build_receipt_sha256']==sha(packet/'evidence/microbench-build.json')
  assert w['samples_sha256']==sha(out/'samples.jsonl') and w['identity']['binary_sha256']==sha(packet/'build/microbench')
  assert w['prerequisite_bindings']==prerequisites(packet)
  reports.append(analyze([json.loads(x) for x in (out/'samples.jsonl').read_text().splitlines()],owner=owner));bindings.append(dict(owner=owner,window_sha256=sha(out/'window.json'),samples_sha256=w['samples_sha256']))
 winners=sorted(set(reports[0]['speed_qualified'])&set(reports[1]['speed_qualified'])) if len(reports)==2 else []
 row=dict(schema='packet125.qualification.v1',ready=len(reports)==2,passed=bool(winners),device_measurements=len(reports),qualified_candidates=winners,reports=reports,bindings=bindings,engine_integration_allowed=bool(winners),no_model_speed_claim=True)
 (packet/'evidence/qualification.json').write_text(json.dumps(row,indent=2)+'\n');return row
if __name__=='__main__':print(json.dumps(evaluate(),indent=2))
