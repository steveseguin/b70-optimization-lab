// Exercises every compiled p33 dense T/K/split instantiation without changing
// the runtime object set. This is correctness evidence, never a speed benchmark.
#include "p33_submit.hpp"
#include "failure.hpp"
#include <array>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <set>
#include <vector>

namespace {
using namespace ownrt;
using namespace integrated;
using Clock=std::chrono::steady_clock;
void check(bool ok,const std::string& what){if(!ok)throw std::runtime_error(what);}
#ifdef OWN_RT_HOST_ONLY
struct Cpu final:Backend {
 std::string identity()const override{return "CPU packet37 all-linked p33 fixture";}
 void* allocate(size_t n,Memory)override{return ::operator new(n,std::align_val_t(64));}
 void release(void* p,Memory)override{::operator delete(p,std::align_val_t(64));}
 Event copy(void* dst,const void* src,size_t n,std::span<const Event>)override{std::memcpy(dst,src,n);return next_handle();}
 Event marker(std::span<const Event>)override{return next_handle();}
 Event compute(const Operation& op,std::span<void*const> p,std::span<const Event>)override{dynamic_cast<const HostOperation&>(op).run(p);return next_handle();}
 bool complete(Event)override{return true;}
 bool wait(Event,Deadline)override{return true;}
 EventTiming timing(Event)override{return {0,0};}
 void synchronize()override{}void clear_events()override{}void close_queue()override{}void close_context()override{}
};
#endif
struct Runner {
 Device device;CopyEngine copy;std::vector<Allocation> owned;size_t serial=0;
 std::chrono::seconds wait_limit;Clock::time_point deadline;
 static std::unique_ptr<Backend> backend(unsigned card){
#ifdef OWN_RT_HOST_ONLY
 (void)card;return std::make_unique<Cpu>();
#else
 return make_sycl_device(card,false);
#endif
 }
 Runner(unsigned card,unsigned seconds):device(backend(card)),copy(device),wait_limit(seconds),deadline(Clock::now()+wait_limit){}
 Allocation alloc(size_t n,Memory m=Memory::device){auto id=device.arena.allocate("p33-linked-"+std::to_string(serial++),n,m,Category::scratch,Lifetime::transaction);owned.push_back(id);return id;}
 void finish(Event e){check(device.wait(e,wait_limit),"p33 linked fixture submission deadline");}
 Allocation upload(const void* src,size_t bytes){auto host=alloc(bytes,Memory::pinned),out=alloc(bytes);std::memcpy(device.arena.row(host).pointer,src,bytes);finish(copy.copy(out,0,host,0,bytes,{}));return out;}
 void clear(){device.retire_completed_events();for(auto id:owned)device.arena.release(id);owned.clear();}
 void between_cases(){check(Clock::now()<deadline,"p33 linked fixture total deadline");}
};
uint32_t rng(uint32_t& state){state^=state<<13;state^=state>>17;state^=state<<5;return state;}
const char* type_name(iq3::Type t){switch(t){case iq3::Type::Q6_K:return "Q6_K";case iq3::Type::Q8_0:return "Q8_0";case iq3::Type::F32:return "F32";case iq3::Type::BF16:return "BF16";default:throw std::invalid_argument("fixture type");}}
std::vector<uint8_t> weights(iq3::Type type,unsigned k,unsigned rows,unsigned variant,unsigned mode){
 const auto layout=iq3::layout(type);std::vector<uint8_t> packed(size_t(rows)*(k/layout.elements)*layout.bytes);
 uint32_t state=0x23456789u+unsigned(type)*29+k+mode*17;
 for(auto& byte:packed)byte=uint8_t(rng(state));
 if(type==iq3::Type::F32||type==iq3::Type::BF16){
  constexpr uint32_t tiny32[]{0,0x80000000,1,0x80000001,0x007fffff,0x807fffff,0x00800000,0x80800000};
  constexpr uint16_t tiny16[]{0,0x8000,1,0x8001,0x007f,0x807f,0x0080,0x8080};
  for(size_t i=0;i<size_t(rows)*k;++i){float value=float(int((i*13+mode*7)%127)-63)/128.f;
   if(type==iq3::Type::F32){uint32_t bits=mode==2?tiny32[i%8]:std::bit_cast<uint32_t>(value);std::memcpy(packed.data()+i*4,&bits,4);}
   else {uint16_t bits=mode==2?tiny16[i%8]:iq3::bf16_bits(value);std::memcpy(packed.data()+i*2,&bits,2);}
  }
 }else{
  constexpr uint16_t tiny[]{0,0x8000,1,0x8001,0x03ff,0x83ff,0x0400,0x8400};
  for(size_t off=0;off<packed.size();off+=layout.bytes){const size_t at=off+(type==iq3::Type::Q6_K?208:0);uint16_t scale=mode==2?tiny[(off/layout.bytes)%8]:uint16_t(0x1800+rng(state)%0x1000);packed[at]=uint8_t(scale);packed[at+1]=uint8_t(scale>>8);}
 }
 return arithmetic::is_expanded(variant)?iq3::expanded::expand(type,packed.data(),packed.size(),k):packed;
}
std::vector<uint16_t> inputs(unsigned k,unsigned mode){
 std::vector<uint16_t> x(k);constexpr uint16_t tiny[]{0,0x8000,1,0x8001,0x007f,0x807f,0x0080,0x8080};
 constexpr uint16_t extreme[]{0,0x8000,0x4f00,0xcf00,0x3000,0xb000,0x3f80,0xbf80};
 for(unsigned i=0;i<k;++i){x[i]=iq3::bf16_bits(float(int(i*17%127)-63)/128.f);if(mode==1)x[i]=i%2?0x8000:0;if(mode==2)x[i]=tiny[i%8];if(mode==3)x[i]=extreme[i%8];}
 return x;
}
} // namespace

int main(int argc,char** argv){
 std::filesystem::path out;std::unique_ptr<Runner> runner;bool authorized=false;unsigned checks=0;
 try{
  unsigned card=0,seconds=300;
  for(int i=1;i<argc;++i){std::string arg=argv[i];
   if(arg=="--output"&&i+1<argc)out=argv[++i];
   else if(arg=="--card"&&i+1<argc)card=std::stoul(argv[++i]);
   else if(arg=="--seconds"&&i+1<argc)seconds=std::stoul(argv[++i]);
   else if(arg=="--stop-fd"&&i+1<argc)ownrt::set_stop_channel(std::stoi(argv[++i]));
   else if(arg=="--authorized-device-window")authorized=true;
   else throw std::invalid_argument("p33 linked fixture arguments");
  }
  check(!out.empty(),"--output required");check(seconds>=300&&seconds<=86400,"--seconds must be 300..86400");
#ifdef OWN_RT_HOST_ONLY
  check(!authorized,"host binary cannot accept device authorization");
#else
  check(authorized,"device authorization required");
#endif
  // Authorization refusal happens before creating a Device or opening output.
  std::filesystem::create_directories(out);
  std::ofstream bytes(out/"output.bin",std::ios::binary),cases(out/"cases.jsonl");check(bool(bytes)&&bool(cases),"fixture output files");
  runner=std::make_unique<Runner>(card,seconds);std::vector<uint8_t> all_output;
  std::set<std::string> instantiations;unsigned output_rows=0;
  for(auto type:{iq3::Type::Q6_K,iq3::Type::Q8_0,iq3::Type::F32,iq3::Type::BF16})
  for(unsigned k:{320u,640u,2560u,6144u,10240u}){
   if(k%iq3::layout(type).elements)continue;
   for(unsigned split:{1u,4u}){
    const unsigned variant=(type==iq3::Type::F32||type==iq3::Type::BF16)?(split==1?0:4):(split==1?6:7);
    const std::string identity=std::string(type_name(type))+"/K"+std::to_string(k)+"/split"+std::to_string(split);
    instantiations.insert(identity);
    for(unsigned mode=0;mode<6;++mode){
     runner->between_cases();auto& r=*runner;unsigned rows=mode==4?9:mode==5?1:8;
     const size_t rb=arithmetic::row_bytes(type,k,variant);
     auto w=weights(type,k,rows,variant,mode);auto x=inputs(k,mode);check(w.size()==rows*rb,"fixture weight extent");
     std::vector<uint16_t> expected(rows);
     for(unsigned row=0;row<rows;++row)expected[row]=iq3::bf16_bits(arithmetic::row(type,w.data()+row*rb,x.data(),k,variant));
     Matrix m{};m.type=type;m.w=r.upload(w.data(),w.size());m.x=r.upload(x.data(),x.size()*2);m.y=r.alloc(rows*2);m.rows=rows;m.columns=k;m.experts=1;m.count=1;m.span=rows;m.workspace=r.alloc(rows*8*4);
     auto host=r.alloc(rows*2,Memory::pinned);const auto launch=p33::submit(r.device,{m},"p33.dense.segment",false,variant);r.finish(launch.last);r.finish(r.copy.copy(host,0,m.y,0,rows*2,{}));
     const auto* actual=static_cast<const uint8_t*>(r.device.arena.row(host).pointer);
     check(std::memcmp(actual,expected.data(),rows*2)==0,"p33 reference mismatch "+identity+" mode="+std::to_string(mode));
     bytes.write(reinterpret_cast<const char*>(actual),rows*2);all_output.insert(all_output.end(),actual,actual+rows*2);
     cases<<"{\"candidate\":\"p33.dense.segment\",\"identity\":"<<quote(identity)<<",\"type\":"<<quote(type_name(type))<<",\"columns\":"<<k<<",\"split\":"<<split<<",\"variant\":"<<variant<<",\"mode\":"<<mode<<",\"rows\":"<<rows<<",\"bytes_equal\":true,\"output_sha256\":"<<quote(packet26::hash(actual,rows*2))<<"}\n";
     ++checks;output_rows+=rows;r.clear();
    }
   }
  }
  check(instantiations.size()==36&&checks==216&&output_rows==1512,"all p33 dense linked instantiations required");
  bytes.close();cases.close();check(bool(bytes)&&bool(cases),"fixture output flush");
  const auto shutdown=runner->device.shutdown(std::chrono::seconds(60));check(shutdown.safe_to_exit&&shutdown.exit_code==0,"p33 linked fixture teardown");
  std::ofstream receipt(out/"receipt.json");
  receipt<<"{\"schema\":\"packet37.p33-linked-fixtures.v1\",\"passed\":true,\"device_executed\":"<<(authorized?"true":"false")<<",\"diagnostic\":true,\"device_speed_claim\":false,\"reference_exact\":true,\"checks\":"<<checks<<",\"type_k_families\":18,\"split_instantiations\":36,\"modes_per_instantiation\":6,\"output_rows\":"<<output_rows<<",\"argument_limit_bytes\":1024,\"owner_cards\":1,\"card\":"<<card<<",\"output_sha256\":"<<quote(packet26::hash(all_output.data(),all_output.size()))<<",\"teardown\":"<<shutdown.json()<<"}\n";
  receipt.close();check(bool(receipt),"fixture receipt flush");std::cout<<checks<<" p33 linked fixture checks PASS\n";return 0;
 }catch(const std::exception& error){
  std::cerr<<error.what()<<'\n';
  if(runner){std::ofstream(out/"receipt.json")<<"{\"schema\":\"packet37.p33-linked-fixtures.v1\",\"passed\":false,\"device_executed\":"<<(authorized?"true":"false")<<",\"checks\":"<<checks<<",\"error\":"<<quote(error.what())<<"}\n";packet26::failure(runner->device,out,error.what());}
  return 1;
 }
}
