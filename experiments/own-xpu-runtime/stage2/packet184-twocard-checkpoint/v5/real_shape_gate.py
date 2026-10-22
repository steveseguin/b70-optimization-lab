"""Production extent sizes with synthetic bytes, exact actual flat/static tile bodies."""
import csv,json,resource,subprocess
from p184_v5_build_engine import P,LOCAL,ROOT,B,CHECKED,sha,save,run,limits

def main():
 limits();out=B/'real-shape';out.mkdir(exist_ok=True)
 header=(CHECKED/'strict_snapshot.hpp').read_text();start=header.index('#ifdef OWN_RT_HOST_ONLY\nstruct SnapshotFlat');end=header.index('// SPEED2_WRITE_SET_BEGIN')
 rows=[r for r in csv.DictReader((LOCAL/'lineage-inputs/capture-extents.csv').open()) if int(r['candidate_copy_bytes'])]
 specs=[]
 for r in rows:
  n=int(r['candidate_copy_bytes']);stride=n if r['QSA_row']=='True' else 0;divisor=4 if r['source'].endswith('.pooled') else 1
  # Full extent allocation for QSA; other rows need precisely the admitted writer.
  size=int(r['allocation_bytes']) if stride else n
  specs.append('{'+','.join(map(str,(size,n,stride,divisor)))+'}')
 code='''#include <algorithm>\n#include <cstdint>\n#include <cstring>\n#include <cstddef>\n#include <span>\n#include <vector>\n#include <iostream>\n#include <stdexcept>\n#define OWN_RT_HOST_ONLY\nnamespace integrated {struct HostOperation{virtual void run(std::span<void*const>)const=0;virtual ~HostOperation()=default;};}\n'''+header[start:end]+'''
struct Spec{size_t size,bytes,stride,divisor;};
int main(){try{
 std::vector<Spec> specs={'''+','.join(specs)+'''};
 size_t total=0,tiles=0;for(auto r:specs)total+=r.bytes;
 std::vector<std::vector<uint8_t>> source;for(size_t i=0;i<specs.size();++i){source.emplace_back(specs[i].size+32);for(size_t j=0;j<source.back().size();++j)source.back()[j]=uint8_t((j*17+i*31)%251);}
 std::vector<uint8_t> image(total+32,0xa5),expected(image),restored;std::vector<SnapshotStatic::Item> table;
 size_t off=0;for(size_t i=0;i<specs.size();++i){auto r=specs[i];tiles+=(r.bytes+4095)/4096;table.push_back({image.data()+off,source[i].data()+16,r.bytes,tiles,r.stride,r.divisor});off+=r.bytes;}
 unsigned cases=0;
 for(int position:{0,1,3,4,31,32,63,64,4095}){
  off=0;for(size_t i=0;i<specs.size();++i){auto r=specs[i];size_t shift=size_t(position)/r.divisor*r.stride;std::memcpy(expected.data()+off,source[i].data()+16+shift,r.bytes);off+=r.bytes;}
  for(size_t tile=0;tile<tiles;++tile)for(size_t lane=0;lane<256;++lane)SnapshotStatic::copy_lane(table.data(),table.size(),tile,lane,position,false);
  if(image!=expected)throw std::runtime_error("capture bytes/redzone differ");
  std::vector<std::vector<uint8_t>> before=source;
  for(size_t i=0;i<specs.size();++i){auto r=specs[i];size_t shift=size_t(position)/r.divisor*r.stride;std::memset(source[i].data()+16+shift,0x19,r.bytes);}
  for(size_t tile=0;tile<tiles;++tile)for(size_t lane=0;lane<256;++lane)SnapshotStatic::copy_lane(table.data(),table.size(),tile,lane,position,true);
  if(source!=before)throw std::runtime_error("restore bytes, old QSA rows or redzones differ");
  ++cases;
 }
 std::cout<<"{\\\"passed\\\":true,\\\"positions\\\":"<<cases<<",\\\"extents\\\":"<<specs.size()<<",\\\"copy_bytes\\\":"<<total<<",\\\"table_bytes\\\":"<<table.size()*sizeof(SnapshotStatic::Item)<<"}"<<std::endl;
}catch(const std::exception& e){std::cerr<<e.what()<<std::endl;return 1;}}
'''
 source=out/'transport.cpp';source.write_text(code);results=[]
 for name,cxx in [('GNU','g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
  binary=out/('fixture-'+name);run([cxx,'-std=c++20','-O2',source,'-o',binary],'transport-'+name)
  for repeat in (1,2):
   cp=subprocess.run([str(binary)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120);assert cp.returncode==0,cp.stderr
   result=json.loads(cp.stdout);assert result['extents']==984 and result['copy_bytes']==19025640;results.append(dict(result,compiler=name,repeat=repeat))
 save(P/'evidence/real-shape.json',dict(passed=True,device_executed=False,model_read=False,synthetic_payload=True,actual_production_extent_sizes=True,runs=results,sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'real_shape_gate.py',CHECKED/'strict_snapshot.hpp',LOCAL/'lineage-inputs/capture-extents.csv']}))
 print('Production extent bytes/offsets/redzones GNU+Intel PASS')
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
