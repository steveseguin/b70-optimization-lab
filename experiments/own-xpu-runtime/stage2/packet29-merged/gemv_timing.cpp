#include "k2_failure.hpp"
#include "fixture_validation.hpp"
#include "adapter_fixture.hpp"
#include "performance.hpp"
#include "failure.hpp"
#include "dispatch.hpp"
#include "p25_bridge.hpp"
#include "p28/submit.hpp"
#include "expert_down.hpp"
#include <fstream>
#include <cstring>
#include <array>
#include <vector>
#include <algorithm>
#include <iostream>
namespace {
using namespace ownrt;using namespace integrated;
using Shape=p28::Shape;
constexpr auto& shapes=p28::shapes;
uint32_t rng(uint32_t& s){s^=s<<13;s^=s>>17;s^=s<<5;return s;}
std::vector<uint8_t> seed(const Shape& s,unsigned salt,unsigned v,unsigned mode=0){auto fmt=iq3::layout(s.type);std::vector<uint8_t> packed(8*(s.k/fmt.elements)*fmt.bytes);uint32_t state=0x23456789u+salt;for(auto& b:packed)b=rng(state);for(size_t off=0;off<packed.size();off+=fmt.bytes){size_t at=off+(s.type==iq3::Type::Q6_K?208:0);uint16_t half=uint16_t(0x1800+rng(state)%0x1000);if(mode==2){constexpr uint16_t special[]{0,0x8000,1,0x8001,0x03ff,0x83ff,0x0400,0x8400};half=special[(off/fmt.bytes)%8];}packed[at]=half&255;packed[at+1]=half>>8;}if(s.type==iq3::Type::F32||s.type==iq3::Type::BF16){for(size_t off=0;off<packed.size();off+=fmt.bytes){float value=float(int((off/fmt.bytes)*13%127)-63)/128.f;if(s.type==iq3::Type::F32){auto bits=std::bit_cast<uint32_t>(value);std::memcpy(packed.data()+off,&bits,4);}else{auto bits=iq3::bf16_bits(value);std::memcpy(packed.data()+off,&bits,2);}}}return arithmetic::is_expanded(v)?iq3::expanded::expand(s.type,packed.data(),packed.size(),s.k):packed;}
#ifdef OWN_RT_HOST_ONLY
struct Cpu:Backend {
 std::string identity()const override{return "CPU packet26 GEMV fixture";}
 void* allocate(size_t n,Memory)override{return ::operator new(n,std::align_val_t(64));}void release(void* p,Memory)override{::operator delete(p,std::align_val_t(64));}
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
 for(auto s:shapes){auto& r=*runner;unsigned experts=s.count>1?512:1,v=arithmetic::r5_variant(s.type,s.rows,s.k,experts,false);auto rb=arithmetic::row_bytes(s.type,s.k,v);if(!timing&&s.type!=iq3::Type::IQ4_NL)s.rows=8;auto selected=packet26::dispatch.gemv_for(s.klass);bool candidate_available=!selected.empty()&&selected!="r5";
 for(unsigned mode=0;mode<(!timing?6u:1u);++mode){
  if(!timing&&s.type!=iq3::Type::IQ4_NL)s.rows=mode==4?9:8;
  std::vector<uint16_t> x(size_t(s.k)*(s.paired?1:s.count));for(size_t i=0;i<x.size();++i){x[i]=iq3::bf16_bits(float(int(i*17%127)-63)/128.f);if(mode==1)x[i]=i%2?0x8000:0;if(mode==2){constexpr uint16_t tiny[]{0,0x8000,1,0x8001,0x007f,0x807f,0x0080,0x8080};x[i]=tiny[i%8];}if(mode==3){constexpr uint16_t extreme[]{0,0x8000,0x4f00,0xcf00,0x3000,0xb000,0x3f80,0xbf80};x[i]=extreme[i%8];}}
  auto xid=r.upload(x.data(),x.size()*2);constexpr unsigned ids[]{1,1,7,3,3,0,9,2,5,4};std::array<iq3::Route,10> routes{};for(unsigned j=0;j<s.count;++j)routes[j]={timing?j:ids[j],0,(!timing&&s.type==iq3::Type::IQ4_NL)?8u:s.rows};if(!timing&&mode==5&&s.count>1){routes[0]={experts,0,1};routes[1]={0,s.rows-1,2};routes[2]={0,0,0};routes[3]={1,1,3};routes[4]={experts-1,2,4};}auto rid=s.count>1?r.upload(routes.data(),s.count*sizeof(iq3::Route)):Allocation(0);
  const size_t payload=size_t(s.count)*s.rows*rb*(s.paired?2:1);const bool heavy=timing&&payload>8000000;const unsigned copies=heavy?8:1;
  std::vector<Allocation> route_banks(copies,rid);if(s.count>1)for(unsigned copy=1;copy<copies;++copy){auto shifted=routes;for(auto& route:shifted)route.expert_id+=copy*10;route_banks[copy]=r.upload(shifted.data(),s.count*sizeof(iq3::Route));}
  std::vector<std::vector<Matrix>> banks(copies);std::vector<Matrix> matrices;std::vector<std::vector<uint16_t>> expected;std::vector<Allocation> hosts,status_hosts;
  for(unsigned projection=0;projection<(s.paired?2u:1u);++projection){auto eight=seed(s,projection,v,mode);size_t weight_bytes=size_t(experts)*s.rows*rb;std::vector<uint8_t> weights(fixture_validation::only?0:weight_bytes);if(!fixture_validation::only)for(size_t row=0;row<size_t(experts)*s.rows;++row)std::memcpy(weights.data()+row*rb,eight.data()+(row%8)*rb,rb);
   Matrix m{};m.type=s.type;m.w=r.upload(weights.data(),weight_bytes);m.x=xid;m.y=r.alloc(size_t(s.count)*s.rows*2);m.rows=s.rows;m.columns=s.k;m.experts=experts;m.count=s.count;m.span=s.rows;m.routes=rid;m.status=s.count>1?r.alloc(s.count*4):Allocation(0);m.workspace=r.alloc(std::max(size_t(s.count)*s.rows*8*4,s.paired?size_t(2)*s.count*s.rows*(s.k/iq3::layout(s.type).elements)*4:size_t(0)));
#ifdef OWN_RT_HOST_ONLY
   if(fixture_validation::poison_dense&&s.count==1)m.status=r.alloc(4);
#endif
   matrices.push_back(m);for(unsigned copy=0;copy<copies;++copy){auto rotated=m;if(copy){if(s.count==1)rotated.w=r.upload(weights.data(),weight_bytes);else rotated.routes=route_banks[copy];}banks[copy].push_back(rotated);}hosts.push_back(r.alloc(size_t(s.count)*s.rows*2,Memory::pinned));status_hosts.push_back(s.count>1?r.alloc(s.count*4,Memory::pinned):Allocation(0));
   std::vector<uint16_t> oracle(size_t(s.count)*s.rows);if(!fixture_validation::only)for(unsigned slot=0;slot<s.count;++slot){uint16_t cache[8];for(unsigned row=0;row<8;++row)cache[row]=iq3::bf16_bits(arithmetic::row(s.type,eight.data()+row*rb,x.data()+(s.paired?0:size_t(slot)*s.k),s.k,v));for(unsigned row=0;row<s.rows;++row)oracle[size_t(slot)*s.rows+row]=(s.count>1&&(!iq3::valid_route(routes[slot],experts,s.rows,s.rows)||row>=routes[slot].row_count))?uint16_t(0x7fc0):cache[((s.count>1?size_t(routes[slot].expert_id)*s.rows+routes[slot].row_begin:0)+row)%8];}expected.push_back(std::move(oracle));
  }
  auto candidates=(s.type==iq3::Type::F32||s.type==iq3::Type::BF16)?std::vector<std::string>{}:packet26::p25bridge::alternatives(s.type);auto added=p28::candidates(s.type);candidates.insert(candidates.end(),added.begin(),added.end());if(s.type==iq3::Type::IQ4_NL)candidates.insert(candidates.end(),{"p29.down.wg32","p29.down.rows4"});
  auto fp32=r.alloc(x.size()*4);
  for(const auto& candidate:candidates){selected=candidate;candidate_available=!selected.empty()&&selected!="r5";
  if(candidate=="p25.half_table")for(unsigned mutation=0;mutation<3;++mutation){auto bad=matrices;bad[0].workspace=mutation==0?Allocation(0):mutation==1?xid:bad[0].w;bool rejected=false;try{packet26::p25bridge::submit(r.device,bad,candidate,s.paired,v);}catch(const std::invalid_argument&){rejected=true;}if(!rejected)throw std::runtime_error("half_table accepted missing/undersized/aliased workspace");++checks;}

  for(unsigned timing_mode=0;timing_mode<(heavy?2u:1u);++timing_mode){const bool rotated=timing_mode==1;
  std::vector<double> elapsed[2];bool excluded[2]{};for(unsigned iteration=0;iteration<(timing&&!fixture_validation::only?216u:1u);++iteration)for(unsigned variant=0;variant<2;++variant){if(excluded[variant])continue;const bool measuring=timing&&!fixture_validation::only&&iteration>=8&&iteration<208;const unsigned repetition=iteration<8?iteration:iteration<208?iteration-8:iteration-208;try{fixture_validation::inject_failure(std::string("gemv:")+s.klass,variant);const unsigned buffer_copy=rotated?(repetition+variant*4)%copies:0;auto& current=banks[buffer_copy];Launch prep{};if(variant&&selected=="p27.fp32_input")prep=packet26::p25bridge::prepare_input(r.device,xid,fp32,x.size());auto launched=variant&&candidate_available?(selected.starts_with("p28.")?p28::submit(r.device,current,selected,s.paired,v):selected.starts_with("p29.")?p29::submit(r.device,current,selected,s.paired,v):packet26::p25bridge::submit(r.device,current,selected,s.paired,v,fp32)):(s.count>1?integrated::experts(r.device,current,s.paired):dense(r.device,current[0],v));if(prep.first)launched.first=prep.first;r.finish(launched.last);std::vector<std::pair<Event,EventTiming>> times;for(Event event=launched.first;event<=launched.last;++event)times.push_back({event,r.device.timing(event)});
   if(!measuring)for(size_t j=0;j<matrices.size();++j){size_t bytes=expected[j].size()*2;r.finish(r.copy.copy(hosts[j],0,matrices[j].y,0,bytes,{}));if(!fixture_validation::only&&std::memcmp(r.device.arena.row(hosts[j]).pointer,expected[j].data(),bytes)){auto actual=static_cast<const uint16_t*>(r.device.arena.row(hosts[j]).pointer);size_t at=0;while(at<expected[j].size()&&actual[at]==expected[j][at])++at;throw std::runtime_error(std::string("GEMV exactness: ")+s.label+" mode="+std::to_string(mode)+" variant="+std::to_string(variant)+" projection="+std::to_string(j)+" element="+std::to_string(at)+" expected_bf16="+std::to_string(expected[j][at])+" actual_bf16="+std::to_string(actual[at]));}if(s.count>1){r.finish(r.copy.copy(status_hosts[j],0,matrices[j].status,0,s.count*4,{}));if(!fixture_validation::only){auto status=static_cast<const uint32_t*>(r.device.arena.row(status_hosts[j]).pointer);for(unsigned slot=0;slot<s.count;++slot)if(status[slot]!=unsigned(!iq3::valid_route(routes[slot],experts,s.rows,s.rows)))throw std::runtime_error("GEMV route status differs");}}if(!timing)fixture_bytes.write(static_cast<const char*>(r.device.arena.row(hosts[j]).pointer),bytes);}
   double sum_us=0;for(auto [event,t]:times)sum_us+=double(t.end_ns-t.start_ns)/1000.;if(measuring)elapsed[variant].push_back(sum_us);
   if(measuring||fixture_validation::only)for(auto [event,t]:times)events<<"{\"class\":"<<quote(std::string("gemv:")+s.klass)<<",\"workload\":"<<quote(s.label)<<",\"variant\":\""<<(variant?"specialised":"packet18")<<"\",\"implementation\":"<<quote(variant&&candidate_available?selected:"r5")<<",\"timing_mode\":"<<quote(rotated?"rotated":"reread")<<",\"rotation_copies\":"<<copies<<",\"buffer_copy\":"<<buffer_copy<<",\"full_payload_bytes\":"<<payload<<",\"payload_bytes\":"<<payload<<",\"candidate\":"<<quote(candidate)<<",\"kernel_identity\":"<<quote(variant?selected+":"+s.label+":v"+std::to_string(v):std::string("runtime.r5:")+s.label+":v"+std::to_string(v))<<",\"same_kernel\":false,\"bytes_equal\":true,\"equality_check\":\"untimed-preflight-and-postflight-all-eight-copies\",\"candidate_available\":"<<(candidate_available?"true":"false")<<",\"repetition\":"<<repetition<<",\"event\":"<<event<<",\"stage_count\":"<<times.size()<<",\"start_ns\":"<<t.start_ns<<",\"end_ns\":"<<t.end_ns<<",\"exact\":true}\n";
   if(fixture_validation::only)std::ofstream(out/"validation-entries.jsonl",std::ios::app)<<"{\"class\":"<<quote(s.klass)<<",\"workload\":"<<quote(s.label)<<",\"candidate\":"<<quote(variant&&candidate_available?selected:"r5")<<",\"rows\":"<<s.rows<<",\"columns\":"<<s.k<<",\"count\":"<<s.count<<",\"mode\":"<<mode<<"}\n";
   r.device.retire_completed_events();++checks;
   }catch(const std::exception& e){if(!timing||(fixture_validation::only&&!dynamic_cast<const fixture_validation::InjectedFailure*>(&e)))throw;packet26::candidate_failure(out,std::string("gemv:")+s.klass,variant?"specialised":"packet18",s.label,e,variant&&candidate_available?selected:"r5");excluded[variant]=true;r.device.retire_completed_events();}
  }
  if(timing&&!fixture_validation::only){std::cout<<"GEMV "<<s.label<<" candidate="<<candidate<<" timing_mode="<<(rotated?"rotated":"reread")<<" same_kernel=false bytes_equal="<<(!excluded[0]&&!excluded[1]?"true":"false");for(unsigned arm=0;arm<2;++arm){auto a=elapsed[arm];std::sort(a.begin(),a.end());if(!a.empty())std::cout<<(arm?" candidate":" runtime.R5")<<" median_us="<<(a[(a.size()-1)/2]+a[a.size()/2])/2<<" p90_us="<<a[size_t(.9*(a.size()-1))];}std::cout<<std::endl;}
  }}r.clear();
 }
 }
 auto state=runner->device.shutdown(std::chrono::seconds(60));if(!state.safe_to_exit||state.exit_code)throw std::runtime_error("GEMV K2 teardown");return {checks,runner->maximum,state.json()};
 }catch(const std::exception& error){std::ofstream(out/"gemv-failure.json")<<"{\"passed\":false,\"error\":"<<ownrt::quote(error.what())<<"}\n";packet26::failure(runner->device,out,error.what());throw;}
}
AdapterFixtureReceipt gemv_timing_gate(unsigned card,const std::filesystem::path& out){return gemv_gate(card,out,true);}
AdapterFixtureReceipt gemv_fixture_gate(unsigned card,const std::filesystem::path& out){return gemv_gate(card,out,false);}
