"""Compile verbatim device entry validation into fixture-only CPU twins."""
from pathlib import Path
import hashlib,json,re
P=Path(__file__).resolve().parent
def between(text,start,end):
 assert text.count(start)==1,(start,text.count(start))
 assert end in text.split(start,1)[1],end
 return text.split(start,1)[1].split(end,1)[0]
def mapped(text):
 def replace(m):
  name=m[1]
  if name=="device_validation.hpp":return m[0]
  source=next(x.resolve() for x in (P/name,P/"../../stage1/packet3-prep/src"/name) if x.is_file())
  assert source.is_file(),source
  target=P/'build/checked'/source.relative_to(P.parents[3])
  return '#include '+json.dumps(str(target))
 return re.sub(r'#include "([^"\n]+)"',replace,text)
def generate(dest):
 dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
 p8=(P.parent/'packet8-kopt3/kernels.cpp').read_text()
 p10=(P.parent/'packet10-kopt5/kernels.cpp').read_text()
 p9=(P.parent/'packet9-kopt4/kernels.cpp').read_text()
 native=(P/'native.cpp').read_text()
 dense=between(p10,'kopt3::Launch gemv(ownrt::Device& d,const kopt3::Matrix& m,unsigned split){','Multiply op;')
 expert=between(p9,'Launch project(ownrt::Device& device,const std::vector<Matrix>& matrices,unsigned split,bool shared) {',' auto e=device.compute')
 fields=between(p9,'struct Projection:ownrt::SyclOperation {',' template<Type T>')
 extent=between(p9,'void check(ownrt::Device& d,ownrt::Allocation id,size_t bytes) {','\n}')
 ng=between(native,'ownrt::Event submit(ownrt::Device& d,Shape s,std::span<const ownrt::Allocation> a,std::span<const ownrt::Event> deps){','Kernel k(s);')
 packed=between(p8,'Launch multiply(ownrt::Device& device,const std::vector<Matrix>& matrices,Variant variant) {','  auto first=device.compute')
 packed=packed.replace('workspace_bytes(m.span,m.count,variant)','fixture_validation::packed::workspace_bytes(m.span,m.count,variant)')
 packed_fields=between(p8,'struct Multiply:ownrt::SyclOperation {','  template<bool SLM>')
 desc=between(p8,'struct Desc {','};')
 utilities=between(p8,'size_t mul(size_t a,size_t b)', 'void capture(')
 workspace=between(p8,'size_t workspace_bytes(size_t rows,unsigned count,Variant v)', 'Launch multiply(')
 packed_code=('namespace packed { using namespace iq3;using namespace iq3::kopt3;\n'
  'struct Desc {'+desc+'};\nstruct Multiply {'+packed_fields+'};\n'
  'inline size_t mul(size_t a,size_t b)'+utilities.replace('void check(', 'inline void check(')+'inline size_t workspace_bytes(size_t rows,unsigned count,Variant v)'+workspace+
  'inline void multiply(ownrt::Device& device,const std::vector<Matrix>& matrices,Variant variant){'+packed+'}\n}\n')
 content=("#pragma once\n#include \"performance.hpp\"\n#include \"native.hpp\"\n"
  "namespace fixture_validation { inline bool only=false,poison_dense=false,inject=false;\n"+packed_code+"namespace expanded {\nusing namespace iq3;using namespace iq3::expanded;\n"
  "inline void dense(ownrt::Device& d,const iq3::kopt3::Matrix& m,unsigned split){"+dense+"}\n}\n"
  "namespace expert {using namespace iq3;using namespace iq3::kopt4;\nstruct Projection {"+fields+"};\n"
  "inline void check(ownrt::Device& d,ownrt::Allocation id,size_t bytes){"+extent+"}\n"
  "inline void project(ownrt::Device& device,const std::vector<Matrix>& matrices,unsigned split,bool shared){"+expert+"}\n}\n"
  "inline void nongemv(ownrt::Device& d,ng::Shape s,std::span<const ownrt::Allocation> a){using namespace ng;"+ng+"}\n}\n")
 (dest/'device_validation.hpp').write_text(mapped(content))
 adapter_source=(P/'adapter.cpp').read_text()
 assert adapter_source.count('NgHost k(sh);last=d.compute(k,a,chain);')==1
 adapter=adapter_source.replace('NgHost k(sh);last=d.compute(k,a,chain);','fixture_validation::nongemv(d,sh,a);NgHost k(sh);last=d.compute(k,a,chain);')
 performance_source=(P/'performance.cpp').read_text()
 for anchor in ('return multiply(d,{m},v,false);','return multiply(d,m,2,shared);'):assert performance_source.count(anchor)==1
 performance=performance_source.replace('return multiply(d,{m},v,false);','if(arithmetic::is_expanded(v))fixture_validation::expanded::dense(d,m,v==7?4:1);else {if(v!=2&&v!=4)throw std::invalid_argument("fixture validation: unmirrored dense entry");fixture_validation::packed::multiply(d,{m},v==4?iq3::kopt3::Variant::constant_split4:iq3::kopt3::Variant::constant);}return multiply(d,{m},v,false);').replace('return multiply(d,m,2,shared);','fixture_validation::expert::project(d,m,1,shared);return multiply(d,m,2,shared);')
 for name,text in [('adapter',adapter),('performance',performance)]:
  (dest/(name+'.cpp')).write_text('#include "device_validation.hpp"\n#line 1 '+json.dumps(str(P/(name+'.cpp')))+'\n'+mapped(text))
 (dest/'manifest.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [P.parent/'packet8-kopt3/kernels.cpp',P.parent/'packet10-kopt5/kernels.cpp',P.parent/'packet9-kopt4/kernels.cpp',P/'native.cpp']},indent=2)+'\n')
if __name__=='__main__':
 import sys
 generate(sys.argv[1])
