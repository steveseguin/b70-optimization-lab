#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p49b_expert_fixture.cpp"
// Actual owner submissions for the qualified expert formats and both verification rows.
// This is correctness evidence, never a speed benchmark.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/build/checked/experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/p49b_expert_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/build/checked/experiments/own-xpu-runtime/stage2/packet184-twocard-checkpoint/failure.hpp"
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
 std::string identity()const override{return "CPU packet49b compact expert fixture";}
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
 Allocation alloc(size_t n,Memory m=Memory::device){auto id=device.arena.allocate("p49b-expert-"+std::to_string(serial++),n,m,Category::scratch,Lifetime::transaction);owned.push_back(id);return id;}
 void finish(Event e){check(device.wait(e,wait_limit),"p49b expert fixture submission deadline");}
 Allocation upload(const void* src,size_t bytes){auto host=alloc(bytes,Memory::pinned),out=alloc(bytes);std::memcpy(device.arena.row(host).pointer,src,bytes);finish(copy.copy(out,0,host,0,bytes,{}));return out;}
 void clear(){device.retire_completed_events();for(auto id:owned)device.arena.release(id);owned.clear();}
 void between_cases(){check(Clock::now()<deadline,"p49b expert fixture total deadline");}
};
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
   else throw std::invalid_argument("p49b expert fixture arguments");
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
  auto exercise=[&]<iq3::Type T,unsigned K,p39::Kind E>(){
   constexpr bool paired=E==p39::Kind::expert_checks;constexpr unsigned rows=paired?4:2560,experts=10,count=10;
   const size_t raw_stride=p49bgemv::source_row_bytes(T,K),stride=p49bgemv::layout(T,K).row_bytes;
   std::vector<uint8_t> raw(rows*experts*raw_stride),peer(raw.size());uint32_t seed=0x49b;
   for(auto* v:{&raw,&peer}){for(auto& byte:*v){seed=seed*1664525u+1013904223u;byte=seed>>24;}
    auto block=iq3::layout(T);for(size_t i=0;i<v->size();i+=block.bytes){(*v)[i]=0;(*v)[i+1]=0x24;}}
   std::vector<uint8_t> packed(rows*experts*stride),packed_peer(packed.size());
   for(size_t i=0;i<rows*experts;++i){p49bgemv::repack_row(T,K,raw.data()+i*raw_stride,packed.data()+i*stride);p49bgemv::repack_row(T,K,peer.data()+i*raw_stride,packed_peer.data()+i*stride);}
   // Repacking refuses nonfinite weights before touching the destination.
   auto bad=raw;bad[0]=0;bad[1]=0x7c;auto sentinel=packed;bool refused=false;
   try{p49bgemv::repack_row(T,K,bad.data(),sentinel.data());}catch(const std::invalid_argument&){refused=true;}
   check(refused&&sentinel==packed,"nonfinite scale must refuse without writes");
   for(unsigned batch:{1u,2u})for(unsigned scenario=0;scenario<8;++scenario)for(unsigned token=0;token<batch;++token){
    auto&r=*runner;r.between_cases();
    std::vector<uint16_t> x(K*(paired?1:count));for(size_t i=0;i<x.size();++i)x[i]=iq3::bf16_bits(float(int((i+token*7)%17)-8)/32.f);
    if(scenario==5)x[0]=0x7fc1;if(scenario==6){x[0]=0x7f80;x[8]=0xff80;}if(scenario==7){x[0]=1;x[1]=0x8001;}
    std::vector<iq3::Route> routes(count);for(unsigned i=0;i<count;++i)routes[i]={uint32_t((i+token)%experts),0,scenario==0?rows:4};
    if(scenario>=1&&scenario<=3)routes[2].expert_id=experts;
    if(scenario==4){routes[0].row_count=0;routes[1].row_count=2;routes[1].row_begin=1;}
    std::vector<uint16_t> y(rows*count,0x7e31),py(rows*count,0x7e32);std::vector<uint32_t> status(count,9),peer_status(count,8);
    uint32_t active=scenario==2?0:1,error=scenario==3?7:0,position=0;
    p39::Bound expected{};expected.w=raw.data();expected.peer=peer.data();expected.x=x.data();expected.y=y.data();expected.py=py.data();expected.routes=routes.data();expected.status=status.data();expected.peer_status=peer_status.data();expected.active=&active;expected.error=&error;expected.position=&position;expected.rows=rows;expected.count=count;expected.experts=experts;expected.rb=raw_stride;
    p39::host_gemv<T,K,E,true>(expected);
    std::vector<uint16_t> empty(rows*count,0);std::vector<uint32_t> zero(count,0);uint32_t initial_error=scenario==3?7:0;
    Matrix m{};m.type=T;m.w=r.upload(packed.data(),packed.size());m.x=r.upload(x.data(),x.size()*2);m.y=r.upload(empty.data(),empty.size()*2);m.rows=rows;m.columns=K;m.span=rows;m.count=count;m.experts=experts;m.routes=r.upload(routes.data(),routes.size()*sizeof(iq3::Route));m.status=r.upload(zero.data(),zero.size()*4);m.workspace=r.alloc(rows*count*32);
    auto second=m;second.w=r.upload(packed_peer.data(),packed_peer.size());second.y=r.upload(empty.data(),empty.size()*2);second.status=r.upload(zero.data(),zero.size()*4);
    p39::Bindings b;b.error=r.upload(&initial_error,4);b.active=r.upload(&active,4);b.position=r.upload(&position,4);b.capacity=4096;
    std::vector<Matrix> matrices{m};if constexpr(paired)matrices.push_back(second);
    auto launch=p49b::submit(r.device,matrices,E,b);r.finish(launch.last);
    auto compare=[&](Allocation id,const void* oracle,size_t size){auto h=r.alloc(size,Memory::pinned);r.finish(r.copy.copy(h,0,id,0,size,{}));auto actual=static_cast<const uint8_t*>(r.device.arena.row(h).pointer);check(!std::memcmp(actual,oracle,size),"expert byte mismatch T="+std::to_string(int(T))+" scenario="+std::to_string(scenario));bytes.write(reinterpret_cast<const char*>(actual),size);all_output.insert(all_output.end(),actual,actual+size);};
    compare(m.y,y.data(),y.size()*2);compare(m.status,status.data(),status.size()*4);compare(b.error,&error,4);
    if constexpr(paired){compare(second.y,py.data(),py.size()*2);compare(second.status,peer_status.data(),peer_status.size()*4);}
    cases<<"{\"batch_rows\":"<<batch<<",\"row\":"<<token<<",\"scenario\":"<<scenario<<",\"type\":"<<int(T)<<",\"passed\":true}\n";
    ++checks;r.clear();
   }
  };
  exercise.template operator()<iq3::Type::IQ2_S,2560,p39::Kind::expert_checks>();
  exercise.template operator()<iq3::Type::IQ4_NL,640,p39::Kind::down_status>();
  check(checks==48,"p49b expert fixture coverage");
  bytes.close();cases.close();check(bool(bytes)&&bool(cases),"fixture output flush");
  const auto shutdown=runner->device.shutdown(std::chrono::seconds(60));check(shutdown.safe_to_exit&&shutdown.exit_code==0,"p49b expert fixture teardown");
  std::ofstream receipt(out/"receipt.json");
  receipt<<"{\"schema\":\"packet49b.expert-fixtures.v1\",\"passed\":true,\"device_executed\":"<<(authorized?"true":"false")<<",\"reference_exact\":true,\"checks\":"<<checks<<",\"card\":"<<card<<",\"output_sha256\":"<<quote(packet26::hash(all_output.data(),all_output.size()))<<",\"teardown\":"<<shutdown.json()<<"}\n";
  receipt.close();check(bool(receipt),"fixture receipt flush");std::cout<<checks<<" p49b expert fixture checks PASS\n";return 0;
 }catch(const std::exception& error){
  std::cerr<<error.what()<<'\n';
  if(runner){std::ofstream(out/"receipt.json")<<"{\"schema\":\"packet49b.expert-fixtures.v1\",\"passed\":false,\"device_executed\":"<<(authorized?"true":"false")<<",\"checks\":"<<checks<<",\"error\":"<<quote(error.what())<<"}\n";packet26::failure(runner->device,out,error.what());}
  return 1;
 }
}
