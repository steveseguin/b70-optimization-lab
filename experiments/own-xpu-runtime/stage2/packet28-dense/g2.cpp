#include "submit.hpp"
#include "../packet26-specialised/failure.hpp"
#ifdef OWN_RT_HOST_ONLY
#include "device_validation.hpp"
#else
#include <sycl/sycl.hpp>
#endif
#include <array>
#include <cstring>
#include <fstream>
#include <iostream>
#include <set>
#include <filesystem>
#include <cstdlib>
#include <csignal>
namespace {
using namespace ownrt;using namespace integrated;
volatile std::sig_atomic_t stopped=0;
void stop_requested(int){stopped=1;}
void check_stop(){if(stopped)throw std::runtime_error("cooperative stop requested");}
bool validation=false,cpu_fixtures=false;
struct Options {unsigned card=0;std::string mode="G2";std::filesystem::path output;};
Options options(int argc,char** argv){Options o;for(int i=1;i<argc;++i){std::string a=argv[i];if(a=="--validate")validation=true;else if(a=="--cpu-fixtures")cpu_fixtures=true;else if((a=="--card"||a=="--mode"||a=="--output")&&i+1<argc){std::string val=argv[++i];if(a=="--card"){size_t end=0;auto n=std::stoul(val,&end);if(end!=val.size()||n>3)throw std::invalid_argument("card must be 0..3");o.card=n;}else if(a=="--mode")o.mode=val;else o.output=val;}else throw std::invalid_argument("unknown/missing option: "+a);}if(o.output.empty()||(o.mode!="K0"&&o.mode!="G2"))throw std::invalid_argument("--output and --mode K0|G2 required");
#ifdef OWN_RT_HOST_ONLY
 if(!validation&&!cpu_fixtures)throw std::invalid_argument("host binary requires --validate or --cpu-fixtures");
#else
 if(validation||cpu_fixtures)throw std::invalid_argument("native binary forbids CPU-only modes");
#endif
 return o;}
#ifdef OWN_RT_HOST_ONLY
struct Cpu final:Backend {
 std::string identity()const override{return "packet28 CPU (no accelerator libraries)";}
 void* allocate(size_t n,Memory)override{void* p=nullptr;if(posix_memalign(&p,64,validation?64:std::max(n,size_t(64))))throw std::bad_alloc();return p;}
 void release(void* p,Memory)override{free(p);}
 Event copy(void* a,const void* b,size_t n,std::span<const Event>)override{if(!validation)std::memcpy(a,b,n);return next_handle();}
 Event marker(std::span<const Event>)override{return next_handle();}
 Event compute(const Operation& op,std::span<void*const> p,std::span<const Event>)override{if(!validation)dynamic_cast<const HostOperation&>(op).run(p);return next_handle();}
 bool complete(Event)override{return true;}bool wait(Event,Deadline)override{return true;}EventTiming timing(Event)override{return {};}
 void synchronize()override{}void clear_events()override{}void close_queue()override{}void close_context()override{}
};
#endif
struct Runner {
 Device device;CopyEngine copy;std::vector<Allocation> owned;unsigned serial=0;
 static std::unique_ptr<Backend> backend(unsigned card){
#ifdef OWN_RT_HOST_ONLY
 (void)card;return std::make_unique<Cpu>();
#else
 return make_sycl_device(card,true);
#endif
 }
 explicit Runner(unsigned card):device(backend(card)),copy(device){}
 Allocation alloc(size_t n,Memory m=Memory::device){auto id=device.arena.allocate("p28-"+std::to_string(serial++),std::max(n,size_t(16)),m,Category::scratch,Lifetime::transaction);owned.push_back(id);return id;}
 void finish(Event e){if(!device.wait(e,std::chrono::seconds(300)))throw std::runtime_error("p28 submission deadline: 300 s");check_stop();}
 Allocation upload(const void* p,size_t n){auto h=alloc(n,Memory::pinned),d=alloc(n);if(!validation)std::memcpy(device.arena.row(h).pointer,p,n);finish(copy.copy(d,0,h,0,n,{}));return d;}
 Allocation tiled(const std::vector<uint8_t>& seed,size_t n){auto d=alloc(n);size_t chunk=std::min(n,std::max(seed.size(),size_t(4*1024*1024)/seed.size()*seed.size()));auto h=alloc(chunk,Memory::pinned);if(!validation)for(size_t off=0;off<chunk;off+=seed.size())std::memcpy(static_cast<uint8_t*>(device.arena.row(h).pointer)+off,seed.data(),std::min(seed.size(),chunk-off));for(size_t off=0;off<n;off+=chunk)finish(copy.copy(d,off,h,0,std::min(chunk,n-off),{}));return d;}
 std::vector<uint16_t> read(Allocation src,size_t n){std::vector<uint16_t> values(n);auto h=alloc(n*2,Memory::pinned);finish(copy.copy(h,0,src,0,n*2,{}));if(!validation)std::memcpy(values.data(),device.arena.row(h).pointer,n*2);return values;}
 void clear(){device.retire_completed_events();for(auto a:owned)device.arena.release(a);owned.clear();}
};
uint32_t random(uint32_t& s){s^=s<<13;s^=s>>17;s^=s<<5;return s;}
std::vector<uint8_t> seed(const p28::Shape& s,unsigned variant,unsigned projection,unsigned mode){auto fmt=iq3::layout(s.type);size_t rb=size_t(s.k)/fmt.elements*fmt.bytes;std::vector<uint8_t> w(rb*17);uint32_t state=0x45678901u+projection;for(auto& b:w)b=random(state);
 if(fmt.elements==1){for(size_t i=0;i<size_t(s.k)*17;++i){float value=float(int(random(state)%63)-31)/64;uint32_t bits=std::bit_cast<uint32_t>(value);if(mode==3){constexpr uint32_t special[]{0x7fc10000,0xffc10000,0x7f800000,0xff800000,0,0x80000000,1,0x80000001};bits=special[i%8];}if(s.type==iq3::Type::F32)for(unsigned j=0;j<4;++j)w[i*4+j]=bits>>(8*j);else{auto b=iq3::bf16_bits(iq3::bits_float(bits));w[i*2]=b&255;w[i*2+1]=b>>8;}}}
 else for(size_t off=0;off<w.size();off+=fmt.bytes){size_t at=off+(s.type==iq3::Type::Q6_K?208:0);uint16_t half=uint16_t(0x1800+random(state)%0x1000);if(mode==3){constexpr uint16_t special[]{0x7e01,0xfe01,0x7c00,0xfc00,0,0x8000,1,0x8001};half=special[(off/fmt.bytes)%8];}if(mode==2){constexpr uint16_t tiny[]{0,0x8000,1,0x8001,0x03ff,0x83ff,0x0400,0x8400};half=tiny[(off/fmt.bytes)%8];}w[at]=half&255;w[at+1]=half>>8;}
 return arithmetic::is_expanded(variant)?iq3::expanded::expand(s.type,w.data(),w.size(),s.k):w;
}
bool nan(uint16_t a){return (a&0x7f80)==0x7f80&&(a&0x7f);}
bool equivalent(const std::vector<uint16_t>& a,const std::vector<uint16_t>& b,bool nan_equal){if(a.size()!=b.size())return false;for(size_t i=0;i<a.size();++i)if(a[i]!=b[i]&&!(nan_equal&&nan(a[i])&&nan(b[i])))return false;return true;}
struct Fixture {
 std::vector<Matrix> matrices;std::vector<std::vector<uint16_t>> host;std::vector<uint32_t> status;
 Fixture(Runner& r,p28::Shape s,unsigned v,unsigned mode){unsigned experts=s.count>1?512:1;auto rb=arithmetic::row_bytes(s.type,s.k,v);
  std::vector<uint16_t> x(size_t(s.k)*(s.paired?1:s.count));for(size_t i=0;i<x.size();++i){x[i]=iq3::bf16_bits(float(int(i*17%127)-63)/128);if(mode==1)x[i]=i%2?0x8000:0;if(mode==2){constexpr uint16_t tiny[]{0,0x8000,1,0x8001,0x7f,0x807f,0x80,0x8080};x[i]=tiny[i%8];}if(mode==3){constexpr uint16_t special[]{0x7fc1,0xffc1,0x7f80,0xff80,0,0x8000,1,0x8001};x[i]=special[i%8];}if(mode==4){constexpr uint16_t extreme[]{0,0x8000,0x4f00,0xcf00,0x3000,0xb000,0x3f80,0xbf80};x[i]=extreme[i%8];}}
  auto xid=r.upload(x.data(),x.size()*2);constexpr unsigned ids[]{1,37,107,203,311,0,509,222,405,154};std::array<iq3::Route,10> routes{};for(unsigned i=0;i<s.count;++i)routes[i]={ids[i],0,s.rows};if(mode==5&&s.count>1){routes[0].expert_id=512;routes[1].row_begin=s.rows+1;routes[2].row_count=s.rows+1;routes[3].row_count=0;routes[4].row_begin=1;routes[4].row_count=s.rows-2;}for(unsigned i=0;i<s.count;++i)status.push_back(iq3::valid_route(routes[i],experts,s.rows,s.rows)?0:1);auto rid=s.count>1?r.upload(routes.data(),s.count*sizeof(iq3::Route)):Allocation(0);
  for(unsigned j=0;j<(s.paired?2u:1u);++j){auto eight=seed(s,v,j,mode);Matrix m{};m.type=s.type;m.rows=s.rows;m.columns=s.k;m.experts=experts;m.count=s.count;m.span=s.rows;m.routes=rid;m.status=s.count>1?r.alloc(s.count*4):Allocation(0);m.w=r.tiled(eight,size_t(experts)*s.rows*rb);m.x=xid;m.y=r.alloc(size_t(s.count)*s.rows*2);m.workspace=r.alloc(size_t(s.count)*s.rows*8*4);matrices.push_back(m);
   std::vector<uint16_t> expected(size_t(s.count)*s.rows);if(!validation)for(unsigned slot=0;slot<s.count;++slot){uint16_t cache[17];for(unsigned row=0;row<17;++row)cache[row]=iq3::bf16_bits(arithmetic::row(s.type,eight.data()+row*rb,x.data()+(s.paired?0:size_t(slot)*s.k),s.k,v));for(unsigned row=0;row<s.rows;++row)expected[size_t(slot)*s.rows+row]=s.count>1?(status[slot]||row>=routes[slot].row_count?iq3::bf16_bits(iq3::bits_float(0x7fc00000)):cache[(size_t(routes[slot].expert_id)*s.rows+routes[slot].row_begin+row)%17]):cache[row%17];}host.push_back(std::move(expected));
  }
 }
};
void poison(Runner& r,Fixture& f){if(validation)return;for(auto& m:f.matrices){std::vector<uint16_t> sentinel(size_t(m.rows)*m.count,0xdead);auto h=r.alloc(sentinel.size()*2,Memory::pinned);std::memcpy(r.device.arena.row(h).pointer,sentinel.data(),sentinel.size()*2);r.finish(r.copy.copy(m.y,0,h,0,sentinel.size()*2,{}));if(m.status){auto hstatus=r.alloc(m.count*4,Memory::pinned);std::memset(r.device.arena.row(hstatus).pointer,0xcd,m.count*4);r.finish(r.copy.copy(m.status,0,hstatus,0,m.count*4,{}));}}}
bool statuses(Runner& r,Fixture& f){for(auto& m:f.matrices)if(m.status){auto actual=r.read(m.status,m.count*2);if(std::memcmp(actual.data(),f.status.data(),m.count*4))return false;}return true;}
std::string current_kernel(const p28::Shape& s,unsigned v){return s.count>1?(s.paired?"integrated::experts/iq3::kopt4::expert_gate_up(split=1)":"integrated::experts/iq3::kopt4::expert_down(split=1)"):std::string("integrated::dense/")+arithmetic::name(v);}
Launch baseline(Runner& r,Fixture& f,p28::Shape s,unsigned v){
#ifdef OWN_RT_HOST_ONLY
 p28_validation::baseline(r.device,f.matrices,v,s.paired);
#endif
 return s.count>1?integrated::experts(r.device,f.matrices,s.paired):integrated::dense(r.device,f.matrices[0],v);
}
}
int main(int argc,char** argv){std::unique_ptr<Runner> runner;Options o;unsigned checks=0,failures=0,negative=0;try{std::signal(SIGTERM,stop_requested);std::signal(SIGINT,stop_requested);o=options(argc,argv);check_stop();std::filesystem::create_directories(o.output);
#ifndef OWN_RT_HOST_ONLY
 if(o.mode=="K0"){std::vector<sycl::device> devices;for(auto p:sycl::platform::get_platforms())if(p.get_backend()==sycl::backend::ext_oneapi_level_zero)for(auto d:p.get_devices(sycl::info::device_type::gpu))devices.push_back(d);if(o.card>=devices.size())throw std::invalid_argument("K0 card range");auto ids=sycl::get_kernel_ids();if(ids.empty())throw std::runtime_error("K0 has no linked kernels");{auto d=devices[o.card];sycl::context context(d);auto input=sycl::get_kernel_bundle<sycl::bundle_state::input>(context,{d},ids);auto executable=sycl::build(input,{d});for(auto id:ids)if(!executable.has_kernel(id,d))throw std::runtime_error("K0 kernel missing from executable bundle");}check_stop();std::ofstream(o.output/"receipt.json")<<"{\"passed\":true,\"completed\":true,\"safe_to_exit\":true,\"device_executed\":true,\"kernel_execution\":false,\"mode\":\"K0\",\"live_bytes\":0,\"in_flight\":0,\"finite_element_gate_failures\":0,\"kernels\":"<<ids.size()<<"}\n";return 0;}
#endif
 runner=std::make_unique<Runner>(o.card);auto& r=*runner;std::ofstream exact(o.output/"exactness.jsonl"),timing(o.output/"timing.jsonl"),validation_log(o.output/"validation-entries.jsonl");
 for(auto production:p28::shapes){check_stop();auto s=production;unsigned v=arithmetic::r5_variant(s.type,s.rows,s.k,s.count>1?512:1,false);if(cpu_fixtures||o.mode=="K0")s.rows=9;
  std::set<std::string> excluded;bool baseline_failed=false;auto choices=p28::candidates(s.type);
  for(unsigned mode=0;mode<(validation||o.mode=="K0"?1u:(s.count>1?6u:5u));++mode){Fixture f(r,s,v,mode);std::vector<std::vector<uint16_t>> current;
   poison(r,f);auto b=baseline(r,f,s,v);r.finish(b.last);
   if(validation){for(auto& name:choices){p28::validate(r.device,f.matrices,name,s.paired,v);++checks;validation_log<<"{\"workload\":"<<quote(s.label)<<",\"candidate\":"<<quote(name)<<",\"device_argument_validation\":true}\n";
     for(unsigned mutation=0;mutation<7;++mutation){auto bad=f.matrices;if(mutation==0)bad[0].columns=0;if(mutation==1)bad[0].rows=0;if(mutation==2)bad[0].activation=iq3::Type::F32;if(mutation==3)bad[0].output_type=iq3::Type::F32;if(mutation==4)bad[0].y=bad[0].x;if(mutation==5)bad[0].span=bad[0].rows+1;if(mutation==6)bad[0].workspace=bad[0].x;bool rejected=false;try{p28::validate(r.device,bad,name,s.paired,v);}catch(const std::invalid_argument&){rejected=true;}if(!rejected)throw std::runtime_error("negative candidate validation escaped: "+name+" mutation "+std::to_string(mutation));++negative;}}
    r.clear();continue;}
   std::string current_hashes;for(size_t j=0;j<f.matrices.size();++j){current.push_back(r.read(f.matrices[j].y,f.host[j].size()));current_hashes+=packet26::hash(current[j].data(),current[j].size()*2)+":";if(!equivalent(current[j],f.host[j],true))baseline_failed=true;}if(!statuses(r,f))baseline_failed=true;++checks;exact<<"{\"class\":"<<quote(s.klass)<<",\"workload\":"<<quote(s.label)<<",\"candidate\":\"r5\",\"current_kernel\":"<<quote(current_kernel(s,v))<<",\"mode\":"<<mode<<",\"passed\":"<<(!baseline_failed?"true":"false")<<",\"output_hashes\":"<<quote(current_hashes)<<",\"host_nan_equivalence\":true}\n";exact.flush();
   if(baseline_failed){++failures;excluded.insert(choices.begin(),choices.end());}
   for(auto& name:choices){if(excluded.count(name))continue;try{poison(r,f);auto event=p28::submit(r.device,f.matrices,name,s.paired,v);r.finish(event.last);bool passed=true,bytes=true;std::string output_hashes;for(size_t j=0;j<f.matrices.size();++j){auto actual=r.read(f.matrices[j].y,f.host[j].size());output_hashes+=packet26::hash(actual.data(),actual.size()*2)+":";bytes=bytes&&equivalent(actual,current[j],false);passed=passed&&equivalent(actual,current[j],cpu_fixtures)&&equivalent(actual,f.host[j],true);}passed=passed&&statuses(r,f);++checks;exact<<"{\"class\":"<<quote(s.klass)<<",\"workload\":"<<quote(s.label)<<",\"candidate\":"<<quote(name)<<",\"mode\":"<<mode<<",\"passed\":"<<(passed?"true":"false")<<",\"output_hashes\":"<<quote(output_hashes)<<",\"new_current_bytes_equal\":"<<(bytes?"true":"false")<<"}\n";exact.flush();if(!passed)throw std::runtime_error("candidate output mismatch");}
    catch(const std::invalid_argument& e){excluded.insert(name);++failures;exact<<"{\"class\":"<<quote(s.klass)<<",\"workload\":"<<quote(s.label)<<",\"candidate\":"<<quote(name)<<",\"mode\":"<<mode<<",\"passed\":false,\"error\":"<<quote(e.what())<<"}\n";exact.flush();}
    catch(const std::runtime_error& e){if(std::string(e.what())!="candidate output mismatch")throw;excluded.insert(name);++failures;std::cerr<<s.label<<" "<<name<<": "<<e.what()<<"\n";}
   }r.clear();
  }
  if(!validation&&!cpu_fixtures&&o.mode=="G2"&&!baseline_failed){Fixture f(r,production,v,0);std::vector<std::string> timed{"r5"};for(auto& c:choices)if(!excluded.count(c))timed.push_back(c);
   for(auto& name:timed){try{for(unsigned repetition=0;repetition<200;++repetition){check_stop();auto event=name=="r5"?baseline(r,f,production,v):p28::submit(r.device,f.matrices,name,s.paired,v);r.finish(event.last);unsigned index=0;for(Event e=event.first;e<=event.last;++e){auto t=r.device.timing(e);timing<<"{\"class\":"<<quote(s.klass)<<",\"workload\":"<<quote(s.label)<<",\"candidate\":"<<quote(name)<<",\"current_kernel\":"<<quote(current_kernel(s,v))<<",\"repetition\":"<<repetition<<",\"event_index\":"<<index++<<",\"event_count\":"<<event.passes<<",\"start_ns\":"<<t.start_ns<<",\"end_ns\":"<<t.end_ns<<",\"exact\":true,\"rows\":"<<production.rows<<",\"columns\":"<<production.k<<"}\n";}r.device.retire_completed_events();}}catch(const std::invalid_argument& e){++failures;exact<<"{\"class\":"<<quote(s.klass)<<",\"workload\":"<<quote(s.label)<<",\"candidate\":"<<quote(name)<<",\"phase\":\"timing\",\"passed\":false,\"error\":"<<quote(e.what())<<"}\n";exact.flush();if(name=="r5")break;}}timing.flush();r.clear();}
 }
 auto state=r.device.shutdown(std::chrono::seconds(60));if(!state.safe_to_exit||state.exit_code)throw std::runtime_error("owner teardown incomplete");std::ofstream(o.output/"receipt.json")<<"{\"passed\":"<<(failures?"false":"true")<<",\"completed\":true,\"safe_to_exit\":true,\"device_executed\":"<<((validation||cpu_fixtures)?"false":"true")<<",\"mode\":"<<quote(o.mode)<<",\"live_bytes\":"<<state.live_bytes<<",\"in_flight\":"<<state.in_flight<<",\"finite_element_gate_failures\":"<<failures<<",\"checks\":"<<checks<<",\"negative_validation_checks\":"<<negative<<",\"teardown\":"<<state.json()<<"}\n";return failures?2:0;
 }catch(const std::exception& e){std::cerr<<e.what()<<"\n";if(runner)packet26::failure(runner->device,o.output,e.what());else if(!o.output.empty())std::ofstream(o.output/"failure.json")<<"{\"passed\":false,\"error\":"<<quote(e.what())<<"}\n";return 1;}
}
