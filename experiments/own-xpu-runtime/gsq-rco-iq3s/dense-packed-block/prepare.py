#!/usr/bin/env python3
"""Deterministically derive source only. No compiler, payload or Device invocation."""
from pathlib import Path
import collections,difflib,hashlib,json
P=Path(__file__).resolve().parent;L=P.parent;R=L.parents[2]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def derive():
 g=json.loads((L/'graph/new-plan.json').read_text());c=json.loads((L/'metadata/new-census.json').read_text());sites=[]
 for x in g['launches']:
  if x['op']!='gemv' or len(x['weights'])!=1:continue
  name=x['weights'][0];t=c['tensors'][name]
  if t['type_id'] not in (12,13,23):continue
  assert x['shape']==[1,t['dimensions'][1],2560] and t['dimensions']==[2560,t['dimensions'][1]]
  sites.append(dict(label=x['label'],weight=name,type_id=t['type_id'],rows=t['dimensions'][1],columns=2560,packed_bytes=t['bytes'],input=x['inputs'][0],outputs=x['outputs'],shard=t['shard'],file_offset=t['file_offset']))
 assert len(sites)==116 and collections.Counter(s['type_id'] for s in sites)=={12:43,13:31,23:42}
 (P/'selection.json').write_text(json.dumps(dict(sites=sites,counts=dict(collections.Counter(s['type_id'] for s in sites)),scope='Exact original dense shared-input count1/expert1 sites; no active/error operands are consumed by the inherited PackedOperation.'),indent=2)+'\n')
 h='#pragma once\n#include <array>\n#include <string_view>\nnamespace denseblock {\nstruct Site {std::string_view label,weight;unsigned type,rows;size_t bytes;};\ninline constexpr std::array<Site,116> sites{{\n'
 for s in sites:h+=' {"'+s['label']+'","'+s['weight']+'",'+str(s['type_id'])+','+str(s['rows'])+','+str(s['packed_bytes'])+'},\n'
 h+='}};\ninline const Site* selected(std::string_view label,std::string_view weight){for(const auto&s:sites)if(s.label==label&&s.weight==weight)return &s;return nullptr;}\n}\n'
 (P/'selection.hpp').write_text(h)
 old=(L/'native-formats/packed.hpp').read_text();begin=old.index('template<unsigned T> class PackedKernel;');end=old.index('inline Shape validate(',begin)
 operation=old[begin:end].replace('PackedKernel','DenseBlockKernel').replace('PackedOperation','DenseBlockOperation').replace('lane_sum<T>','block_lane_sum<T>')
 prefix=(P/'arithmetic.hpp').read_text()
 out='#pragma once\n#include "../native-formats/packed.hpp"\n#include "selection.hpp"\n'+prefix+'\nnamespace denseblock {\nusing gsqn::Shape;using gsqn::Bound;using gsqn::require;\n'+operation+'''
inline const Site& policy(const integrated::Matrix&m,std::string_view label,std::string_view weight,gsqn::InputMode input){
 const auto*s=selected(label,weight);require(s,"dense block exact census site");
 require(unsigned(m.type)==s->type&&m.rows==s->rows&&m.columns==2560&&m.span==m.rows,"dense block exact geometry/type/span");
 require(m.count==1&&m.experts==1&&!m.routes&&!m.status&&input==gsqn::InputMode::shared,"dense block original dense shared input");
 require(m.activation==iq3::Type::BF16&&m.output_type==iq3::Type::BF16&&!m.fp32,"dense block original BF16 precision");
 require(gsq::row_bytes(s->type,m.columns)*m.rows==s->bytes,"dense block exact packed extent");return *s;
}
template<unsigned T> inline integrated::Launch issue(ownrt::Device&d,const integrated::Matrix&m,Shape s){DenseBlockOperation<T>op;op.s=s;std::array<ownrt::Allocation,5>ids{m.w,m.x,m.y,m.x,m.y};auto e=d.compute(op,ids,{});return {e,e,1};}
inline integrated::Launch submit(ownrt::Device&d,const integrated::Matrix&m,std::string_view label,std::string_view weight,gsqn::InputMode input){
 policy(m,label,weight,input);auto s=gsqn::validate(d,m,input,gsqn::Storage::packed_direct);
 switch(unsigned(m.type)){case 12:return denseblock::issue<12>(d,m,s);case 13:return denseblock::issue<13>(d,m,s);case 23:return denseblock::issue<23>(d,m,s);}throw std::invalid_argument("dense block unsupported type");
}
} // namespace denseblock
'''
 (P/'block.hpp').write_text(out)
 (P/'kernel-delta.patch').write_text(''.join(difflib.unified_diff(old[begin:end].splitlines(True),operation.splitlines(True),fromfile='native-formats/packed.hpp operation',tofile='dense-packed-block/block.hpp operation')))
 sources=[L/'native-formats/packed.hpp',L/'native-formats/device_formats.hpp',L/'graph/new-plan.json',L/'metadata/new-census.json',L/'dense-q6-p33/build/source/generic_engine.hpp',L/'profiling/dense-q6-class/launch-b/evidence/device-b/review.json']
 (P/'source-pins.json').write_text(json.dumps({str(p.relative_to(R)):sha(p) for p in sources},indent=2)+'\n')
 print(json.dumps(dict(source_only=True,sites=len(sites),counts=dict(collections.Counter(s['type_id'] for s in sites)),block_sha256=sha(P/'block.hpp'))))
if __name__=='__main__':derive()
