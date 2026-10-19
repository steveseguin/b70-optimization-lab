#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet151-sibling-cost/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p49c_fixture.cpp"
// Actual owner submissions for the qualified expert formats and both verification rows.
// This is correctness evidence, never a speed benchmark.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet151-sibling-cost/build/checked/experiments/own-xpu-runtime/stage2/packet151-sibling-cost/p49c_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet151-sibling-cost/build/checked/experiments/own-xpu-runtime/stage2/packet151-sibling-cost/route42.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet151-sibling-cost/build/checked/experiments/own-xpu-runtime/stage2/packet151-sibling-cost/failure.hpp"
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
 std::string identity()const override{return "CPU packet49b round2 fixture";}
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
 Allocation alloc(size_t n,Memory m=Memory::device){auto id=device.arena.allocate("p49c-expert-"+std::to_string(serial++),n,m,Category::scratch,Lifetime::transaction);owned.push_back(id);return id;}
 void finish(Event e){check(device.wait(e,wait_limit),"p49c expert fixture submission deadline");}
 Allocation upload(const void* src,size_t bytes){auto host=alloc(bytes,Memory::pinned),out=alloc(bytes);std::memcpy(device.arena.row(host).pointer,src,bytes);finish(copy.copy(out,0,host,0,bytes,{}));return out;}
 void clear(){device.retire_completed_events();for(auto id:owned)device.arena.release(id);owned.clear();}
 void between_cases(){check(Clock::now()<deadline,"p49c expert fixture total deadline");}
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
   else throw std::invalid_argument("p49c expert fixture arguments");
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

  auto read=[&](Allocation id,size_t n){auto&r=*runner;auto h=r.alloc(n,Memory::pinned);r.finish(r.copy.copy(h,0,id,0,n,{}));auto ptr=static_cast<const uint8_t*>(r.device.arena.row(h).pointer);return std::vector<uint8_t>(ptr,ptr+n);};
  auto compare=[&](const std::vector<uint8_t>& actual,const std::vector<uint8_t>& expected,const std::string& name,bool canonical=true){check(actual==expected,"round2 byte mismatch "+name);if(canonical){bytes.write(reinterpret_cast<const char*>(actual.data()),actual.size());all_output.insert(all_output.end(),actual.begin(),actual.end());}};
  auto dense=[&]<iq3::Type T,unsigned K,unsigned Rows,p39::Kind E>(){
   const auto stride=arithmetic::row_bytes(T,K,6);std::vector<uint8_t>w(Rows*stride);uint32_t seed=0x49c;
   for(auto& v:w){seed=seed*1664525u+1013904223u;v=seed>>24;}
   constexpr unsigned group=T==iq3::Type::Q6_K?16:32;
   for(unsigned row=0;row<Rows;++row)for(unsigned j=0;j<K/group;++j){float value=0.015625f;std::memcpy(w.data()+row*stride+K+j*4,&value,4);}
   for(unsigned batch:{1u,2u})for(unsigned scenario=0;scenario<8;++scenario)for(unsigned token=0;token<batch;++token){
    auto&r=*runner;r.between_cases();std::vector<uint16_t>x(K);for(unsigned j=0;j<K;++j)x[j]=iq3::bf16_bits(float(int((j+token*7)%17)-8)/32.f);
    if(scenario==5)x[0]=0x7fc1;if(scenario==6){x[0]=0x7f80;x[8]=0xff80;}if(scenario==7){x[0]=1;x[1]=0x8001;}
    uint32_t active=scenario==1?0:1,error=scenario==2?7:0,position=scenario==3?4096:scenario==4?0xffffffff:token;
    std::vector<uint16_t>y(Rows,0x7e31),out(Rows,0x7e33),streams(Rows*4,0x3d80);std::array<uint16_t,4>inject{0x3f00,0xbe80,0x3e00,0xbf00};std::vector<float>scratch(Rows*8,-7.25f);
    Matrix m{};m.type=T;m.w=r.upload(w.data(),w.size());m.x=r.upload(x.data(),x.size()*2);m.y=r.upload(y.data(),y.size()*2);m.rows=Rows;m.columns=K;m.span=Rows;m.count=m.experts=1;m.workspace=r.upload(scratch.data(),scratch.size()*4);
    p39::Bindings b;b.error=r.upload(&error,4);b.active=r.upload(&active,4);b.position=r.upload(&position,4);b.capacity=4096;b.out=r.upload(out.data(),out.size()*2);b.streams=r.upload(streams.data(),streams.size()*2);b.inject=r.upload(inject.data(),8);
    const std::array watched{m.y,b.out,b.streams,m.workspace,b.error,b.active,b.position};std::vector<std::vector<uint8_t>> initial,expected;
    for(auto id:watched)initial.push_back(read(id,r.device.arena.row(id).bytes));
    integrated::Launch baseline;
    if constexpr(E==p39::Kind::expert_checks)baseline=p28::submit(r.device,{m},"p28.dense.wg32",false,6);
    else baseline=p39::submit(r.device,{m},E,b);
    r.finish(baseline.last);for(auto id:watched)expected.push_back(read(id,r.device.arena.row(id).bytes));
    for(size_t j=0;j<watched.size();++j){auto h=r.alloc(initial[j].size(),Memory::pinned);std::memcpy(r.device.arena.row(h).pointer,initial[j].data(),initial[j].size());r.finish(r.copy.copy(watched[j],0,h,0,initial[j].size(),{}));}
    auto actual=p49c::dense_submit(r.device,m,E,b);r.finish(actual.last);check(actual.passes==baseline.passes,"same dense physical launch count");
    for(size_t j=0;j<watched.size();++j)compare(read(watched[j],expected[j].size()),expected[j],"dense K="+std::to_string(K)+" scenario="+std::to_string(scenario)+" buffer="+std::to_string(j),!(E==p39::Kind::attention_combine&&j==3));
    // A wrong shape and a short tail must refuse without issuing any operation.
    auto bad=m;bad.columns=K+32;bool refused=false;try{p49c::dense_submit(r.device,bad,E,b);}catch(const std::invalid_argument&){refused=true;}check(refused,"dense wrong shape refusal");
    cases<<"{\"batch_rows\":"<<batch<<",\"row\":"<<token<<",\"scenario\":"<<scenario<<",\"columns\":"<<K<<",\"passed\":true}\n";
    ++checks;r.clear();
   }
  };
  dense.template operator()<iq3::Type::Q8_0,10240,320,p39::Kind::silu_div4>();
  dense.template operator()<iq3::Type::Q8_0,320,10240,p39::Kind::expert_checks>();
  dense.template operator()<iq3::Type::Q6_K,6144,2560,p39::Kind::attention_combine>();
  for(unsigned batch:{1u,2u})for(unsigned scenario=0;scenario<8;++scenario)for(unsigned token=0;token<batch;++token){
   auto&r=*runner;r.between_cases();std::array<uint16_t,512>x{};for(unsigned j=0;j<512;++j)x[j]=iq3::bf16_bits(scenario==3?0.f:float(int((j*13+token*29)%257)-128)/16.f);
   if(scenario==4)x[0]=iq3::bf16_bits(40.f);if(scenario==5)x[0]=iq3::bf16_bits(-40.f);if(scenario==6)x.fill(iq3::bf16_bits(-40.f));if(scenario==7){x[0]=1;x[1]=0x8001;}
   uint32_t active=scenario==1?0:1,error=scenario==2?7:0,position=token;std::array<int32_t,10> ids;ids.fill(-7);std::array<float,10>prob;prob.fill(-6);std::array<int32_t,30>gate,down;gate.fill(-5);down.fill(-4);std::array<float,1088>scratch;scratch.fill(-7.25f);
   Spec s{};s.op=Op::route;s.ni=3;s.no=4;s.sizes[0]=512;s.sizes[1]=s.sizes[2]=1;s.sizes[3]=s.sizes[4]=10;s.sizes[5]=s.sizes[6]=30;s.types[0]=flash::Scalar::bf16;s.types[1]=s.types[2]=flash::Scalar::u32;s.types[3]=s.types[5]=s.types[6]=flash::Scalar::i32;s.types[4]=flash::Scalar::f32;s.site.shape[0]=512;s.site.shape[1]=10;s.g.h=2560;s.g.mid=640;
   auto er=r.upload(&error,4),ac=r.upload(&active,4);std::vector<Allocation>a{r.upload(x.data(),1024),er,ac,r.upload(ids.data(),40),r.upload(prob.data(),40),r.upload(gate.data(),120),r.upload(down.data(),120),r.upload(scratch.data(),scratch.size()*4),er,r.upload(&position,4),ac,r.alloc(4)};
   std::vector<std::vector<uint8_t>>initial,expected;for(unsigned j=3;j<=10;++j)initial.push_back(read(a[j],r.device.arena.row(a[j]).bytes));
   auto baseline=route42::submit(r.device,s,a);r.finish(baseline.last);for(unsigned j=3;j<=10;++j)expected.push_back(read(a[j],r.device.arena.row(a[j]).bytes));
   for(unsigned j=3;j<=10;++j){auto&v=initial[j-3];auto h=r.alloc(v.size(),Memory::pinned);std::memcpy(r.device.arena.row(h).pointer,v.data(),v.size());r.finish(r.copy.copy(a[j],0,h,0,v.size(),{}));}
   auto actual=p49c::route(r.device,s,a);r.finish(actual.last);check(actual.passes==baseline.passes,"same four route passes");
   for(unsigned j=3;j<=10;++j)compare(read(a[j],expected[j-3].size()),expected[j-3],"route scenario="+std::to_string(scenario)+" buffer="+std::to_string(j));
   auto alias=a;alias[3]=alias[0];bool refused=false;try{p49c::route(r.device,s,alias);}catch(const std::invalid_argument&){refused=true;}check(refused,"route output alias refusal");
   cases<<"{\"batch_rows\":"<<batch<<",\"row\":"<<token<<",\"scenario\":"<<scenario<<",\"kind\":\"route\",\"passed\":true}\n";++checks;r.clear();
  }
  check(checks==96,"p49c expert fixture coverage");
  bytes.close();cases.close();check(bool(bytes)&&bool(cases),"fixture output flush");
  const auto shutdown=runner->device.shutdown(std::chrono::seconds(60));check(shutdown.safe_to_exit&&shutdown.exit_code==0,"p49c expert fixture teardown");
  std::ofstream receipt(out/"receipt.json");
  receipt<<"{\"schema\":\"packet49c.round2-fixtures.v1\",\"passed\":true,\"device_executed\":"<<(authorized?"true":"false")<<",\"reference_exact\":true,\"canonical_output_excludes\":[\"attention.split4.workspace\"],\"same_backend_workspace_compared\":true,\"checks\":"<<checks<<",\"card\":"<<card<<",\"output_sha256\":"<<quote(packet26::hash(all_output.data(),all_output.size()))<<",\"teardown\":"<<shutdown.json()<<"}\n";
  receipt.close();check(bool(receipt),"fixture receipt flush");std::cout<<checks<<" p49c expert fixture checks PASS\n";return 0;
 }catch(const std::exception& error){
  std::cerr<<error.what()<<'\n';
  if(runner){std::ofstream(out/"receipt.json")<<"{\"schema\":\"packet49c.round2-fixtures.v1\",\"passed\":false,\"device_executed\":"<<(authorized?"true":"false")<<",\"checks\":"<<checks<<",\"error\":"<<quote(error.what())<<"}\n";packet26::failure(runner->device,out,error.what());}
  return 1;
 }
}
