#include "fixture.hpp"
#include "gguf.hpp"
#include "mock_device.hpp"
#include <iomanip>
#include <iostream>
#include <sstream>
#include <cstring>
using namespace iq3;
void expect(bool b) {if(!b)throw std::runtime_error("test assertion failed");}
template<class F>void rejects(F f) {bool rejected=false;try{f();}catch(const std::exception&){rejected=true;}expect(rejected);}
std::string meta_json(const Meta& m) {
  if(auto p=std::get_if<std::string>(&m.value))return ownrt::quote(*p);
  if(auto p=std::get_if<uint64_t>(&m.value))return std::to_string(*p);
  if(auto p=std::get_if<int64_t>(&m.value))return std::to_string(*p);
  if(auto p=std::get_if<double>(&m.value)){std::ostringstream s;s<<std::setprecision(17)<<*p;return s.str();}
  std::string out="[";bool comma=false;for(auto& v:std::get<std::vector<Meta>>(m.value)){out+=(comma?",":"")+meta_json(v);comma=true;}return out+"]";
}
struct CpuBackend:ownrt::MockDevice {
  ownrt::Event compute(const ownrt::Operation&,std::span<void* const> ptrs,std::span<const ownrt::Event> deps) override {
    return copy(ptrs[1],ptrs[0],4,deps);
  }
};
void ownership() {
  auto backend=std::make_unique<CpuBackend>();auto* mock=backend.get();ownrt::Device d(std::move(backend));
  auto alloc=[&](std::string s,ownrt::Memory m){return d.arena.allocate(s,4,m,ownrt::Category::weights,ownrt::Lifetime::process);};
  auto a=alloc("a",ownrt::Memory::device),b=alloc("b",ownrt::Memory::device),h=alloc("host",ownrt::Memory::shadow);
  *static_cast<uint32_t*>(d.arena.row(a).pointer)=123;ownrt::Operation op;std::array ids{a,b};
  std::array bad{a,h};rejects([&]{d.compute(op,bad,{});});ownrt::Event foreign=999999;rejects([&]{d.compute(op,ids,std::span(&foreign,1));});
  auto e=d.compute(op,ids,{});rejects([&]{d.arena.release(a);});
  auto failed=d.shutdown(std::chrono::milliseconds(1));expect(!failed.safe_to_exit && d.arena.row(a).live);
  mock->finish(e);expect(*static_cast<uint32_t*>(d.arena.row(b).pointer)==123);
  auto done=d.shutdown(std::chrono::milliseconds(10));expect(done.safe_to_exit && !done.live_bytes && !done.in_flight);
  rejects([&]{d.compute(op,ids,{});});std::cout<<done.json()<<'\n';
}
void routes() {
  // Exercise every expert ID on ordinary CPU storage; no device API involved.
  constexpr unsigned rows=3,k=32,experts=512;
  std::vector<uint8_t> weights(size_t(experts)*rows*k*2);
  std::array<uint16_t,k> x;x.fill(half_bits(1));
  for(unsigned e=0;e<experts;++e)for(unsigned r=0;r<rows;++r)for(unsigned c=0;c<k;++c) {
    auto bits=half_bits(float((e%16)*3+r+c%3));auto off=((e*rows+r)*k+c)*2;
    weights[off]=uint8_t(bits);weights[off+1]=uint8_t(bits>>8);
  }
  for(unsigned e=0;e<experts;++e) {
    Route route{e,1,2};expect(valid_route(route,experts,rows,2));
    for(unsigned r=0;r<route.row_count;++r) {
      auto index=size_t(route.expert_id)*rows+route.row_begin+r;
      float expected=0;for(unsigned c=0;c<k;++c)expected+=float((e%16)*3+1+r+c%3);
      expect(gemv_row(Type::F16,weights.data()+index*k*2,x.data(),Type::F16,k)==expected);
    }
  }
  for(auto bad:{Route{512,0,1},Route{0,4,0},Route{0,2,2},Route{0,0,3},Route{UINT32_MAX,UINT32_MAX,UINT32_MAX}})
    expect(!valid_route(bad,experts,rows,2));
  expect(valid_route(Route{0,3,0},experts,rows,2));
  for(uint32_t bits:{0u,0x80000000u,1u,0x007fffffu,0x7f800000u,0xff800000u,0x7f800001u,0xffc12345u}) {
    uint8_t b[]={uint8_t(bits),uint8_t(bits>>8),uint8_t(bits>>16),uint8_t(bits>>24)};
    expect(std::bit_cast<uint32_t>(decode(Type::F32,b,0))==bits);
  }
  std::cout<<"512 expert IDs, row spans, invalid routes, F32 special bits pass\n";
}
int main(int argc,char** argv) {
  try {
    if(argc<2)throw std::runtime_error("mode required");std::string mode=argv[1];
    if(mode=="--ownership")ownership();
    else if(mode=="--routes")routes();
    else if(mode=="--math" && argc==4) {
      Fixture f(argv[2]);auto decoded=f.decoded(),y=f.gemv();std::ofstream out(argv[3],std::ios::binary);
      out.write(reinterpret_cast<const char*>(decoded.data()),decoded.size()*4);out.write(reinterpret_cast<const char*>(y.data()),y.size()*4);
      for(auto v:y){auto b=output_bits(v,f.output_type);out.write(reinterpret_cast<const char*>(&b),2);}expect(bool(out));
    } else if(mode=="--casts" && argc==4) {
      std::ifstream in(argv[2],std::ios::binary);std::ofstream out(argv[3],std::ios::binary);float f;
      while(in.read(reinterpret_cast<char*>(&f),4)){uint16_t b[]={half_bits(f),bf16_bits(f)};out.write(reinterpret_cast<const char*>(b),4);}expect(in.eof() && bool(out));
    } else if(mode=="--widen" && argc==3) {
      std::ofstream out(argv[2],std::ios::binary);for(uint32_t i=0;i<65536;++i){uint8_t b[]={uint8_t(i),uint8_t(i>>8)};float v[]={decode(Type::F16,b,0),decode(Type::BF16,b,0)};out.write(reinterpret_cast<const char*>(v),8);}expect(bool(out));
    } else if(mode=="--headers") {
      std::vector<Shard> shards;for(int i=2;i<argc;++i)shards.emplace_back(argv[i]);validate_splits(shards);
      std::cout<<'[';bool comma=false;
      for(auto& s:shards) {
        std::cout<<(comma?",":"")<<"{\"file_bytes\":"<<s.file_bytes<<",\"header_bytes\":"<<s.header_bytes<<",\"read_bytes\":"<<s.read_bytes<<",\"data_start\":"<<s.data_start<<",\"metadata\":{";comma=true;bool mc=false;
        for(auto& [key,m]:s.metadata){std::cout<<(mc?",":"")<<ownrt::quote(key)<<":"<<meta_json(m);mc=true;}
        std::cout<<"},\"tensors\":{";bool tc=false;
        for(auto& [name,t]:s.tensors){std::cout<<(tc?",":"")<<ownrt::quote(name)<<":{\"type_id\":"<<unsigned(t.type)<<",\"data_offset\":"<<t.offset<<",\"bytes\":"<<t.bytes<<",\"dimensions\":[";tc=true;for(size_t i=0;i<t.dimensions.size();++i)std::cout<<(i?",":"")<<t.dimensions[i];std::cout<<"]}";}
        std::cout<<"}}";
      }std::cout<<"]\n";
    } else if(mode=="--model" && argc>=4) {
      std::vector<std::filesystem::path> paths;for(int i=3;i<argc;++i)paths.emplace_back(argv[i]);Model m(paths,read_plan(argv[2]));auto totals=m.census();
      std::cout<<'['<<totals[0]<<','<<totals[1]<<','<<totals[2]<<"]\n";
    } else if(mode=="--slice" && argc==7) {
      Shard s(argv[2]);auto& t=s.tensors.at(argv[3]);uint64_t start=std::stoull(argv[4]);size_t bytes=std::stoull(argv[5]);auto slice=s.slice(t,start,bytes);auto moved=std::move(slice);
      std::ofstream out(argv[6],std::ios::binary);out.write(reinterpret_cast<const char*>(moved.data()),moved.size());expect(bool(out));
      rejects([&]{s.slice(t,t.bytes,1);});rejects([&]{s.slice(t,UINT64_MAX,1);});rejects([&]{s.slice(t,0,0);});
    } else if(mode=="--reserve" && argc>=4) {
      std::vector<std::filesystem::path> paths;for(int i=3;i<argc;++i)paths.emplace_back(argv[i]);Model m(paths,read_plan(argv[2]));ownrt::Device d(std::make_unique<ownrt::MockDevice>());
      for(auto& p:m.plan) {
        if(!p.mask){rejects([&]{m.reserve(p.name,0,d);});continue;}
        for(unsigned card=0;card<2;++card) {
          if(!(p.mask&(1<<card))){rejects([&]{m.reserve(p.name,card,d);});continue;}
          auto id=m.reserve(p.name,card,d);expect(d.arena.row(id).bytes==p.bytes && d.arena.row(id).category==ownrt::Category::weights);d.arena.release(id);
        }
      }expect(d.shutdown(std::chrono::milliseconds(10)).safe_to_exit);std::cout<<"reserve pass\n";
    } else throw std::runtime_error("unknown mode/arguments");
    return 0;
  }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
