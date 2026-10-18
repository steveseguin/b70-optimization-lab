"""Recompute one-card counts from retained original-byte receipts, no GPU."""
import gzip,json,statistics,struct,hashlib,resource
from build_engine import P,ROOT,sha,limits
OLD=P.parent/'packet58n-onecard-loo'
def main():
 limits();pins=json.loads((OLD/'analysis-inputs.json').read_text());sources={}
 def raw(name):
  entry=pins[name];path=OLD/entry['archive'];data=gzip.decompress(path.read_bytes());assert hashlib.sha256(data).hexdigest()==entry['sha256'];sources[str(path.relative_to(ROOT))]=sha(path);return data
 prefix='experiments/own-xpu-runtime/stage2/packet58k-onecard-screen/evidence/card0-screen-b/production-before/WSCREEN/'
 summary=json.loads(raw(prefix+'summary.json'));cache=[json.loads(l) for l in raw(prefix+'run/run/cache.jsonl').splitlines()];at=0;chosen=[]
 for request in summary['requests']:
  base=prefix+'run/run/'+request['prompt_id']+'/'
  pre=[json.loads(l) for l in raw(base+'prefill-timings.jsonl').splitlines()];gen=[json.loads(l) for l in raw(base+'timings.jsonl').splitlines()]
  assert len(gen)==128
  for t in pre+gen:
   c=cache[at];at+=1;assert c['epoch']==at;assert t['copy_counts'][0]['host_to_device']==3*c['fills']+147
   assert t['gemv_device_ms']==t['non_gemv_device_ms']==0 and t['enqueue_family_ms'] is None
   assert (c['fill_bytes']-c['fills']*1971200)%358400==0
   if t['kind']!='prefill_token' and 2<=t['generated_index']<=100:chosen.append((t,c))
 assert at==len(cache)==2386 and len(chosen)==1188
 mean=lambda vals:statistics.mean(vals)
 count=mean(c['fills'] for t,c in chosen);payload=mean(c['fill_bytes'] for t,c in chosen)
 accounting=dict(charged_positions=1188,misses_per_token=count,logical_missed_bytes_per_token=payload,logical_down_missed_bytes_per_token=count*921600,expert_hit_rate=1-count/480,byte_hit_rate=1-payload/949760000,mean_token_wall_ms=mean(t['wall_ms'] for t,c in chosen),mean_cache_planning_fills_publication_ms=mean(c['wall_ms'] for t,c in chosen),mean_host_preparation_ms=mean(t['prepare_ms'] for t,c in chosen),mean_enqueue_loop_ms=mean(t['enqueue_loop_ms'] for t,c in chosen),mean_host_wait_ms=mean(t['wait_ms'] for t,c in chosen),zero_copy_read_ms=None,device_compute_ms=None,physical_pcie_bytes=None,timers_overlap=True,actual_pinned_alignment=None)
 cases=[struct.unpack_from('<33I',(P/'evidence/cases.bin').read_bytes(),i*132) for i in range(384)]
 separate=compact=aligned=tile=0;hist={}
 for token,layer,mask,*_ in cases:
  n=mask.bit_count();e=2329600 if layer==2 else 1971200
  up=lambda n:(n+65535)//65536*65536
  separate+=n*e;compact+=n*up(e+64);aligned+=n*up(e);tile+=n*921600;hist[n]=hist.get(n,0)+1
 pinned=separate+compact+aligned+tile+4*65536+120
 # Exact native explicit allocations plus rounded allowance for context/driver.
 device=10*2329600+10*921600+3*512*16+5120+3*12800+51200+240+132+512*1024**2+65536*4
 memory=dict(pinned_bytes=pinned,device_explicit_bytes=device,pageable_case_bytes=10*2329600+10*921600,process_budget_bytes=8*1024**3,host_reserve_bytes=8*1024**3,admission_bytes=16*1024**3,driver_runtime_and_transient_margin_bytes=8*1024**3-pinned-device-40_000_000,miss_count_histogram=hist)
 assert pinned<7*1024**3 and memory['driver_runtime_and_transient_margin_bytes']>500_000_000
 row=dict(schema='packet125.accounting.v1',passed=True,device_executed=False,onecard=accounting,micro_memory=memory,sources=sources,analysis_inputs_sha256=sha(OLD/'analysis-inputs.json'))
 (P/'evidence/accounting.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(dict(onecard=accounting,memory=memory),indent=2))
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,)*2);main()
