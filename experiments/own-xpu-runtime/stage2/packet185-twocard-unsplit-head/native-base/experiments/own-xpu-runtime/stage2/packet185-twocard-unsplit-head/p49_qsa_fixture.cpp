#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p49_qsa_fixture.cpp"
// Exercises every compiled p33 dense T/K/split instantiation without changing
// the runtime object set. This is correctness evidence, never a speed benchmark.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/build/checked/experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/p49_qsa_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/build/checked/experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/p49_qsa_reference.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/build/checked/experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head/failure.hpp"
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
   else throw std::invalid_argument("p49 QSA fixture arguments");
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
  for(int context:{2,3,31,32,33,63,64,65,1027,2051,4096})for(int rows:{1,2})for(int mode:{0,1,2,3}){
   auto&r=*runner;r.between_cases();p47ref::Fixture fixture(context,rows,4901+context,mode==1?1:0),expected=fixture;
   if(mode==2){fixture.args().i(18)[0]=0;expected.args().i(18)[0]=0;}
   if(mode==3){fixture.args().i(15)[0]=7;expected.args().i(15)[0]=7;}
   p47ref::cpu_split(expected.shape,expected.args());std::array<Allocation,19>a;
   for(int j=0;j<19;++j)a[j]=r.upload(fixture.data[j].data(),fixture.data[j].size()*4);
   const auto scratch=r.alloc(p49::scratch_bytes(fixture.shape));
   auto launch=p49::attention(r.device,fixture.shape,a,scratch);r.finish(launch.last);
   auto host=r.alloc(fixture.data[5].size()*4,Memory::pinned);r.finish(r.copy.copy(host,0,a[5],0,fixture.data[5].size()*4,{}));
   const auto*actual=static_cast<const uint8_t*>(r.device.arena.row(host).pointer);size_t size=fixture.data[5].size()*4;
   check(!std::memcmp(actual,expected.data[5].data(),size),"p49 split32 owner output differs");
   bytes.write(reinterpret_cast<const char*>(actual),size);all_output.insert(all_output.end(),actual,actual+size);
   cases<<"{\"context\":"<<context<<",\"rows\":"<<rows<<",\"mode\":"<<mode<<",\"passed\":true}\n";
   ++checks;r.clear();
  }
  check(checks==88,"p49 fixture coverage");
  bytes.close();cases.close();check(bool(bytes)&&bool(cases),"fixture output flush");
  const auto shutdown=runner->device.shutdown(std::chrono::seconds(60));check(shutdown.safe_to_exit&&shutdown.exit_code==0,"p49 QSA fixture teardown");
  std::ofstream receipt(out/"receipt.json");
  receipt<<"{\"schema\":\"packet49.qsa-fixtures.v1\",\"passed\":true,\"device_executed\":"<<(authorized?"true":"false")<<",\"reference_exact\":true,\"checks\":"<<checks<<",\"card\":"<<card<<",\"output_sha256\":"<<quote(packet26::hash(all_output.data(),all_output.size()))<<",\"teardown\":"<<shutdown.json()<<"}\n";
  receipt.close();check(bool(receipt),"fixture receipt flush");std::cout<<checks<<" p49 QSA fixture checks PASS\n";return 0;
 }catch(const std::exception& error){
  std::cerr<<error.what()<<'\n';
  if(runner){std::ofstream(out/"receipt.json")<<"{\"schema\":\"packet49.qsa-fixtures.v1\",\"passed\":false,\"device_executed\":"<<(authorized?"true":"false")<<",\"checks\":"<<checks<<",\"error\":"<<quote(error.what())<<"}\n";packet26::failure(runner->device,out,error.what());}
  return 1;
 }
}
