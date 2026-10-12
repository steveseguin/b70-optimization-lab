#!/usr/bin/env python3
import json,re
from pathlib import Path
P=Path(__file__).resolve().parent

def memory_buffers(kernel):
 records=[]
 for chunk in re.split(r'^      - ', '\n'.join(kernel.get('per_thread_memory_buffers_metadata',[])),flags=re.M)[1:]:
  fields=dict(re.findall(r'(\w+):\s+([^\n]+)',chunk))
  fields['size']=int(fields.get('size','0'))
  fields['is_simt_thread']=fields.get('is_simt_thread','false')=='true'
  records.append(fields)
 return records

def scratch_per_hw_thread(kernel):
 return sum(b['size']*(kernel['simd'] if b['is_simt_thread'] else 1) for b in memory_buffers(kernel) if b.get('type')=='scratch')

def main():
 data=json.loads((P/'codegen.json').read_text());ks=data['kernels'];rows=[]
 def add(label,predicate,note='',dynamic=None):
  found=[k for k in ks if predicate(k['demangled'])]
  if not found:raise ValueError('missing '+label)
  rows.append(dict(label=label,kernels=[k['kernel'] for k in found],asm_sha256=[k['asm_sha256'] for k in found],
   simd=sorted({k['simd'] for k in found}),static_instructions=sum(k['instructions'] for k in found),static_messages=sum(k['memory_messages'] for k in found),
   alu64=sum(k['alu64'] for k in found),conversions=sum(k['conversions_to_float'] for k in found),
   slm_messages=sum(k['slm_messages'] for k in found),barriers=sum(k['barriers'] for k in found),
   calls=sum(k['calls'] for k in found),payload_bytes=max(k['cross_thread_payload_extent_bytes'] for k in found),
   spill_bytes=max([int(v) for k in found for v in re.findall(r'//.spill size (\d+)','\n'.join(k['spill_metadata']))] or [0]),
   scratch_bytes_per_hw_thread=max(scratch_per_hw_thread(k) for k in found),
   private_size_bytes_per_hw_thread=max(int(k['execution_env'].get('private_size','0')) for k in found),
   memory_buffer_metadata=[dict(kernel=k['kernel'],buffers=memory_buffers(k)) for k in found],
   memory_size_note='Spill is unrounded GRF spill requirement; scratch is allocated bytes per hardware SIMD thread. private_size is execution_env private bytes per hardware SIMD thread; a global is_simt_thread allocation is per lane and remains separately recorded. These quantities are not additive. Table aggregates use maximum across member kernels.',
   prefix_instructions=sum(k['prologue_instructions_before_first_branch'] for k in found),
   loop_backedges=sum(len(k['backward_branch_regions']) for k in found),dynamic=dynamic,
   note=note or 'Static counts include alternate and exceptional paths. SIMD is the dispatch width; memory opcode kinds are in referenced kernels.',
   per_weight_and_work_item='Unknown dynamic count unless dynamic field supplies a witnessed finite path; not zero. Memory kinds and widths in referenced kernels.',
   conversion_note='Counter detects MOVs from integer/half-typed operands to float, not all bit-expansion operations. BF16 and IQ-half lowering require path-specific inspection; expert-down evidence is in review-assembly.json.',
   subgroup_note='SIMD16 instruction halves do not imply split dispatch. SLM/barriers are static counts; exact reduction/communication lowering requires path-specific inspection. The adjacent1/2/4/8/16 tree is independently witnessed for expert-down only.'))
 def contains(fragment):return lambda d:fragment in d and 'RoundedRangeKernel' not in d
 add('down R5 IQ4',contains('iq3::kopt4::(anonymous namespace)::Projection::run<(iq3::Type)20>'),dynamic=dict(weights_per_lane=8,instructions=475,messages=25,source='review-assembly.json'))
 for name,v in [('p25.private_decode',3),('p27.packed64',10),('p25.wide8',8),('p27.fp32_input',9)]:add('down '+name,contains(f'packet26::p25bridge::Kernel<(iq3::Type)20, (p25::C){v}>'))
 add('down p28.shared.wg32',contains('p28::Kernel<(iq3::Type)20, 640u, 1u, 1u, true, false>'))
 add('down p29.wg32',contains('p29::Kernel<1u>'),dynamic=dict(weights_per_lane=8,instructions=169,messages=15,source='review-assembly.json'))
 add('down p29.rows4',contains('p29::Kernel<4u>'))
 for t,fmt in [(22,'IQ2'),(21,'IQ3')]:
  add('gate R5 '+fmt,contains(f'iq3::kopt4::(anonymous namespace)::Projection::run<(iq3::Type){t}>'))
  for name,sh,pair in [('private','false','false'),('shared','true','false'),('paired','false','true')]:add('gate p28.'+name+'.wg32 '+fmt,contains(f'p28::Kernel<(iq3::Type){t}, 2560u, 1u, 1u, {sh}, {pair}>'))
  for name,v in [('half_table',5),('paired_input',4)]:add('gate p25.'+name+' '+fmt,contains(f'packet26::p25bridge::Kernel<(iq3::Type){t}, (p25::C){v}>'),'Main kernel only; preparation module retained separately in codegen.json; event counts enter fitted model.')
 for t,fmt in [(14,'Q6'),(8,'Q8')]:
  add('dense R5 SG32/split4 '+fmt,contains(f'iq3::expanded::(anonymous namespace)::Multiply::run<(iq3::Type){t}>'),'One shipped kernel uses runtime split; static sum contains both paths. Split4 retains SLM/tree and barrier.')
  for name,rpg in [('wg32',1),('rows4',4)]:
   for split in (1,4):add(f'dense p28.{name} {fmt} split{split}',contains(f'p28::Kernel<(iq3::Type){t}, 2560u, {split}u, {rpg}u, false, false>'))
  add('dense p25.scale8 '+fmt,contains(f'packet26::p25bridge::Kernel<(iq3::Type){t}, (p25::C)7>'))
 add('route specialised (5 stages)',lambda d:'packet18::(anonymous namespace)::SimpleNew<(integrated::Op)8,' in d and ', 512, 10>' in d and 'RoundedRangeKernel' not in d,'Source and event receipts show FIVE stages, correcting four-stage premise. Rounded-range alternate entries retained in full census.')
 add('route round2 (3 stages)',lambda d:'round2::Simple<(integrated::Op)8,' in d and ', 512, 10>' in d,'Three stages; BF16 and FP32 input instantiations summed here; examine kernel list per bound input.')
 add('QSA packet18 / activation / GDN native fixture',contains('ng::Kernel::submit'),'One runtime-op kernel, not three tiny kernels. Static aggregate cannot be equated with any one selected path or launch floor.')
 add('QSA/GDN packet18 production adapter',contains('packet18::(anonymous namespace)::Glue::submit'),'Generic runtime switch. No path-specific per-weight count inferred from complete function.')
 for code,name in [(12,'score'),(13,'softmax'),(14,'value'),(1,'GDN recurrence')]:add('round2 '+name,contains(f'round2::Kernel<(ng::Op){code}, 0>'))
 add('small.hc',lambda d:'packet27::small::(anonymous namespace)::Tuple<' in d and '(iq3::Type)8, 320u, 10240u, 7u>' in d)
 for mode,name in [(0,'bank'),(1,'select')]:add('NEW down.'+name,contains(f'p33::Kernel<{mode}u, (iq3::Type)20, 640u, 1u>'),dynamic=dict(weights_per_lane=8,instructions=188 if mode==0 else [290,306,482],messages=7 if mode==0 else 17,source='review-candidate-assembly.json',note='select instruction range depends on uniform or mixed lookup codes; not a speed prediction'))
 for t,fmt in [(22,'IQ2'),(21,'IQ3')]:add('NEW gate.restrict '+fmt,contains(f'p33::Kernel<0u, (iq3::Type){t}, 2560u, 1u>'))
 for t,fmt in [(14,'Q6'),(8,'Q8')]:
  for split in (1,4):add(f'NEW dense.segment {fmt} split{split}',contains(f'p33::Kernel<0u, (iq3::Type){t}, 2560u, {split}u>'))
 add('NEW route.rank4',lambda d:'p33r2::Simple<(integrated::Op)8,' in d and ', 512, 10>' in d,'BF16 and FP32 input variants summed; unchanged stages0/2, four-at-once comparisons stage1.')
 for code,name in [(12,'score'),(13,'softmax'),(14,'value')]:add('NEW QSA.shape '+name,contains(f'p33r2::Kernel<(ng::Op){code}, 0, true>'))
 data['study_rows']=rows;(P/'codegen.json').write_text(json.dumps(data,separators=(',',':'))+'\n')
 header='| Kernel | SIMD | Static inst / messages | 64-bit typed inst | int→float | SLM / barrier | Spill B | Scratch B/HW thread | Private B/HW thread | Cross-thread payload B | Pre-branch inst / backedges | Inner inst / messages per 8 lane weights |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|\n'
 for r in rows:
  d=r['dynamic'];inner=str(d['instructions'])+' / '+str(d['messages']) if d else 'unestablished'
  header+='| '+r['label']+' | '+','.join(map(str,r['simd']))+f" | {r['static_instructions']} / {r['static_messages']} | {r['alu64']} | {r['conversions']} | {r['slm_messages']} / {r['barriers']} | {r['spill_bytes']} | {r['scratch_bytes_per_hw_thread']} | {r['private_size_bytes_per_hw_thread']} | {r['payload_bytes']} | {r['prefix_instructions']} / {r['loop_backedges']} | {inner} |\n"
 (P/'kernel-table.md').write_text(header)
 print(len(rows),'study rows')
if __name__=='__main__':main()
