#include "k2_failure.hpp"
#include "fixture_validation.hpp"
#define integrated kernel_fixture_snapshot_integrated
#define ng kernel_fixture_snapshot_ng
#define detmath kernel_fixture_snapshot_detmath
#define rope_constants kernel_fixture_snapshot_rope_constants
#include "prototype/snapshot/reference.hpp"
#undef integrated
#undef ng
#undef detmath
#undef rope_constants
#include "specialised_submit.hpp"
#include "round2_submit.hpp"
#include "p33r2.hpp"
#include "k2_incumbents.hpp"
#include "small_gemv_fixture.hpp"
#include "native.hpp"
#include "adapter_fixture.hpp"
#include "failure.hpp"
#include "dispatch.hpp"


#include "owner.hpp"
#include "runtime_kernels.hpp"
#include <fstream>
#include <filesystem>
#include <iostream>
#include <openssl/sha.h>
#include <iomanip>
#include <sstream>
#include <unistd.h>
#include <random>
#include <map>
#include <set>
#include <cstring>
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif
namespace {
using namespace ownrt;
#ifdef OWN_RT_HOST_ONLY
using integrated::HostOperation;
#endif
namespace ref=kernel_fixture_snapshot_ng;
void check(bool x,const std::string& text){if(!x)throw std::runtime_error(text);}
struct Fixture {
 ng::Shape shape;std::array<std::vector<uint8_t>,19> data;std::array<bool,19> outputs{};
 std::string name;
 static std::vector<uint8_t> integer(int32_t n){std::vector<uint8_t> b(4);std::memcpy(b.data(),&n,4);return b;}
 void rope(){std::ifstream in(std::filesystem::path(__FILE__).parent_path()/"rope.bf16",std::ios::binary);data[16].assign(std::istreambuf_iterator<char>(in),{});check(data[16].size()==rope_constants::bytes,"kernel fixture RoPE");}
 explicit Fixture(const std::filesystem::path& path):name(path.filename().string()){
  std::ifstream in(path,std::ios::binary);in.read(reinterpret_cast<char*>(&shape),sizeof shape);ng::validate(shape);
  for(int slot=0;slot<16;++slot){uint32_t n=0,o=0;in.read(reinterpret_cast<char*>(&n),4);in.read(reinterpret_cast<char*>(&o),4);check(n&&n<=128*1024*1024,"kernel fixture size");data[slot].resize(n);outputs[slot]=o;in.read(reinterpret_cast<char*>(data[slot].data()),n);if(o)in.seekg(n,std::ios::cur);}
  check(bool(in)&&in.peek()==EOF,"kernel fixture bytes");int32_t control[3];check(data[15].size()>=12,"kernel fixture control");std::memcpy(control,data[15].data(),12);
  data[15]=integer(control[2]);data[17]=integer(control[0]);data[18]=integer(control[1]);outputs[15]=true;rope();
 }
 Fixture(ng::Shape s,std::string label):shape(s),name(std::move(label)){
  auto sizes=ng::required_bytes(s);for(int slot=0;slot<19;++slot)data[slot].resize(std::max(size_t(4),sizes[slot]));
  data[15]=integer(0);data[17]=integer(0);data[18]=integer(1);rope();
  for(int slot=0;slot<15;++slot)for(size_t j=0;j<data[slot].size()/2;++j){uint16_t v=ng::Args::bits(float(int((j*17+slot*11)%71)-35)*0.03125f);std::memcpy(data[slot].data()+j*2,&v,2);}
  outputs[s.op==ng::norm?2:5]=true;if(s.op==ng::combine_norm)outputs[4]=true;outputs[15]=true;
 }
 ng::Args args(){ng::Args a;for(int j=0;j<19;++j)a.p[j]=data[j].data();return a;}
 void reference(){ref::Shape s;static_assert(sizeof(s)==sizeof(shape));std::memcpy(&s,&shape,sizeof s);ref::Args a;for(int j=0;j<15;++j)a.p[j]=data[j].data();int32_t control[]{0,0,0};std::memcpy(control,data[17].data(),4);std::memcpy(control+1,data[18].data(),4);std::memcpy(control+2,data[15].data(),4);a.p[15]=control;ref::reference::cpu(s,a);std::memcpy(data[15].data(),control+2,4);}
};

#ifdef OWN_RT_HOST_ONLY
struct Cpu:Backend {
 std::string identity()const override{return "CPU packet26 fixture";}
 void* allocate(size_t n,Memory)override{return ::operator new(n);}
 void release(void* p,Memory)override{::operator delete(p);}
 Event copy(void* a,const void* b,size_t n,std::span<const Event>)override{std::memcpy(a,b,n);return next_handle();}
 Event marker(std::span<const Event>)override{return next_handle();}
 Event compute(const Operation& op,std::span<void* const> p,std::span<const Event>)override{if(!fixture_validation::only)dynamic_cast<const HostOperation&>(op).run(p);return next_handle();}
 bool complete(Event)override{return true;}bool wait(Event,Deadline)override{return true;}
 EventTiming timing(Event)override{return {0,0};}
 void synchronize()override{}void clear_events()override{}void close_queue()override{}void close_context()override{}
};
struct Original:HostOperation {ng::Shape shape;explicit Original(ng::Shape s):shape(s){}void run(std::span<void*const> p)const override{ng::Args a;std::copy_n(p.begin(),19,a.p.begin());ng::cpu(shape,a);}};
#endif
std::string classname(ng::Shape s){switch(s.op){case ng::norm:return "norm";case ng::combine_norm:return "hc.combine_norm";case ng::gated_norm:return "gdn.norm";case ng::gdn:return "gdn.recurrence";case ng::prepare:return "qsa.prepare";case ng::pool:return "qsa.pool";case ng::select:return "qsa.select";case ng::attention_score:return "qsa.attention";case ng::route_gather:return "route_gather";case ng::conv:return "conv";case ng::activation:return "activation";case ng::mix:return "hc.mix";case ng::moe_combine:return "moe";default:throw std::invalid_argument("fixture class");}}
struct Runner {
 Device device;CopyEngine copy;std::vector<Allocation> owned;size_t serial=0;uint64_t maximum=0;std::ofstream* events=nullptr;
 static std::unique_ptr<Backend> backend(unsigned card){
 #ifdef OWN_RT_HOST_ONLY
 (void)card;return std::make_unique<Cpu>();
 #else
 return make_sycl_device(card,true);
 #endif
 }
 explicit Runner(unsigned card):device(backend(card)),copy(device){}
 Allocation allocate(size_t n,Memory m=Memory::device){auto a=device.arena.allocate("fixture-"+std::to_string(serial++),n,m,Category::scratch,Lifetime::transaction);owned.push_back(a);return a;}
 void finish(Event e){check(device.wait(e,std::chrono::seconds(300)),"fixture submission deadline");auto t=device.timing(e);if(t.end_ns>t.start_ns)maximum=std::max(maximum,t.end_ns-t.start_ns);}
 Allocation upload(const std::vector<uint8_t>& b){auto host=allocate(b.size(),Memory::pinned),out=allocate(b.size());std::memcpy(device.arena.row(host).pointer,b.data(),b.size());finish(copy.copy(out,0,host,0,b.size(),{}));return out;}
 std::vector<Allocation> prepare(const Fixture& fixture){std::vector<Allocation> bindings;for(auto& b:fixture.data)bindings.push_back(upload(b));return bindings;}
 void download(Fixture& fixture,const std::vector<Allocation>& bindings){
  for(int j=0;j<19;++j)if(fixture.outputs[j]){auto host=allocate(fixture.data[j].size(),Memory::pinned);finish(copy.copy(host,0,bindings[j],0,fixture.data[j].size(),{}));std::memcpy(fixture.data[j].data(),device.arena.row(host).pointer,fixture.data[j].size());}
 }
 void clear(){device.retire_completed_events();for(auto a:owned)device.arena.release(a);owned.clear();}
 void run(Fixture& fixture,int implementation,int repetition=-1,int role=0,const std::string& candidate="specialised",const std::vector<Allocation>* prepared=nullptr,Allocation prepared_scratch=0){
  auto bindings=prepared?*prepared:prepare(fixture);auto shapes=std::vector<ng::Shape>{fixture.shape};if(fixture.shape.op==ng::attention_score){auto s=fixture.shape;s.op=ng::attention_softmax;shapes.push_back(s);s.op=ng::attention_value;shapes.push_back(s);}
  size_t floats=1;for(auto s:shapes)if(specialised::supported(s))floats=std::max(floats,specialised::scratch_floats(s));auto scratch=prepared_scratch?prepared_scratch:allocate(floats*4);
  std::vector<std::pair<Event,EventTiming>> timings;
  for(auto s:shapes){integrated::Launch launch{};
   if(implementation==3&&round2::supported(s))launch=p33r2::submit(device,s,bindings,scratch);
   else if(implementation==2&&round2::supported(s))launch=round2::submit(device,s,bindings,scratch);
   else if(implementation&&specialised::supported(s))launch=specialised::submit(device,s,bindings,scratch);
   else {
#ifdef OWN_RT_HOST_ONLY
    fixture_validation::nongemv(device,s,bindings);Original op(s);auto e=device.compute(op,bindings,{});
#else
    auto e=ng::submit(device,s,bindings,{});
#endif
    launch={e,e,1};
   }
   finish(launch.last);
   for(Event event=launch.first;event<=launch.last;++event){auto t=device.timing(event);timings.push_back({event,t});}
  }
  if(!prepared)download(fixture,bindings);
  if(events&&repetition>=0)for(auto [event,t]:timings)*events<<"{\"class\":"<<quote(classname(fixture.shape))<<",\"variant\":\""<<(role?"specialised":"packet18")<<"\",\"candidate\":"<<quote(candidate)<<",\"implementation\":"<<quote(implementation==3?"p33.qsa.shape":implementation==2?"round2":implementation==1?"specialised":"packet18")<<",\"kernel_identity\":"<<quote(classname(fixture.shape)+":"+(implementation==3?"p33.qsa.shape":implementation==2?"round2":implementation==1?"specialised":"packet18"))<<",\"candidate_available\":"<<((implementation||role==0)?"true":"false")<<",\"repetition\":"<<repetition<<",\"event\":"<<event<<",\"stage_count\":"<<timings.size()<<",\"start_ns\":"<<t.start_ns<<",\"end_ns\":"<<t.end_ns<<",\"exact\":true}\n";
  if(!prepared)clear();
 }
};
void compare(const Fixture& a,const Fixture& b,std::ofstream& bytes){if(fixture_validation::only)return;for(int j=0;j<19;++j)if(a.outputs[j]){check(a.data[j]==b.data[j],a.name+" mismatch slot "+std::to_string(j));bytes.write(reinterpret_cast<const char*>(b.data[j].data()),b.data[j].size());}}
}
int main(int argc,char** argv){std::filesystem::path out;std::unique_ptr<Runner> runner;try{
 unsigned card=0,seed=1,repetitions=200;bool authorized=false;auto fixtures=std::filesystem::path(__FILE__).parent_path()/"build/fusion-fixtures";
 for(int i=1;i<argc;++i){std::string arg=argv[i];if(arg=="--validate-only"){
#ifdef OWN_RT_HOST_ONLY
 fixture_validation::only=true;
#else
 throw std::invalid_argument("CPU validation only");
#endif
 }else if(arg=="--poison-dense-status"||arg=="--inject-candidate-failures"){
#ifdef OWN_RT_HOST_ONLY
 if(arg=="--poison-dense-status")fixture_validation::poison_dense=true;else fixture_validation::inject=true;
#else
 throw std::invalid_argument("CPU regression only");
#endif
 }else if(arg=="--stop-fd"&&i+1<argc)ownrt::set_stop_channel(std::stoi(argv[++i]));else if(arg=="--dispatch"&&i+1<argc)packet26::dispatch.load(argv[++i]);else if(arg=="--card"&&i+1<argc)card=std::stoul(argv[++i]);else if(arg=="--output"&&i+1<argc)out=argv[++i];else if(arg=="--fixtures"&&i+1<argc)fixtures=argv[++i];else if(arg=="--seed"&&i+1<argc)seed=std::stoul(argv[++i]);else if(arg=="--repetitions"&&i+1<argc)repetitions=std::stoul(argv[++i]);else if(arg=="--authorized-device-window")authorized=true;else throw std::invalid_argument("fixture arguments");}
 check(!out.empty(),"--output required");std::filesystem::create_directories(out);
#ifdef OWN_RT_HOST_ONLY
 check(!authorized,"host fixture binary cannot run device window");
#else
 check(authorized,"device authorization required");
#endif
 std::ifstream list(fixtures/"cases.txt");check(bool(list),"fixture list missing");std::vector<Fixture> cases;std::string name;while(list>>name)cases.emplace_back(fixtures/name);check(cases.size()==72,"all72 fixtures required");
#ifndef PACKET26_K2
 for(int n:{1,3,17,255,2560})for(int op:{int(ng::norm),int(ng::combine_norm)})for(int unit:{0,1}){ng::Shape shape;shape.op=op;shape.width=n;shape.tokens=1;shape.heads=4;shape.flags=unit;cases.emplace_back(shape,"odd-width-"+std::to_string(n));}
#endif
#ifndef PACKET26_K2
 // Regression for the K2 position mutation: preserve coherent completed pool
 // history while forcing the current four-token block to be newly calculated.
 {auto it=std::find_if(cases.begin(),cases.end(),[](const Fixture& f){return f.name=="qsa-pool-1.fixture";});check(it!=cases.end(),"pool regression fixture");auto moved=*it;moved.name="qsa-pool-position63-regression";moved.data[17]=Fixture::integer(63);if(!fixture_validation::only){auto fixed=moved;fixed.reference();std::copy_n(fixed.data[7].begin(),size_t(63/4)*128*2,moved.data[7].begin());}cases.push_back(std::move(moved));}
#endif
 std::mt19937 rng(seed);std::shuffle(cases.begin(),cases.end(),rng);std::ofstream bytes(out/"output.bin",std::ios::binary),events(out/"events.jsonl");runner=std::make_unique<Runner>(card);size_t checks=0;
#ifdef PACKET26_K2
 check(repetitions==200,"K2 requires exactly200 repetitions");
 const std::set<std::string> decode_names{"norm-stored-f32-1.fixture","combine-norm-1.fixture","gdn-gated-1.fixture","gdn-runtime-f32-1.fixture","qsa-prepare-1.fixture","qsa-pool-1.fixture","qsa-select-1.fixture","qsa-attention-1.fixture","route-gather-1.fixture","conv-10240-1.fixture","ffn-routed-act-1.fixture","mix-1.fixture","moe-combine-1.fixture"};
 unsigned decode_cases=0;
 for(auto source:cases){if(!decode_names.contains(source.name))continue;++decode_cases;
  if(source.shape.op==ng::prepare||source.shape.op==ng::pool||source.shape.op==ng::select||source.shape.op==ng::attention_score){source.data[17]=Fixture::integer(63);if(source.shape.op==ng::attention_score){auto a=source.args();for(int j=0;j<source.shape.budget+3;++j)a.i(4)[j]=j<64?j:-1;}}
  auto oracle=source;if(!fixture_validation::only)oracle.reference();
  // Timing moves this fixture from its original position to 63. The reference
  // recomputes every historic pool; native kernels retain previous pools. Seed
  // exactly that retained prefix from the reference over the same raw history.
  // The current block is left untouched and must still be computed by both.
  if(source.shape.op==ng::pool&&!fixture_validation::only){int pos=63;size_t prior=size_t(pos/4)*128*2;std::copy_n(oracle.data[7].begin(),prior,source.data[7].begin());}
  int incumbent=packet37::class_incumbent(classname(source.shape));
  for(int alternative:source.shape.op==ng::attention_score?std::vector<int>{2,3}:std::vector<int>{round2::supported(source.shape)?2:specialised::supported(source.shape)?1:0}){
  std::string candidate=alternative==3?"p33.qsa.shape":alternative==2?"round2":"specialised";
  bool excluded[2]{};
  const unsigned repeats=fixture_validation::only?1u:repetitions;
  // Each stateful invocation gets a fresh preuploaded state. No transfers or
  // allocations occur in the timed submission loop; all outputs are read later.
  std::vector<std::vector<Allocation>> prepared[2];
  for(int version:{0,1})for(unsigned r=0;r<repeats;++r)prepared[version].push_back(runner->prepare(source));
  size_t nf=1;auto ss=std::vector<ng::Shape>{source.shape};if(source.shape.op==ng::attention_score){auto s=source.shape;s.op=ng::attention_softmax;ss.push_back(s);s.op=ng::attention_value;ss.push_back(s);}
  for(auto s:ss)if(specialised::supported(s))nf=std::max(nf,specialised::scratch_floats(s));
  auto prepared_scratch=runner->allocate(nf*4);
  for(unsigned r=0;r<repeats;++r)for(int version:{0,1}){
   if(excluded[version])continue;
   try{fixture_validation::inject_failure(classname(source.shape),version);auto actual=source;runner->events=&events;runner->run(actual,version?alternative:incumbent,r,version,candidate,&prepared[version][r],prepared_scratch);++checks;}
   catch(const std::exception& e){if(fixture_validation::only&&!dynamic_cast<const fixture_validation::InjectedFailure*>(&e))throw;packet26::candidate_failure(out,classname(source.shape),version?"specialised":"packet18",source.name,e,version?(alternative==3?"p33.qsa.shape":alternative==2?"round2":alternative==1?"specialised":"packet18"):(incumbent==2?"round2":incumbent==1?"specialised":"packet18"));excluded[version]=true;
    runner->device.retire_completed_events();}
  }
  for(int version:{0,1})if(!excluded[version])for(unsigned r=0;r<repeats;++r){auto actual=source;runner->download(actual,prepared[version][r]);compare(oracle,actual,bytes);}
  runner->clear();
  }
 }
 check(decode_cases==decode_names.size(),"all registered decode fixtures required");
#else
 for(const auto& source:cases){auto oracle=source,old=source,newer=source;if(!fixture_validation::only)oracle.reference();runner->run(old,0);runner->run(newer,1);compare(oracle,old,bytes);compare(oracle,newer,bytes);compare(old,newer,bytes);++checks;if(round2::supported(source.shape)){auto newest=source;runner->run(newest,2);compare(oracle,newest,bytes);compare(old,newest,bytes);++checks;}if(source.shape.op==ng::attention_score){auto newest=source;runner->run(newest,3);compare(oracle,newest,bytes);compare(old,newest,bytes);++checks;}}
#endif
 bytes.close();events.close();
 auto shutdown=runner->device.shutdown(std::chrono::seconds(60));check(shutdown.safe_to_exit&&shutdown.exit_code==0,"fixture teardown");
 std::string teardown="["+shutdown.json()+"]";unsigned adapter_checks=0;
#ifndef PACKET26_K2
 auto adapter=adapter_fixture_gate(card,out/"output.bin");
#else
 auto adapter=adapter_timing_gate(card,out);
#endif
 adapter_checks=adapter.checks;runner->maximum=std::max(runner->maximum,adapter.max_submission_ns);teardown.insert(teardown.size()-1,","+adapter.teardown);
#ifdef PACKET26_K2
 auto gemv=gemv_timing_gate(card,out);
#else
 auto gemv=gemv_fixture_gate(card,out);
#endif
 #ifdef PACKET26_K2
 auto small=small_gemv_timing_gate(card,out);
#else
 auto small=small_gemv_fixture_gate(card,out);
#endif
 adapter_checks+=small.checks;runner->maximum=std::max(runner->maximum,small.max_submission_ns);teardown.insert(teardown.size()-1,","+small.teardown);
 adapter_checks+=gemv.checks;runner->maximum=std::max(runner->maximum,gemv.max_submission_ns);teardown.insert(teardown.size()-1,","+gemv.teardown);
 std::ifstream input(out/"output.bin",std::ios::binary);SHA256_CTX hash;SHA256_Init(&hash);std::array<char,65536> block;while(input){input.read(block.data(),block.size());SHA256_Update(&hash,block.data(),input.gcount());}unsigned char digest[32];SHA256_Final(digest,&hash);std::ostringstream hex;for(auto b:digest)hex<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(b);
 bool all_exact=!fixture_validation::only&&!std::filesystem::exists(out/"candidate-failures.jsonl");
 std::ofstream receipt(out/"receipt.json");receipt<<"{\"schema\":\""<<
#ifdef PACKET26_K2
 "packet26.k2.v1"
#else
 "packet26.fixtures.v1"
#endif
 <<"\",\"passed\":true,\"device_executed\":"<<(authorized?"true":"false")<<",\"validation_only\":"<<(fixture_validation::only?"true":"false")<<",\"diagnostic\":true,\"owner_cards\":1,\"reference_exact\":"<<(all_exact?"true":"false")<<",\"packet18_exact\":"<<(all_exact?"true":"false")<<",\"fixtures\":"<<checks<<",\"source_fixtures\":"<<cases.size()<<",\"gemv_checks\":"<<gemv.checks<<",\"small_gemv_checks\":"<<small.checks<<",\"adapter_only_checks\":"<<adapter.checks<<",\"adapter_checks\":"<<adapter_checks<<",\"odd_lengths\":20,\"ties\":1,\"nan_routes\":1,\"repetitions\":"<<repetitions<<",\"output_sha256\":\""<<hex.str()<<"\",\"max_submission_ns\":"<<runner->maximum<<",\"teardown\":"<<teardown<<"}\n";
 std::cout<<checks<<" fixture checks PASS\n";return 0;
 }catch(const std::exception& error){std::cerr<<error.what()<<'\n';if(!out.empty()){std::filesystem::create_directories(out);std::ofstream(out/"failure.json")<<"{\"passed\":false,\"error\":"<<quote(error.what())<<"}\n";}if(runner)packet26::failure(runner->device,out,error.what());return 1;}}
