#include "k2_failure.hpp"
#include "fixture_validation.hpp"
#include "adapter_fixture.hpp"
#include "performance.hpp"
#include "failure.hpp"
#include "dispatch.hpp"
#include "p25_bridge.hpp"
#include <fstream>
#include <cstring>
#include <array>
#include <vector>
#include <algorithm>
namespace {
using namespace ownrt;using namespace integrated;
struct Shape {const char* label;const char* klass;iq3::Type type;unsigned rows,k,count;bool paired;};
// Production geometry/type identities from packet25 fixtures and this packet's plan.tsv.
// K1 GEMV modes: finite varied, signed zero, finite subnormal, finite extreme.
// Nonfinite GEMV weights/activations are NOT qualified; see NONFINITE-GEMV.md.
constexpr Shape shapes[]{
 {"expsgate.iq2","expsgate",iq3::Type::IQ2_S,640,2560,10,true},
 {"expsgate.iq3","expsgate",iq3::Type::IQ3_S,640,2560,10,true},
 {"expsdown","expsdown",iq3::Type::IQ4_NL,2560,640,10,false},
 {"gdn.qkv.q6","gdn.qkv",iq3::Type::Q6_K,10240,2560,1,false},
 {"gdn.qkv.q8","gdn.qkv",iq3::Type::Q8_0,10240,2560,1,false},
 {"gdn.z.q6","gdn.z",iq3::Type::Q6_K,6144,2560,1,false},
 {"gdn.z.q8","gdn.z",iq3::Type::Q8_0,6144,2560,1,false},
 {"qsa.qgate","qsa.qgate",iq3::Type::Q6_K,12288,2560,1,false},
 {"qsa.k","qsa.k",iq3::Type::Q6_K,512,2560,1,false},
 {"qsa.v","qsa.v",iq3::Type::Q6_K,512,2560,1,false},
 {"attention.gdn","attention",iq3::Type::Q6_K,2560,6144,1,false},
 {"attention.qsa","attention",iq3::Type::Q6_K,2560,6144,1,false},
 {"ple.key","ple.key",iq3::Type::Q8_0,10240,2560,1,false},
 {"ple.value","ple.value",iq3::Type::Q8_0,2560,2560,1,false},
 {"hc.gate","hc.gate",iq3::Type::Q8_0,10240,320,1,false},
 {"hc.low","hc.low",iq3::Type::Q8_0,320,10240,1,false},
 {"logits","logits",iq3::Type::Q6_K,248320,2560,1,false}
};
uint32_t rng(uint32_t& s){s^=s<<13;s^=s>>17;s^=s<<5;return s;}
std::vector<uint8_t> seed(const Shape& s,unsigned salt,unsigned v,unsigned mode=0){auto fmt=iq3::layout(s.type);std::vector<uint8_t> packed(8*(s.k/fmt.elements)*fmt.bytes);uint32_t state=0x23456789u+salt;for(auto& b:packed)b=rng(state);for(size_t off=0;off<packed.size();off+=fmt.bytes){size_t at=off+(s.type==iq3::Type::Q6_K?208:0);uint16_t half=uint16_t(0x1800+rng(state)%0x1000);if(mode==2){constexpr uint16_t special[]{0,0x8000,1,0x8001,0x03ff,0x83ff,0x0400,0x8400};half=special[(off/fmt.bytes)%8];}packed[at]=half&255;packed[at+1]=half>>8;}return arithmetic::is_expanded(v)?iq3::expanded::expand(s.type,packed.data(),packed.size(),s.k):packed;}
#ifdef OWN_RT_HOST_ONLY
struct Cpu:Backend {
 std::string identity()const override{return "CPU packet26 GEMV fixture";}
 void* allocate(size_t n,Memory)override{return ::operator new(n);}void release(void* p,Memory)override{::operator delete(p);}
 Event copy(void* a,const void* b,size_t n,std::span<const Event>)override{if(!fixture_validation::only)std::memcpy(a,b,n);return next_handle();}Event marker(std::span<const Event>)override{return next_handle();}
 Event compute(const Operation& op,std::span<void*const> p,std::span<const Event>)override{if(!fixture_validation::only)dynamic_cast<const HostOperation&>(op).run(p);return next_handle();}
 bool complete(Event)override{return true;}bool wait(Event,Deadline)override{return true;}EventTiming timing(Event)override{return {0,0};}
 void synchronize()override{}void clear_events()override{}void close_queue()override{}void close_context()override{}
};
#endif
struct Runner {
 Device device;CopyEngine copy;std::vector<Allocation> owned;size_t serial=0;uint64_t maximum=0;
 static std::unique_ptr<Backend> backend(unsigned card){
#ifdef OWN_RT_HOST_ONLY
 (void)card;return std::make_unique<Cpu>();
#else
 return make_sycl_device(card,true);
#endif
 }
 explicit Runner(unsigned card):device(backend(card)),copy(device){}
 Allocation alloc(size_t n,Memory m=Memory::device){auto id=device.arena.allocate("gemv-k2-"+std::to_string(serial++),n,m,Category::scratch,Lifetime::transaction);owned.push_back(id);return id;}
 void finish(Event e){if(!device.wait(e,std::chrono::seconds(300)))throw std::runtime_error("GEMV K2 submission timeout");auto t=device.timing(e);if(t.end_ns>t.start_ns)maximum=std::max(maximum,t.end_ns-t.start_ns);}
 Allocation upload(const void* src,size_t bytes){auto h=alloc(std::min(bytes,size_t(4*1024*1024)),Memory::pinned),d=alloc(bytes);for(size_t off=0;off<bytes;off+=4*1024*1024){size_t n=std::min(bytes-off,size_t(4*1024*1024));if(!fixture_validation::only)std::memcpy(device.arena.row(h).pointer,static_cast<const uint8_t*>(src)+off,n);finish(copy.copy(d,off,h,0,n,{}));}return d;}
 void clear(){device.retire_completed_events();for(auto id:owned)device.arena.release(id);owned.clear();}
};
}
static AdapterFixtureReceipt gemv_gate(unsigned card,const std::filesystem::path& out,bool timing){
#ifdef OWN_RT_HOST_ONLY
 if(timing&&!fixture_validation::only)throw std::runtime_error("GEMV K2 is a coordinator-only device timing window");
#endif
 auto runner=std::make_unique<Runner>(card);unsigned checks=0;try{std::ofstream events(out/"events.jsonl",std::ios::app),fixture_bytes;if(!timing)fixture_bytes.open(out/"output.bin",std::ios::binary|std::ios::app);
 for(auto s:shapes){auto& r=*runner;unsigned experts=s.count>1?512:1,v=arithmetic::r5_variant(s.type,s.rows,s.k,experts,false);auto rb=arithmetic::row_bytes(s.type,s.k,v);if(!timing)s.rows=8;auto selected=packet26::dispatch.gemv_for(s.klass);bool candidate_available=!selected.empty()&&selected!="r5";
 for(unsigned mode=0;mode<(!timing?4u:1u);++mode){
  std::vector<uint16_t> x(size_t(s.k)*(s.paired?1:s.count));for(size_t i=0;i<x.size();++i){x[i]=iq3::bf16_bits(float(int(i*17%127)-63)/128.f);if(mode==1)x[i]=i%2?0x8000:0;if(mode==2){constexpr uint16_t tiny[]{0,0x8000,1,0x8001,0x007f,0x807f,0x0080,0x8080};x[i]=tiny[i%8];}if(mode==3){constexpr uint16_t extreme[]{0,0x8000,0x4f00,0xcf00,0x3000,0xb000,0x3f80,0xbf80};x[i]=extreme[i%8];}}
  auto xid=r.upload(x.data(),x.size()*2);constexpr unsigned ids[]{1,1,7,3,3,0,9,2,5,4};std::array<iq3::Route,10> routes{};for(unsigned j=0;j<s.count;++j)routes[j]={ids[j],0,s.rows};auto rid=s.count>1?r.upload(routes.data(),s.count*sizeof(iq3::Route)):Allocation(0);
  std::vector<Matrix> matrices;std::vector<std::vector<uint16_t>> expected;std::vector<Allocation> hosts;
  for(unsigned projection=0;projection<(s.paired?2u:1u);++projection){auto eight=seed(s,projection,v,mode);size_t weight_bytes=size_t(experts)*s.rows*rb;std::vector<uint8_t> weights(fixture_validation::only?0:weight_bytes);if(!fixture_validation::only)for(size_t row=0;row<size_t(experts)*s.rows;++row)std::memcpy(weights.data()+row*rb,eight.data()+(row%8)*rb,rb);
   Matrix m{};m.type=s.type;m.w=r.upload(weights.data(),weight_bytes);m.x=xid;m.y=r.alloc(size_t(s.count)*s.rows*2);m.rows=s.rows;m.columns=s.k;m.experts=experts;m.count=s.count;m.span=s.rows;m.routes=rid;m.status=s.count>1?r.alloc(s.count*4):Allocation(0);m.workspace=r.alloc(size_t(s.count)*s.rows*4*4);
#ifdef OWN_RT_HOST_ONLY
   if(fixture_validation::poison_dense&&s.count==1)m.status=r.alloc(4);
#endif
   matrices.push_back(m);hosts.push_back(r.alloc(size_t(s.count)*s.rows*2,Memory::pinned));
   std::vector<uint16_t> oracle(size_t(s.count)*s.rows);if(!fixture_validation::only)for(unsigned slot=0;slot<s.count;++slot){uint16_t cache[8];for(unsigned row=0;row<8;++row)cache[row]=iq3::bf16_bits(arithmetic::row(s.type,eight.data()+row*rb,x.data()+(s.paired?0:size_t(slot)*s.k),s.k,v));for(unsigned row=0;row<s.rows;++row)oracle[size_t(slot)*s.rows+row]=cache[((s.count>1?size_t(ids[slot])*s.rows:0)+row)%8];}expected.push_back(std::move(oracle));
  }
  std::vector<std::string> candidates{selected};
  if(fixture_validation::only)candidates=s.count==1?std::vector<std::string>{"r5","p25.rows4","p25.wide8","p25.scale8"}:std::vector<std::string>{"r5","p25.rows4","p25.wg32","p25.private_decode",s.type==iq3::Type::IQ4_NL?"p25.wide8":"p25.paired_input"};
  for(const auto& candidate:candidates){selected=candidate;candidate_available=!selected.empty()&&selected!="r5";
  bool excluded[2]{};for(unsigned repetition=0;repetition<(timing&&!fixture_validation::only?200u:1u);++repetition)for(unsigned variant=0;variant<2;++variant){if(excluded[variant])continue;try{fixture_validation::inject_failure(std::string("gemv:")+s.klass,variant);auto launched=variant&&candidate_available?packet26::p25bridge::submit(r.device,matrices,selected,s.paired,v):(s.count>1?integrated::experts(r.device,matrices,s.paired):dense(r.device,matrices[0],v));r.finish(launched.last);std::vector<std::pair<Event,EventTiming>> times;for(Event event=launched.first;event<=launched.last;++event)times.push_back({event,r.device.timing(event)});
   for(size_t j=0;j<matrices.size();++j){size_t bytes=expected[j].size()*2;r.finish(r.copy.copy(hosts[j],0,matrices[j].y,0,bytes,{}));if(!fixture_validation::only&&std::memcmp(r.device.arena.row(hosts[j]).pointer,expected[j].data(),bytes)){auto actual=static_cast<const uint16_t*>(r.device.arena.row(hosts[j]).pointer);size_t at=0;while(at<expected[j].size()&&actual[at]==expected[j][at])++at;throw std::runtime_error(std::string("GEMV exactness: ")+s.label+" mode="+std::to_string(mode)+" variant="+std::to_string(variant)+" projection="+std::to_string(j)+" element="+std::to_string(at)+" expected_bf16="+std::to_string(expected[j][at])+" actual_bf16="+std::to_string(actual[at]));}if(!timing)fixture_bytes.write(static_cast<const char*>(r.device.arena.row(hosts[j]).pointer),bytes);}
   if(timing)for(auto [event,t]:times)events<<"{\"class\":"<<quote(std::string("gemv:")+s.klass)<<",\"workload\":"<<quote(s.label)<<",\"variant\":\""<<(variant?"specialised":"packet18")<<"\",\"implementation\":"<<quote(variant&&candidate_available?selected:"r5")<<",\"candidate_available\":"<<(candidate_available?"true":"false")<<",\"repetition\":"<<repetition<<",\"event\":"<<event<<",\"start_ns\":"<<t.start_ns<<",\"end_ns\":"<<t.end_ns<<",\"exact\":true}\n";
   if(fixture_validation::only)std::ofstream(out/"validation-entries.jsonl",std::ios::app)<<"{\"class\":"<<quote(s.klass)<<",\"workload\":"<<quote(s.label)<<",\"candidate\":"<<quote(variant&&candidate_available?selected:"r5")<<",\"rows\":"<<s.rows<<",\"columns\":"<<s.k<<",\"count\":"<<s.count<<",\"mode\":"<<mode<<"}\n";
   r.device.retire_completed_events();++checks;
   }catch(const std::exception& e){if(!timing||(fixture_validation::only&&!dynamic_cast<const fixture_validation::InjectedFailure*>(&e)))throw;packet26::candidate_failure(out,std::string("gemv:")+s.klass,variant?"specialised":"packet18",s.label,e,variant&&candidate_available?selected:"r5");excluded[variant]=true;r.device.retire_completed_events();}
  }}r.clear();
 }
 }
 auto state=runner->device.shutdown(std::chrono::seconds(60));if(!state.safe_to_exit||state.exit_code)throw std::runtime_error("GEMV K2 teardown");return {checks,runner->maximum,state.json()};
 }catch(const std::exception& error){std::ofstream(out/"gemv-failure.json")<<"{\"passed\":false,\"error\":"<<ownrt::quote(error.what())<<"}\n";packet26::failure(runner->device,out,error.what());throw;}
}
AdapterFixtureReceipt gemv_timing_gate(unsigned card,const std::filesystem::path& out){return gemv_gate(card,out,true);}
AdapterFixtureReceipt gemv_fixture_gate(unsigned card,const std::filesystem::path& out){return gemv_gate(card,out,false);}
