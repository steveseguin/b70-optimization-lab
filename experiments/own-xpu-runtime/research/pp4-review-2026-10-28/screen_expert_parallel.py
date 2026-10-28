#!/usr/bin/env python3
"""CPU-only archived-route / allocation screen; no device access."""
import collections,hashlib,json,math,statistics,struct
from pathlib import Path
ROOT=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime')
OUT=Path(__file__).parent
route=Path('/dev/shm/ownrt-lab-experts/routes-4096.bin');raw=route.read_bytes();o=0;seq=collections.defaultdict(list)
while o<len(raw):
 n,=struct.unpack_from('<I',raw,o);o+=4;label=raw[o:o+n].decode();o+=n;m,s=struct.unpack_from('<II',raw,o);o+=8
 vals=list(struct.iter_unpack('<III',raw[o:o+12*s]));o+=12*s
 if label.endswith('expsdown'):seq[label].extend(vals)
samples=[]
for label,rows in sorted(seq.items()):
 layer=int(label.split('.')[1]);src=min(2,layer//16)
 for start in range(0,len(rows),2560):
  rt=rows[start:start+2560]
  if len(rt)!=2560:continue
  hist=collections.Counter(x[0]for x in rt);slots=[0]*3;tiles=[0]*3
  for e,n in hist.items():slots[e%3]+=n;tiles[e%3]+=(n+3)//4
  remote=sum(e%3!=src for e,_,_ in rt)
  inputpairs=set((t//10,e%3)for t,(e,_,_)in enumerate(rt)if e%3!=src)
  samples.append(dict(layer=layer,start_token=start//10,distinct=len(hist),slots=slots,tiles=tiles,tile_critical_fraction=max(tiles)/sum(tiles),remote_slots=remote,dedup_remote_inputs=len(inputpairs),remote_bytes_dedup=len(inputpairs)*2560*4+remote*2560*4,remote_bytes_slot=remote*2560*4*2))
base=Path('/dev/shm/sc117-pp4-262k-lan/control-_uc2cmys/output')
weights=[]
for i in range(4):
 p=json.loads((base/f'stage{i}/native/plan.json').read_text())
 weights.extend(x for x in p['tensor_owners']if x['component']=='routed_experts')
bylayer=collections.Counter()
for x in weights:bylayer[int(x['name'].split('.')[1])]+=x['stored_bytes']
time=json.loads((base/'requests/request-000002/driver-result.json').read_text())['prefill_timing']
prof=json.loads((ROOT/'research/rank0-prefill-c27/analysis.json').read_text());f=prof['largest_costs_ms']['routed_experts_combined']/prof['profile_target_prefill_ms'];r=statistics.mean(s['tile_critical_fraction']for s in samples)
work=time['target_work_wall_s'];span=time['target_only_phase_wall_s']+time['mixed_phase_wall_s'];rows=121852
bytes_per_layer_per_position=statistics.mean(s['remote_bytes_dedup']/256 for s in samples);traffic=bytes_per_layer_per_position*48*rows
output={'schema':'ownrt.expert-parallel-cpu-screen.v1','verdict':'pure-layer-serial-EP-not-supported-by-current-cost-share;hybrid-remains-unmeasured','measured_inputs':{'route_dump':str(route),'route_sha256':hashlib.sha256(raw).hexdigest(),'route_layers':sorted(int(x.split('.')[1])for x in seq),'route_tokens_per_layer':4096,'samples_256rows':len(samples),'target_timing':time,'old_profile':str(ROOT/'research/rank0-prefill-c27/analysis.json'),'routed_weight_bytes_total':sum(bylayer.values()),'routed_weight_bytes_per_layer':dict(sorted(bylayer.items()))},'route_replay_model':{'owners':3,'assignment':'expert_id modulo3, static; attention source layer//16 capped2','T':4,'distinct_mean':statistics.mean(s['distinct']for s in samples),'critical_tile_fraction_mean':r,'critical_tile_fraction_max':max(s['tile_critical_fraction']for s in samples),'critical_slot_fraction_mean':statistics.mean(max(s['slots'])/2560 for s in samples),'bytes_per_layer_position_dedup_mean':bytes_per_layer_per_position,'estimated_121852rows_48layers_remote_bytes':traffic,'traffic_definition':'remote input dedup per(token,owner) plus one full F32down output perremote top10slot, no partialsum reassociation; excludes metadata and staging secondleg','samples':samples},'estimated_critical_path':{'expert_fraction_from_other4096rank_profile':f,'warning':'profile fraction from different context/rank; no long121K perop profile, NOT measured EP speed','pure_EP3_target_seconds_no_comm':work*((1-f)+f*r),'current_PP4_target_active_phase_seconds':span,'current_PP4_total_wall_seconds':time['total_wall_s'],'expert_fraction_needed_to_beat_current_target_span_no_comm':(1-span/work)/(1-r),'traffic_seconds_sensitivity_effective_aggregate_GBps':{str(b):traffic/(b*1e9)for b in [4,8,16,32,64]},'sum_routed_weights_per_owner_bytes_ideal':sum(bylayer.values())/3,'weight_limit_note':'expert weights alone, before dense/KV/workspace/provider; actual ownership uneven / model allocations gate required'},'next_gate':'CPU combined EP+pipeline discrete-event schedule with per-op121K timings, exact owner allocations and existing transfer evidence; do not build pureEPengine from shortprofile alone','discovery_open':True}
(OUT/'expert-parallel-screen.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps({k:v for k,v in output['estimated_critical_path'].items()},indent=2));print('traffic GB',traffic/1e9,'r',r,'weights GB',sum(bylayer.values())/1e9)
