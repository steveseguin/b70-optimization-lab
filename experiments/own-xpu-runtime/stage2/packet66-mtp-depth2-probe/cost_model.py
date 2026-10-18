#!/usr/bin/env python3
"""CPU analysis of retained routing and per-site receipts; no M=3 measurement."""
import gzip,hashlib,json,statistics as st
from collections import defaultdict
from pathlib import Path
from analyze import projection
P=Path(__file__).resolve().parent;S=P.parent;ROOT=P.parents[3]
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def packed(layer):return 2329600 if layer==2 else 1971200
def main():
 sources={}
 def bind(p):sources[str(p.relative_to(ROOT))]=sha(p)
 routes=S/'packet55-feasibility/route/evidence/cards23-a/routes.jsonl.gz';bind(routes)
 bind(S/'packet55-feasibility/analysis/locality.py')
 bind(S/'packet48-gemv/byte-census.json')
 route_receipt=routes.with_name('window.json');bind(route_receipt)
 assert json.loads(route_receipt.read_text())['passed']
 selected=defaultdict(dict);visits=0
 with gzip.open(routes,'rt') as f:
  for line in f:
   r=json.loads(line)
   if r['role']!='target' or r['phase']!='decode':continue
   assert len(set(r['ids']))==10
   selected[r['prompt_id']][(r['position'],r['layer'])]=set(r['ids']);visits+=1
 extra2=[[],[]];extra3=[[],[]];triples=0
 for rows in selected.values():
  positions=sorted({p for p,l in rows})
  complete={p for p in positions if all((p,l) in rows for l in range(48))}
  for p in positions:
   if not {p,p+1,p+2}<=complete:continue
   totals2=[0,0];totals3=[0,0]
   for l in range(48):
    a,b,c=(rows[(p+i,l)] for i in range(3));rank=int(l>=23)
    totals2[rank]+=len(b-a)*packed(l);totals3[rank]+=len(c-(a|b))*packed(l)
   for rank in (0,1):extra2[rank].append(totals2[rank]);extra3[rank].append(totals3[rank])
   triples+=1
 assert triples>0
 rows_by_rank=[[],[]];draft=[]
 base=S/'packet57-attribution/build/device-cards01-a/W57-attribution/run'
 for request in sorted((base/'repeat-1').iterdir()):
  if not request.is_dir():continue
  for rank in (0,1):
   site=request/f'rank{rank}/sites.jsonl';bind(site);groups=defaultdict(list);dg=defaultdict(float)
   for line in site.read_text().splitlines():
    r=json.loads(line)
    if r.get('schema')!='packet57.event.v1':continue
    label=r['label']
    if label.startswith('draft.'):
     # Copies may carry sentinel timings; only positive compute events enter.
     if 'transfer' not in label and r['end_ns']>r['start_ns']:dg[r['position']]+=r['device_ms']
    elif label.startswith('blk.'):
     groups[(r['position'],r['speculative'],int(label.split('.')[1]))].append(r)
   if rank==1:draft.extend(dg.values())
   for (pos,spec,layer),events in groups.items():
    # A cancelled prefix is never treated as a complete measured layer.
    if not any(r['label'].endswith('.ffn.combine') for r in events):continue
    labels={r['label'].split('.',2)[2] for r in events}
    expert=sum(r['device_ms'] for r in events if r['label'].endswith(('.expsgate','.expsdown')))
    glue=sum(r['device_ms'] for r in events if r['label'].endswith(('.gdn.conv','.gdn.recurrence','.gdn.gated')))
    assert expert>0
    rows_by_rank[rank].append(dict(layer=layer,ms=sum(r['device_ms'] for r in events),expert_ms=expert,expert_bytes=10*packed(layer),gdn_glue_ms=glue if 'gdn.recurrence' in labels else None))
 assert all(rows_by_rank) and draft
 params=[]
 for rank,rows in enumerate(rows_by_rank):
  bw=st.median(r['expert_bytes']/r['expert_ms']/1e6 for r in rows)
  glue=st.median(r['gdn_glue_ms'] for r in rows if r['gdn_glue_ms'] is not None)
  layers=range(23) if rank==0 else range(23,48)
  serial_bytes=sum(10*packed(l) for l in layers);gdn_layers=sum(l%4!=3 for l in layers)
  params.append(dict(rank=rank,complete_sampled_layers=len(rows),median_layer_ms=st.median(r['ms'] for r in rows),expert_effective_GB_s=bw,gdn_glue_ms_per_row_per_layer=glue,gdn_layers=gdn_layers,serial_expert_bytes_per_added_row=serial_bytes,
   observed_unique_increment_M1_to_M2_bytes_mean=st.mean(extra2[rank]),observed_unique_increment_M2_to_M3_bytes_mean=st.mean(extra3[rank]),
   serial_expert_ms=serial_bytes/(bw*1e6),serial_gdn_glue_ms=glue*gdn_layers,
   serial_proxy_ms=serial_bytes/(bw*1e6)+glue*gdn_layers,
   union_reuse_proxy_ms=st.mean(extra3[rank])/(bw*1e6)+glue*gdn_layers))
 verify=max(r['serial_proxy_ms'] for r in params);serial_verify=sum(r['serial_proxy_ms'] for r in params)
 wall=[]
 for trace in sorted((S/'packet57-attribution/build/device-cards01-a/W57-control/run/repeat-1').glob('*/rank1/draft-rows.jsonl')):
  bind(trace);wall.extend(r['wall_ms'] for r in map(json.loads,trace.read_text().splitlines()) if r.get('head'))
 assert len(wall)==1536
 draft_ms=st.median(wall)
 c1=1000*1.787/51.03
 result=dict(schema='packet66.cost-model.v1',diagnostic=True,device_executed=False,new_measurements=False,sources=sources,baseline_tok_s=51.03,a1=.787,baseline_identity='packet61x / cmvco3d6606u1le01941ek8hq (owner brief)',
  route_observed_visits=visits,route_complete_adjacent_triples=triples,route_prompt_count=len(selected),rank_models=params,
  measured_M1_to_M2_GDN_increment_ms=None,measured_a2=None,measured_extra_draft_ms=None,
  old_packet57_draft_compute_ms_median=st.median(draft),old_packet57_control_draft_wall_ms_median=draft_ms,
  serial_row_proxy=dict(verify_increment_ms=verify,verify_increment_rank_sum_ms=serial_verify,normalized_equivalent_depth1_cycle_ms=c1,projected_depth2_equivalent_cycle_excluding_extra_draft_ms=c1+verify,extra_draft_assumption_ms=draft_ms),
  projection_assumptions=['Current packet61x is one token per pipeline iteration; not a batched M=2 verifier. Normalize its 51.03 tok/s to an equivalent (1+a1)-token cycle before using the proposed depth2 formula.',
   'Added verify row proxy = max(rank extra expert payload / packet57 effective expert bandwidth + 18 serial GDN glue rows), assuming full rank overlap. Also show rank-sum cost without that overlap. Neither is a measured M1-to-M2 difference.',
   'GDN glue = conv + recurrence + gated; QKV/Z, attention output, HC, QSA, shared experts, rollback and scheduling increments are omitted. This is an optimistic partial cost, not a full M3 prediction.',
   'Serial expert kernels reread all 10 selected experts. Adjacent route union bytes describe a hypothetical fused kernel only; distinct routes are retained.',
   'Packet55 last observed routes at complete adjacent positions approximate successful serial rows; cancelled prefixes and its different prompt suite prevent claiming real M3 routing or measured DRAM bytes.',
   'Packet57 is an older instrumented line. It cannot measure packet61x M3 cost. No source supplies a matched M1-to-M2 GDN increment.',
   'No depth2 window has run. a2=0.60 +/-0.05 is only the owner example, never a measurement.'],
  illustrative_a2_table=projection(.6,draft_ms,verify),
  illustrative_a2_rank_sum_table=projection(.6,draft_ms,serial_verify),
  requested_measured_a2_table=[dict(case=k,a2=None,projected_tok_s=None,reason='coordinator screen pending') for k in ('measured - 0.05','measured','measured + 0.05')],
  a2_needed_for_10_percent=1.787*(1.1*(c1+draft_ms+verify)/c1-1)/.787,
  decision='Do not build the depth2 engine yet: the >=10% bar is unproven. Run the prepared probe, then use measured a2 and second-pass time with the explicitly conditional cost proxy.')
 (P/'cost-model.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:result[k] for k in ('rank_models','serial_row_proxy','illustrative_a2_table','a2_needed_for_10_percent','decision')},indent=2))
if __name__=='__main__':main()
