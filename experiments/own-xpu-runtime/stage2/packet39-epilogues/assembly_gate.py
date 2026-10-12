#!/usr/bin/env python3
"""Conservative static gate. Does not infer speed or dynamic instruction cost."""
import hashlib,json,re
from pathlib import Path
P=Path(__file__).resolve().parent
SHAPES=[('expert-act-iq2',22,2560,0,1,47,3),('expert-act-iq3',21,2560,0,1,1,3),('down-status',20,640,1,1,48,1),('hc-low-act',8,10240,2,4,97,1),('shared-up-act-q6',14,2560,3,4,47,1),('shared-up-act-q8',8,2560,3,1,1,1),('attention-combine',14,6144,4,4,48,1),('shared-down-combine',8,640,5,1,48,2),('gdn-qkv-conv-q6',14,2560,6,1,35,1),('gdn-qkv-conv-q8',8,2560,6,1,1,1),('expert-checks-iq2',22,2560,7,1,47,2),('expert-checks-iq3',21,2560,7,1,1,2)]
def flags(r):
 return sum(int(m[1]) for x in r['spill_metadata'] if (m:=re.search(r'flag (?:store|load) (\d+)',x)))
def data_spill(r):
 return sum(int(r.get('execution_env',{}).get(k,0)) for k in ['spill_size','scratch_size','private_size'])
def metrics(r):return dict(instructions=r['instructions'],messages=r['memory_messages'],simd=r['simd'],grf=r['grf'],flag_spills=flags(r),data_spill_or_scratch_bytes=data_spill(r),barriers=r['barriers'],slm=r['slm_messages'],payload_bytes=r['cross_thread_payload_extent_bytes'],asm=r['asm'],asm_sha256=r['asm_sha256'],kernel=r['kernel'])
def main():
 data=json.loads((P/'codegen.json').read_text());allrows=data['kernels'];classes={};table=[]
 def select(stage,t,k,e,f,split,wrapper=False):
  token=f'p39::{stage}Kernel<(iq3::Type){t}, {k}u, (p39::Kind){e}, {str(f).lower()}, {split}u>'
  found=[r for r in allrows if token in r['demangled'] and ('__pf_kernel_wrapper' in r['demangled'])==wrapper]
  if len(found)!=1:raise RuntimeError((token,wrapper,len(found)))
  return found[0]
 for name,t,k,e,split,groups,removed in SHAPES:
  stage='Rows4Gemv' if e in (2,3) else 'Gemv'
  base=select(stage,t,k,e,False,split);new=select(stage,t,k,e,True,split)
  pairs=[('Gemv',base,new)]
  if split==4 and e==4:
   pairs += [(stage,select('Finish',t,k,e,False,split,wrapper),select('Finish',t,k,e,True,split,wrapper)) for stage,wrapper in [('Finish',False),('Finish work-item wrapper',True)]]
  reasons=[]
  for stage,a,b in pairs:
   if not a['offline_binary_match']['selected'] or not b['offline_binary_match']['selected']:reasons.append(stage+' final ELF text identity unproven')
   if a['simd']!=b['simd']:reasons.append(stage+' SIMD width changed')
   if flags(b)>flags(a):reasons.append(stage+' adds flag-register spills')
   if data_spill(b)>data_spill(a):reasons.append(stage+' adds data spill/scratch')
   if b['barriers']>a['barriers'] or b['slm_messages']>a['slm_messages']:reasons.append(stage+' adds barriers/SLM')
   if b['cross_thread_payload_extent_bytes']>1024:reasons.append(stage+' payload exceeds1024')
  # These specialised GEMVs have the same loop structure; sort the lexical
  # envelopes to ignore compiler label numbering. Split finish wrappers are
  # work-item loops, not GEMV loops and are deliberately not compared here.
  before=sorted((x['instructions'],x['memory_messages']) for x in base['backward_branch_regions'])
  after=sorted((x['instructions'],x['memory_messages']) for x in new['backward_branch_regions'])
  if len(before)!=len(after):reasons.append('GEMV loop structure changed; manual qualification required')
  elif any(b[0]>a[0] or b[1]>a[1] for a,b in zip(before,after)):reasons.append('GEMV loop grows (includes scheduling instructions)')
  tail_base=pairs[1][1] if split==4 and e==4 else base;tail_new=pairs[1][2] if split==4 and e==4 else new
  delta_inst=tail_new['instructions']-tail_base['instructions'];delta_msg=tail_new['memory_messages']-tail_base['memory_messages']
  accepted=not reasons
  row=dict(accepted=accepted,reason='; '.join(reasons) if reasons else 'SIMD/loop/SLM/barrier/spill static gates pass; device identity and timing pending',groups_per_token=groups,launches_removed_per_group=removed,static_per_row_body_delta=dict(instructions=delta_inst,memory_messages=delta_msg,scope='Static full-program delta for the final row owner. Split1 SG32 computes one row; rows4 split4 uses four subgroups per row with one final row owner. Range finish SIMD32 covers up to32 independent rows. Alternate math branches included; not a dynamic executed-path count.',rows_per_simd_dispatch=32 if split==4 and e==4 else 1,static_instruction_delta_per_row_amortized=delta_inst/(32 if split==4 and e==4 else 1),static_message_delta_per_row_amortized=delta_msg/(32 if split==4 and e==4 else 1)),gemv_loops_before=before,gemv_loops_after=after,variants=[dict(stage=stage,unfused=metrics(a),fused=metrics(b)) for stage,a,b in pairs])
  classes[name]=row;table.append(f'| {name} | {base["instructions"]}/{base["memory_messages"]} | {new["instructions"]}/{new["memory_messages"]} | {delta_inst:+d}/{delta_msg:+d} | {"admit to G4" if accepted else "reject selection"} |')
 result=dict(schema='packet39.assembly-review.v1',device_executed=False,arithmetic_qualified=False,codegen_sha256=hashlib.sha256((P/'codegen.json').read_bytes()).hexdigest(),classes=classes,eligible_launches_removed_per_token=sum(x['groups_per_token']*x['launches_removed_per_group'] for x in classes.values() if x['accepted']))
 (P/'assembly-review.json').write_text(json.dumps(result,indent=2)+'\n')
 (P/'assembly-table.md').write_text('# Offline assembly pairs\n\nStatic instruction/message counts. The delta is in the row epilogue owner: inline rows4 finish for HC/shared split4, separate finish for attention split4. One split1 SG32 computes one row; rows4 split4 uses four subgroups per row with one final row owner. A separate finish SIMD32 dispatch covers up to32 independent rows. JSON also gives static delta/row amortized by that geometry, not dynamic counts. It includes alternate finite/exceptional branches and is not a dynamic per-row instruction count or a speed prediction. Every table row has final ELF-text-matched assembly, SIMD, payload and spill metadata in [assembly-review.json](assembly-review.json); work-item wrappers are recorded separately there.\n\n| Class | Unfused GEMV inst/msg | Fused GEMV inst/msg | Row-tail delta inst/msg | Gate |\n| --- | ---: | ---: | ---: | --- |\n'+'\n'.join(table)+'\n')
 print('assembly-admitted launches/token',result['eligible_launches_removed_per_token'])
if __name__=='__main__':main()
