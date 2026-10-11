"""Compile verbatim device entry validation into fixture-only CPU twins."""
from pathlib import Path
import hashlib,json
P=Path(__file__).resolve().parent
def between(text,start,end):
 assert text.count(start)==1,(start,text.count(start))
 assert end in text.split(start,1)[1],end
 return text.split(start,1)[1].split(end,1)[0]
def generate(dest):
 dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
 p10=(P.parent/'packet10-kopt5/kernels.cpp').read_text()
 p9=(P.parent/'packet9-kopt4/kernels.cpp').read_text()
 native=(P/'native.cpp').read_text()
 dense=between(p10,'kopt3::Launch gemv(ownrt::Device& d,const kopt3::Matrix& m,unsigned split){','Multiply op;')
 expert=between(p9,'Launch project(ownrt::Device& device,const std::vector<Matrix>& matrices,unsigned split,bool shared) {',' auto e=device.compute')
 fields=between(p9,'struct Projection:ownrt::SyclOperation {',' template<Type T>')
 extent=between(p9,'void check(ownrt::Device& d,ownrt::Allocation id,size_t bytes) {','\n}')
 ng=between(native,'ownrt::Event submit(ownrt::Device& d,Shape s,std::span<const ownrt::Allocation> a,std::span<const ownrt::Event> deps){','Kernel k(s);')
 content=("#pragma once\n#include \"performance.hpp\"\n#include \"native.hpp\"\n"
  "namespace fixture_validation { inline bool only=false,poison_dense=false,inject=false;\nnamespace expanded {\nusing namespace iq3;using namespace iq3::expanded;\n"
  "inline void dense(ownrt::Device& d,const iq3::kopt3::Matrix& m,unsigned split){"+dense+"}\n}\n"
  "namespace expert {using namespace iq3;using namespace iq3::kopt4;\nstruct Projection {"+fields+"};\n"
  "inline void check(ownrt::Device& d,ownrt::Allocation id,size_t bytes){"+extent+"}\n"
  "inline void project(ownrt::Device& device,const std::vector<Matrix>& matrices,unsigned split,bool shared){"+expert+"}\n}\n"
  "inline void nongemv(ownrt::Device& d,ng::Shape s,std::span<const ownrt::Allocation> a){using namespace ng;"+ng+"}\n}\n")
 (dest/'device_validation.hpp').write_text(content)
 adapter_source=(P/'adapter.cpp').read_text()
 assert adapter_source.count('NgHost k(sh);last=d.compute(k,a,chain);')==1
 adapter=adapter_source.replace('NgHost k(sh);last=d.compute(k,a,chain);','fixture_validation::nongemv(d,sh,a);NgHost k(sh);last=d.compute(k,a,chain);')
 performance_source=(P/'performance.cpp').read_text()
 for anchor in ('return multiply(d,{m},v,false);','return multiply(d,m,2,shared);'):assert performance_source.count(anchor)==1
 performance=performance_source.replace('return multiply(d,{m},v,false);','if(!arithmetic::is_expanded(v))throw std::invalid_argument("fixture validation: unexpected dense entry");fixture_validation::expanded::dense(d,m,v==7?4:1);return multiply(d,{m},v,false);').replace('return multiply(d,m,2,shared);','fixture_validation::expert::project(d,m,1,shared);return multiply(d,m,2,shared);')
 for name,text in [('adapter',adapter),('performance',performance)]:
  (dest/(name+'.cpp')).write_text('#include "device_validation.hpp"\n#line 1 '+json.dumps(str(P/(name+'.cpp')))+'\n'+text)
 (dest/'manifest.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [P.parent/'packet10-kopt5/kernels.cpp',P.parent/'packet9-kopt4/kernels.cpp',P/'native.cpp']},indent=2)+'\n')
if __name__=='__main__':
 import sys
 generate(sys.argv[1])
