// Exercise the actual diagnostic header, including rejected/late speculation.
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
namespace fs=std::filesystem;using Allocation=unsigned;
static void require(bool v,const std::string&s){if(!v)throw std::runtime_error(s);}
static void save(const fs::path&p,const std::string&s){std::ofstream f(p);f<<s;require(bool(f),"write");}
static std::string hash(const std::vector<uint8_t>&v){unsigned char d[32];SHA256(v.data(),v.size(),d);std::ostringstream o;for(auto x:d)o<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(x);return o.str();}
namespace flash {struct Launch{std::string op,label;std::vector<std::string>weights,inputs,outputs;};inline size_t scalar_bytes(int t){return t;}}
struct Device{std::map<unsigned,std::vector<uint8_t>> allocations;unsigned copies=0;};
namespace ownrt {
static std::string quote(const std::string&s){return "\""+s+"\"";}
struct CopyEngine{Device&d;CopyEngine(Device&v):d(v){}unsigned copy(unsigned dst,size_t off,unsigned src,size_t begin,size_t n,std::initializer_list<int>){auto&a=d.allocations.at(dst);auto&b=d.allocations.at(src);require(off+n<=a.size()&&begin+n<=b.size(),"extent");std::memcpy(a.data()+off,b.data()+begin,n);return ++d.copies;}};
}
struct Engine{
 struct Args{int cards=1,rank=0;fs::path output;}a;
 struct Slot{Allocation id;size_t n;int type;};
 std::vector<std::map<std::string,Slot>>buffers{1};Device device;unsigned tail=0,reads=0;
 Device&dev(int){return device;}
 std::vector<uint8_t>readback(int,Allocation id,size_t n){++reads;auto v=device.allocations.at(id);require(v.size()==n,"read extent");return v;}
#include "route_capture.hpp"
};
template<class F>void refuses(F f){bool fail=false;try{f();}catch(const std::exception&){fail=true;}require(fail,"negative accepted");}
int main(int argc,char**argv){try{
 require(argc==2,"output root");fs::create_directories(argv[1]);
 for(int rank=0;rank<2;++rank){Engine e;e.a.rank=rank;e.a.output=fs::path(argv[1])/std::to_string(rank);fs::create_directories(e.a.output);
  e.device.allocations[1].resize(Engine::route_capture_bytes);e.route_capture_buffers={1};
  e.buffers[0]={{"ids",{2,30,4}},{"input",{3,2560,2}},{"streams",{4,10240,2}},{"logits",{5,512,2}}};
  for(const auto&[name,s]:e.buffers[0])e.device.allocations[s.id].resize(s.n*s.type);
  std::vector<uint8_t>expected(Engine::route_capture_bytes);
  auto site=[&](int local,int kind){std::string prefix="blk."+std::to_string(rank*24+local);
   if(kind==0)return flash::Launch{"gemv",prefix+".router",{prefix+".ffn_gate_inp.weight"},{"input"},{"logits"}};
   if(kind==1)return flash::Launch{"routed_gemv",prefix+".expsdown",{prefix+".ffn_down_exps.weight"},{"unused","ids"},{"unused"}};
   return flash::Launch{"hc_combine",prefix+".ffn.combine",{}, {"streams"},{"streams"}};
  };
  for(int fixture=1;fixture<=48;++fixture){
   if(fixture==17){e.capture_begin();e.capture_down(site(0,0),fixture);refuses([&]{e.capture_accept(fixture,100,123,true);});require(!e.route_capture_valid[fixture-1],"rejected accepted");}
   e.capture_begin();
   for(int local=0;local<24;++local){
    for(const auto&[name,s]:e.buffers[0]){auto&v=e.device.allocations[s.id];for(size_t i=0;i<v.size();++i)v[i]=uint8_t(i*19+local*7+fixture*23+s.id);}
    size_t off=((fixture-1)*24+local)*Engine::capture_stride;
    for(auto[id,offset]:std::vector<std::pair<int,int>>{{2,0},{3,120},{4,5240},{5,25720}}){auto&v=e.device.allocations[id];std::memcpy(expected.data()+off+offset,v.data(),v.size());}
    auto before=e.device.allocations;
    for(int kind=0;kind<3;++kind)e.capture_down(site(local,kind),fixture);
    for(unsigned id=2;id<=5;++id)require(before[id]==e.device.allocations[id],"source changed");
   }
   e.capture_accept(fixture,fixture+86,fixture+100,false);require(e.reads==0,"host read in loop");
  }
  require(e.device.allocations[1]==expected,"copy/redo differs");
  refuses([&]{e.capture_down(site(0,0),48);});refuses([&]{e.capture_accept(48,134,148,false);});
  auto count=e.device.copies;e.capture_down(site(0,0),0);e.capture_down(site(0,0),49);require(count==e.device.copies,"escaped bound");
  e.capture_flush();require(e.reads==1,"boundary read count");
  std::ifstream f(e.a.output/"capture.bin",std::ios::binary);std::vector<uint8_t>actual((std::istreambuf_iterator<char>(f)),{});require(actual==expected,"file bytes differ");
  refuses([&]{e.capture_flush();});
  e.capture_begin();refuses([&]{e.capture_accept(1,1,1,false);});
 }
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"synthetic_unit_test_only\":true,\"ranks\":2,\"steps_per_rank\":48,\"layers_per_rank\":24,\"bytes_compared\":61618176,\"host_reads_in_loop\":0}\n";
 return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
