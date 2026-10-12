#include "parallel.hpp"
#include "gate_mode.hpp"
#include "compile_smoke.hpp"
#include "stop.hpp"
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
 void rope(){std::ifstream in(std::filesystem::path("/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet29-merged/rope.bf16"),std::ios::binary);data[16].assign(std::istreambuf_iterator<char>(in),{});check(data[16].size()==rope_constants::bytes,"kernel fixture RoPE");}
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
   if(implementation==3)launch=p42parallel::submit(device,s,bindings,scratch);
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
  if(events&&repetition>=0)for(auto [event,t]:timings)*events<<"{\"class\":"<<quote(classname(fixture.shape))<<",\"variant\":\""<<(role?"specialised":"packet18")<<"\",\"candidate\":"<<quote(candidate)<<",\"implementation\":"<<quote(implementation==3?"p42.parallel":implementation==2?"round2":implementation==1?"specialised":"packet18")<<",\"kernel_identity\":"<<quote(classname(fixture.shape)+":"+(implementation==3?"p42.parallel":implementation==2?"round2":implementation==1?"specialised":"packet18"))<<",\"candidate_available\":"<<((implementation||role==0)?"true":"false")<<",\"repetition\":"<<repetition<<",\"event\":"<<event<<",\"stage_count\":"<<timings.size()<<",\"start_ns\":"<<t.start_ns<<",\"end_ns\":"<<t.end_ns<<",\"exact\":true}\n";
  if(!prepared)clear();
 }
};
SHA256_CTX output_hash;
void compare(const Fixture& a,const Fixture& b,std::ofstream& bytes){if(p42gate::bindings_only||fixture_validation::only)return;for(int j=0;j<19;++j)if(a.outputs[j]){check(a.data[j]==b.data[j],a.name+" mismatch slot "+std::to_string(j));SHA256_Update(&output_hash,b.data[j].data(),b.data[j].size());}}
}
int main(int argc,char**argv){std::filesystem::path out;std::unique_ptr<Runner> runner;try{p42::install_stop();SHA256_Init(&output_hash);unsigned card=0,repetitions=200;bool smoke=false,authorized=false;
 for(int i=1;i<argc;++i){std::string arg=argv[i];if(arg=="--card"&&i+1<argc)card=std::stoul(argv[++i]);else if(arg=="--output"&&i+1<argc)out=argv[++i];else if(arg=="--repetitions"&&i+1<argc)repetitions=std::stoul(argv[++i]);else if(arg=="--compile-smoke")smoke=true;else if(arg=="--authorized-device-window")authorized=true;else throw std::invalid_argument("parallel arguments");}
 check(!out.empty()&&authorized,"output and authorized-device-window required");std::filesystem::create_directories(out);check(repetitions==200,"200 repetitions required");
 if(smoke){unsigned n=p42_compile_smoke(card);std::ofstream f;f.exceptions(std::ios::failbit|std::ios::badbit);f.open(out/"receipt.json");f<<"{\"infrastructure_passed\":true,\"kernel_execution\":false,\"kernel_count\":"<<n<<"}\n";f.close();return 0;}
 std::ofstream bytes,events,walls,failures;for(auto* stream:{&bytes,&events,&walls,&failures})stream->exceptions(std::ios::failbit|std::ios::badbit);bytes.open(out/"output.bin",std::ios::binary);events.open(out/"events.jsonl");walls.open(out/"walls.jsonl");failures.open(out/"candidate-failures.jsonl");runner=std::make_unique<Runner>(card);unsigned cases=0,failed=0;
 for(auto name:{"route-gather-1.fixture","gdn-runtime-f32-1.fixture"}){Fixture source(std::filesystem::path("/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet29-merged/build/fusion-fixtures")/name),oracle=source;oracle.reference();int incumbent=source.shape.op==ng::gdn?2:1;std::string candidate=source.shape.op==ng::gdn?"p42.gdn.token1":"p42.route.rank32";bool excluded[2]{};
  // Both payloads are below 8 MB. Independent preuploaded states also avoid
  // state carry-over. Device allocation/copies are outside timed regions.
  std::vector<std::vector<Allocation>> prepared[2];for(int version:{0,1})for(unsigned r=0;r<repetitions;++r)prepared[version].push_back(runner->prepare(source));auto scratch=runner->allocate(specialised::scratch_floats(source.shape)*4);
  for(unsigned r=0;r<repetitions;++r)for(int version:{0,1})if(!excluded[version]){p42::check_stop();try{auto actual=source;runner->events=&events;auto start=std::chrono::steady_clock::now();runner->run(actual,version?3:incumbent,r,version,candidate,&prepared[version][r],scratch);auto stop=std::chrono::steady_clock::now();walls<<"{\"class\":"<<quote(classname(source.shape))<<",\"candidate\":"<<quote(candidate)<<",\"version\":"<<version<<",\"repetition\":"<<r<<",\"host_wall_ns\":"<<std::chrono::duration_cast<std::chrono::nanoseconds>(stop-start).count()<<"}\n";
   runner->download(actual,prepared[version][r]);compare(oracle,actual,bytes);++cases;
  }catch(const std::exception&e){if(p42::stopping||dynamic_cast<const std::ios_base::failure*>(&e)||dynamic_cast<const sycl::exception*>(&e))throw;if(!dynamic_cast<const std::invalid_argument*>(&e)&&std::string(e.what()).find(" mismatch slot ")==std::string::npos)throw;failures<<"{\"class\":"<<quote(classname(source.shape))<<",\"candidate\":"<<quote(candidate)<<",\"version\":"<<version<<",\"passed\":false,\"error\":"<<quote(e.what())<<"}\n";failures.flush();excluded[version]=true;++failed;runner->events=nullptr;}}
  runner->clear();
 }
 bytes.close();events.close();walls.close();failures.close();unsigned char digest[32];SHA256_Final(digest,&output_hash);std::ostringstream hex;for(auto v:digest)hex<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(v);std::filesystem::remove(out/"output.bin");
 auto shutdown=runner->device.shutdown(std::chrono::seconds(300));check(shutdown.safe_to_exit&&!shutdown.exit_code,"parallel teardown");std::ofstream receipt;receipt.exceptions(std::ios::failbit|std::ios::badbit);receipt.open(out/"receipt.json");receipt<<"{\"infrastructure_passed\":true,\"device_executed\":" P42_DEVICE_EXECUTED ",\"cases\":"<<cases<<",\"failed_cases\":"<<failed<<",\"output_sha256\":\""<<hex.str()<<"\",\"teardown\":"<<shutdown.json()<<"}\n";receipt.close();return 0;
 }catch(const std::exception&e){std::cerr<<"FAILED parallel window: "<<e.what()<<'\n';try{if(!out.empty()){std::ofstream failure;failure.exceptions(std::ios::failbit|std::ios::badbit);failure.open(out/"failure.json");failure<<"{\"infrastructure_passed\":false,\"error\":"<<ownrt::quote(e.what())<<"}\n";failure.close();}}catch(const std::exception&storage){std::cerr<<"FAILED writing receipt: "<<storage.what()<<'\n';}if(runner)runner->device.shutdown(std::chrono::seconds(300));return 1;}}
