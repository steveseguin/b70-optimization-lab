"""Extract unchanged host argument checks from the actual R5 device entries."""
from pathlib import Path
P=Path(__file__).resolve().parent

def between(s,a,b):
 assert s.count(a)==1,a
 return s.split(a,1)[1].split(b,1)[0]

def generate():
 p6=(P.parent/'packet6-kopt/kernels.cpp').read_text()
 p8=(P.parent/'packet8-kopt3/kernels.cpp').read_text()
 p9=(P.parent/'packet9-kopt4/kernels.cpp').read_text()
 p10=(P.parent/'packet10-kopt5/kernels.cpp').read_text()
 h='#pragma once\n#include "../packet26-specialised/performance.hpp"\n#include <limits>\n#include <set>\nnamespace p28_validation {\n'
 h+='namespace expanded {using namespace iq3;using namespace iq3::expanded;\ninline void check(ownrt::Device& d,const iq3::kopt3::Matrix& m,unsigned split){'+between(p10,'kopt3::Launch gemv(ownrt::Device& d,const kopt3::Matrix& m,unsigned split){','Multiply op;')+'}\n}\n'
 h+='namespace expert {using namespace iq3;using namespace iq3::kopt4;\nstruct Projection {'+between(p9,'struct Projection:ownrt::SyclOperation {',' template<Type T>')+'};\n'
 h+='inline void check(ownrt::Device& d,ownrt::Allocation id,size_t bytes){'+between(p9,'void check(ownrt::Device& d,ownrt::Allocation id,size_t bytes) {','\n}')+'}\n'
 h+='inline void project(ownrt::Device& device,const std::vector<Matrix>& matrices,unsigned split,bool shared){'+between(p9,'Launch project(ownrt::Device& device,const std::vector<Matrix>& matrices,unsigned split,bool shared) {',' auto e=device.compute')+'}\n}\n'
 h+='namespace decode {using namespace iq3;using namespace iq3::kopt3;\n'+between(p8,'std::string properties="null";','void capture')
 h+='struct Desc {'+between(p8,'struct Desc {','};')+'};\nstruct Multiply {'+between(p8,'struct Multiply:ownrt::SyclOperation {','  template<bool SLM>')+'};\n'
 h+='inline size_t workspace_bytes(size_t rows,unsigned count,Variant v){return mul(mul(mul(rows,count),splits(v)),4); }\n'
 h+='inline void project(ownrt::Device& device,const std::vector<Matrix>& matrices,Variant variant){'+between(p8,'Launch multiply(ownrt::Device& device,const std::vector<Matrix>& matrices,Variant variant) {','  auto first=device.compute').replace('workspace_bytes(', 'p28_validation::decode::workspace_bytes(')+'}\n}\n'
 h+='namespace raw {using namespace iq3;using namespace iq3::kopt;\n'+between(p6,'namespace {','// A fully aligned interior')
 h+='struct Multiply {'+between(p6,'struct Multiply:ownrt::SyclOperation {','  template<unsigned SG>')+'};\n'
 h+='inline Descriptor bind_matrix('+between(p6,'Descriptor bind_matrix(','ownrt::Event finish')
 h+='inline void check(ownrt::Device& d,const iq3::kopt3::Matrix& m){Multiply op;op.subgroup=32;op.matrices=1;std::vector<ownrt::Allocation> ids;op.desc[0]=bind_matrix(d,op,ids,{m.type,m.w,m.x,m.y,m.rows,m.columns,m.activation,m.output_type,m.fp32},1,1,m.rows);'+between(p6,'ownrt::Event finish(ownrt::Device& d,Multiply& op,const std::vector<ownrt::Allocation>& ids) {','  return d.compute')+'}\n}\n'
 h+='inline void baseline(ownrt::Device& d,const std::vector<integrated::Matrix>& m,unsigned v,bool shared){if(m[0].count>1)expert::project(d,m,1,shared);else if(v==6||v==7)expanded::check(d,m[0],v==7?4:1);else if(v==0)raw::check(d,m[0]);else if(v==2||v==4)decode::project(d,m,v==4?iq3::kopt3::Variant::constant_split4:iq3::kopt3::Variant::constant);else throw std::invalid_argument("uncovered baseline validation variant");}\n}\n'
 out=P/'build/device_validation.hpp';out.parent.mkdir(exist_ok=True);out.write_text(h)
if __name__=='__main__':generate()
