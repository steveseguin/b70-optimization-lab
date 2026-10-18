// CPU-only byte-copy/commit diagnostic for the exact capture header.
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <vector>
#include <openssl/sha.h>
namespace fs=std::filesystem;
using Allocation=unsigned;
static void require(bool v,const std::string& s){if(!v)throw std::runtime_error(s);}
static void save(const fs::path& p,const std::string& s){std::ofstream f(p);f<<s;require(bool(f),"write");}
static std::string hash(const std::vector<uint8_t>& v){unsigned char d[32];SHA256(v.data(),v.size(),d);std::ostringstream o;for(auto x:d)o<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(x);return o.str();}
namespace flash {struct Launch{std::string op;std::vector<std::string>weights,inputs;};inline size_t scalar_bytes(int){return 4;}}
struct Device{std::map<unsigned,std::vector<uint8_t>> allocations;unsigned copies=0;};
namespace ownrt {
static std::string quote(const std::string&s){return "\""+s+"\"";}
struct CopyEngine {Device& d;CopyEngine(Device& v):d(v){}unsigned copy(unsigned dst,size_t off,unsigned src,size_t begin,size_t n,std::initializer_list<int>){auto&a=d.allocations.at(dst);auto&b=d.allocations.at(src);require(off+n<=a.size()&&begin+n<=b.size(),"extent");std::memcpy(a.data()+off,b.data()+begin,n);return ++d.copies;}};
}
struct Engine {
 struct Args{int cards=1,rank=0;fs::path output;}a;
 struct Slot{Allocation id;size_t n;int type=0;};
 std::vector<std::map<std::string,Slot>> buffers{1};
 Device device;unsigned tail=0,reads=0;
 Device&dev(int){return device;}
 std::vector<uint8_t>readback(int,Allocation id,size_t n){++reads;auto v=device.allocations.at(id);require(v.size()==n,"read extent");return v;}
#include "route_capture.hpp"
};
template<class F>static void refuses(F f){bool failed=false;try{f();}catch(const std::exception&){failed=true;}require(failed,"negative case accepted");}
int main(int argc,char**argv){try{
 require(argc==2,"output root");fs::create_directories(argv[1]);
 for(int rank=0;rank<2;++rank){Engine e;e.a.rank=rank;e.a.output=fs::path(argv[1])/std::to_string(rank);fs::create_directories(e.a.output);
  e.device.allocations[1].resize(Engine::route_capture_bytes);e.route_capture_buffers={1};
  std::vector<uint8_t>expected(Engine::route_capture_bytes);
  for(int local=0;local<24;++local){e.device.allocations[local+2].resize(120);e.buffers[0][std::to_string(local)]={unsigned(local+2),30};}
  auto site=[&](int local){return flash::Launch{"routed_gemv",{"blk."+std::to_string(rank*24+local)+".ffn_down_exps.weight"},{"activation",std::to_string(local)}};};
  for(int fixture=1;fixture<=64;++fixture){
   // A partially issued rejected speculation must never gain an accepted flag.
   if(fixture==17){e.route_capture_mask=0;e.capture_down(site(0),fixture);refuses([&]{e.capture_accept(fixture,fixture+86,fixture+100,true);});require(!e.route_capture_valid[fixture-1],"rejected speculation retained");}
   e.route_capture_mask=0;
   for(int local=0;local<24;++local){
    auto&source=e.device.allocations.at(local+2);
    for(int slot=0;slot<10;++slot){uint32_t fields[3]={uint32_t((fixture*17+local*13+slot)%512),0,2560};std::memcpy(source.data()+12*slot,fields,12);}
    auto original=source;e.capture_down(site(local),fixture);
    require(source==original,"capture modified source");
    std::memcpy(expected.data()+((fixture-1)*24+local)*120,source.data(),120);
   }
   e.capture_accept(fixture,fixture+86,fixture+100,false);
   require(e.reads==0,"host read in token loop");
  }
  require(e.device.allocations.at(1)==expected,"copy/redo bytes differ");
  auto count=e.device.copies;e.capture_down(site(0),0);e.capture_down(site(0),65);
  require(count==e.device.copies,"capture escaped 64-token bound");
  refuses([&]{e.capture_down(site(0),64);});
  refuses([&]{e.capture_accept(64,150,164,false);});
  e.capture_flush();require(e.reads==1,"one boundary read required");
  std::ifstream file(e.a.output/"routes.bin",std::ios::binary);std::vector<uint8_t>actual((std::istreambuf_iterator<char>(file)),{});
  require(actual==expected,"boundary output differs");
  refuses([&]{e.capture_flush();});
 }
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"synthetic_unit_test_only\":true,\"ranks\":2,\"steps_per_rank\":64,\"layers_per_rank\":24,\"bytes_compared\":368640,\"host_reads_in_loop\":0}\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
