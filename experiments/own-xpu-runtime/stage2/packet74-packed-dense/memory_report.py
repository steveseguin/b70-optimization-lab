"""Exact allocation-byte deltas from retained headers, no model payload or GPU."""
from pathlib import Path
import json,hashlib
P=Path(__file__).resolve().parent;ROOT=P.parents[3];SOURCE=P.parent/'packet72-occupancy'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
headers=json.loads((SOURCE/'header-census.json').read_text())['tensors']
rows=json.loads((SOURCE/'all-layer-bytes.json').read_text())['rows']
sites={'gdn.qkv','gdn.z','qsa.qgate','qsa.k','qsa.v','attention','shexpdown'}
tensors={}
for r in rows:
 if r['site'] in sites:
  for t in r['tensors']:
   if t['type'] in ('Q6_K','Q8_0'):tensors[t['name']]=(r['rank'],r['site'])
for n in ('blk.1.ple_key.weight','blk.1.ple_value.weight'):tensors[n]=(0,'ple.key' if 'key' in n else 'ple.value')
tensors['output.weight']=(1,'logits')
entries=[]
for name,(rank,site) in sorted(tensors.items()):
 t=headers[name];n,k=t['shape'];typ=t['type'];expanded_rb=k*338//256 if typ=='Q6_K' else k*38//32;packed_rb=k*210//256 if typ=='Q6_K' else k*34//32
 fetched=k*320//256 if typ=='Q6_K' else k*36//32
 entries.append(dict(name=name,rank=rank,site=site,type=typ,rows=n,columns=k,expanded_resident_bytes=n*expanded_rb,packed_resident_bytes=n*packed_rb,expanded_weight_read_bytes=n*fetched,packed_weight_read_bytes=n*packed_rb,saving_bytes=n*(expanded_rb-packed_rb)))
prefix=91392*3380
views={}
for name in ('production','head-packed','dense-packed','combined'):
 selected=[r for r in entries if (name in ('head-packed','combined') if r['site']=='logits' else name in ('dense-packed','combined'))]
 saved=[sum(r['saving_bytes'] for r in selected if r['rank']==rank) for rank in (0,1)];extra=prefix if name in ('head-packed','combined') else 0;saved[1]-=extra
 views[name]=dict(selected_tensors=len(selected),target_weight_saving_bytes_by_rank=[sum(r['saving_bytes'] for r in selected if r['rank']==rank) for rank in (0,1)],expanded_draft_prefix_bytes=extra,net_vram_saving_bytes_by_rank=saved,measured_vram=None)
report=dict(schema='packet74.packed-residency.v1',device_executed=False,views=views,tensors=entries,sources={str((SOURCE/n).relative_to(ROOT)):sha(SOURCE/n) for n in ('header-census.json','all-layer-bytes.json')},scope='Q6/Q8 selected projections only; fused HC and small FFN unchanged; original memory admission retained conservatively',actual_peak_vram='pending coordinator device receipts')
(P/'VRAM.json').write_text(json.dumps(report,indent=2)+'\n')
lines=['# Packet74 exact allocation deltas','', 'These are allocation calculations from pinned tensor headers, not measured GPU memory. The inherited memory admission remains conservative. Draft keeps its expanded91392-row prefix, original kernel, and original outputs. It does not keep a second expanded full head.','', '| View | Rank0 fewer bytes | Rank1 fewer bytes | Extra draft prefix bytes |','| --- | ---: | ---: | ---: |']
for name,v in views.items():lines.append(f"| {name} | {v['net_vram_saving_bytes_by_rank'][0]:,} | {v['net_vram_saving_bytes_by_rank'][1]:,} | {v['expanded_draft_prefix_bytes']:,} |")
lines+=['', 'Q6 head:839,321,600 expanded resident bytes become521,472,000 packed bytes plus308,904,960 draft-prefix bytes: net8,944,640 saved. Target traffic falls794,624,000→521,472,000 bytes (34.375%). QKV Q6:34,611,200 resident→21,504,000; useful reads32,768,000→21,504,000. Q8 saves10.526% resident and5.556% fetched bytes. All block and row bytes are exact; no padding or full-size decode scratch is allocated.','', 'The dense view retains fused HC and small-FFN tuples and their expanded bytes. Its router is raw F32, so no router weight format is silently changed. Routed experts and official BF16/INT8 draft tensors are unchanged. PLE key/value are included on rank0.','', '[Per-tensor identity and totals](VRAM.json). Actual peak and speed remain unmeasured.']
(P/'VRAM.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(views,indent=2))
