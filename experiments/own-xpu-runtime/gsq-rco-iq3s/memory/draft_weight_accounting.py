#!/usr/bin/env python3
"""Source/manifest-only draft device-weight accounting; never reads tensors."""
from pathlib import Path
import hashlib,json
P=Path(__file__).resolve().parent;ROOT=P.parents[3];OLD=ROOT/'experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 source=(OLD/'mtp.hpp').read_text()
 for fragment in ('cols+cols/16*4','gain?4:2','float f=1.f+iq3::bits_float(uint32_t(b)<<16)','full.begin()+rows*cols*2','full.end()-rows*cols*2','weights.count(name)','store->reads.size()==3101'):
  assert fragment in source,fragment
 selection=json.loads((OLD/'selection.json').read_text());assert selection['draft']['head_format']=='production' and selection['draft']['head_prefix']=='p114-80128'
 rows={}
 for line in (OLD/'mtp-manifest.tsv').read_text().splitlines():
  r=line.split();assert len(r)==13 and r[0] not in rows
  rows[r[0]]={'name':r[0],'source_bytes':int(r[3]),'dtype':r[4],'rows':int(r[5]),'columns':int(r[6])}
 assert len(rows)==3101
 def gain(n):return ('hc_norm.weight' in n or n.endswith(('q_norm.weight','k_norm.weight','q_layernorm.weight','k_layernorm.weight')) or 'pre_fc_norm_' in n)
 groups={kind:[] for kind in ('gate','up','down')};dense=[];scales=[]
 for n,r in rows.items():
  if '.experts.' in n:
   if n.endswith('.weight_scale_inv'):scales.append(r);continue
   assert n.endswith('.weight') and r['dtype']=='F8_E4M3';kind=n.split('.')[-2].removesuffix('_proj');assert kind in groups
   assert r['source_bytes']==r['rows']*r['columns'] and r['columns']%128==0 and r['rows']%128==0
   peer=rows[n.removesuffix('.weight')+'.weight_scale_inv'];assert peer['dtype']=='BF16' and peer['source_bytes']==(r['rows']//128)*(r['columns']//128)*2
   r['device_bytes']=r['rows']*(r['columns']+r['columns']//16*4);groups[kind].append(r)
  else:
   assert r['dtype']=='BF16' and r['source_bytes']==r['rows']*r['columns']*2
   r['gain_widened_with_plus_one']=gain(n);r['device_bytes']=r['source_bytes']*(2 if gain(n) else 1);dense.append(r)
 assert len(scales)==1536 and len(dense)==29 and all(len(v)==512 for v in groups.values())
 index=rows['mtp.layers.0.self_attn.indexer.index_qk_proj.weight'];assert (index['rows'],index['columns'])==(640,2560)
 index_split={'source_bytes':index['source_bytes'],'q_rows':512,'k_rows':128,'q_device_bytes':512*2560*2,'k_device_bytes':128*2560*2,'single_source_counted_once':True}
 assert index_split['q_device_bytes']+index_split['k_device_bytes']==index['device_bytes']
 expert=sum(r['device_bytes'] for v in groups.values() for r in v);other=sum(r['device_bytes'] for r in dense);base=expert+other
 result={'schema':'gsq.draft-weight-planning.v1','source_only':True,'model_payload_reads':0,'device_executed':False,'fit_qualified':False,'sources':{str(f.relative_to(ROOT)):sha(f) for f in (OLD/'mtp.hpp',OLD/'mtp-manifest.tsv',OLD/'selection.json',OLD/'p83_head.hpp',OLD.parent/'packet10-kopt5/expanded.hpp',P/'draft_weight_accounting.py')},'manifest_tensors':len(rows),'expert_weight_tensors':1536,'source_fp8_expert_bytes':sum(r['source_bytes'] for v in groups.values() for r in v),'source_fp8_scale_bytes':sum(r['source_bytes'] for r in scales),'device_expert_int8_g16_bytes':expert,'expert_groups':{k:{'experts':len(v),'rows':v[0]['rows'],'columns':v[0]['columns'],'bytes':sum(r['device_bytes'] for r in v)} for k,v in groups.items()},'dense_and_gain_source_bytes':sum(r['source_bytes'] for r in dense),'dense_and_gain_device_bytes':other,'gain_source_bytes':sum(r['source_bytes'] for r in dense if r['gain_widened_with_plus_one']),'gain_device_bytes':sum(r['device_bytes'] for r in dense if r['gain_widened_with_plus_one']),'nonexpert_tensors':dense,'index_projection_split':index_split,'base_draft_device_weight_bytes':base,'base_weight_allocations':33,'head':{'target_q6_expanded_row_bytes':3380,'required_new_policy':'full248320 draft vocabulary required; historical prefix excluded','rows':248320,'extra_bytes':248320*3380,'rank0_no_local_head_weight_total':base+248320*3380,'historical_excluded_prefix_rows':80128,'historical_excluded_prefix_bytes':80128*3380,'rank1_already_expanded_target_head_weight_total':base,'packed_or_missing_local_head_requires_extra_full_head':True,'shared_target_head_counted_by_target_only':True},'excluded':['all draft mutable buffers/KV/scratch/control/head workspaces','backend/runtime allocations and compilation caches','allocator alignment/fragmentation','temporary host FP8 requantization buffers','target weights and state','actual available device memory or measured peak'],'rank_placement':'Rank0 costs an extra839321600-byte full head if it lacks local expanded head; prefer it only when target rank0 headroom exceeds rank1 by more than that overhead. It can avoid concentrating a3.32695GB draft on the rank carrying the larger target/head placement. Reverse hidden handoff and existing draft-rank admission must also be preserved.'}
 out=P/'draft-weight-accounting.json';out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ('base_draft_device_weight_bytes','device_expert_int8_g16_bytes','dense_and_gain_device_bytes','head')}))
if __name__=='__main__':main()
