// The runtime planner, Engine and submission implementations are compiled from
// packet29 without a semantic edit. Device uses its qualified capture mirror.
#ifndef P29_MAIN
#define P29_MAIN "../packet29-merged/main.cpp"
#endif
#define main packet29_unused_entry
#include P29_MAIN
#undef main
#include "fixture34.hpp"
#include "backend34.hpp"
#include <time.h>
#include <numeric>
namespace replay34 {
using Clock=std::chrono::steady_clock;
static uint64_t ns(){return std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now().time_since_epoch()).count();}
static uint64_t cpu_ns(){timespec t{};if(clock_gettime(CLOCK_THREAD_CPUTIME_ID,&t))throw std::runtime_error("thread CPU clock");return uint64_t(t.tv_sec)*1000000000+t.tv_nsec;}
static size_t rss(){std::ifstream f("/proc/self/status");std::string line;while(std::getline(f,line))if(line.starts_with("VmRSS:")){std::istringstream s(line.substr(6));size_t k;s>>k;return k*1024;}throw std::runtime_error("RSS unavailable");}
struct Control {uint32_t iteration,position,parity,seed;};
struct Boundary
#ifdef OWN_RT_HOST_ONLY
 final:HostOperation
#else
 final:ownrt::SyclOperation
#endif
{
 size_t n;
 explicit Boundary(size_t size):n(size){}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override{
  auto c=static_cast<const Control*>(p[0]);auto banks=static_cast<const uint16_t*>(p[1]);auto out=static_cast<uint16_t*>(p[2]);
  for(size_t i=0;i<n;++i)out[i]=banks[(c->parity%2)*n+i];
  *static_cast<uint32_t*>(p[3])=c->position;*static_cast<uint32_t*>(p[4])=1;
 }
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{
  auto c=static_cast<const Control*>(p[0]);auto banks=static_cast<const uint16_t*>(p[1]);auto out=static_cast<uint16_t*>(p[2]);
  auto pos=static_cast<uint32_t*>(p[3]);auto active=static_cast<uint32_t*>(p[4]);auto size=n;
  return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::range<1>(size),packet26::checked([=](sycl::id<1> id){auto i=id[0];out[i]=banks[(c->parity%2)*size+i];if(!i){*pos=c->position;*active=1;}}));});
 }
#endif
};
#ifdef OWN_RT_HOST_ONLY
class Cpu final:public packet18::LifetimeMock {
public:
 bool census=false;size_t submissions=0;
 explicit Cpu(bool c):census(c){}
 ownrt::Event copy(void* a,const void* b,size_t n,std::span<const ownrt::Event> d)override{
  if(census)return marker(d);auto e=LifetimeMock::copy(a,b,n,d);finish(e);return e;
 }
 ownrt::Event compute(const ownrt::Operation& o,std::span<void*const> p,std::span<const ownrt::Event> d)override{
  ++submissions;if(!census)dynamic_cast<const HostOperation&>(o).run(p);return marker(d);
 }
};
#endif
struct Fixture {
 Engine& e;bool census;
 std::vector<Allocation> state;
 std::map<Allocation,std::string> names;
 Allocation control=0,banks=0;
 size_t weights_bytes=0,state_bytes=0;
 std::set<unsigned> parities,attention_counts;
 std::set<std::string> routed_sets;
 std::string boundary_hash;
 Fixture(Engine& engine,bool no_data):e(engine),census(no_data){}
 void zero(Allocation id){if(census)return;size_t bytes=e.dev(0).arena.row(id).bytes;std::vector<uint8_t> v(std::min(bytes,size_t(4*1024*1024)),0);for(size_t off=0;off<bytes;off+=v.size())e.upload(0,id,off,v.data(),std::min(v.size(),bytes-off));}
 Allocation alloc(const std::string& name,size_t n,bool immutable=false){
  auto id=e.allocate(0,name,n,immutable?Category::weights:Category::scratch,immutable?Lifetime::process:Lifetime::transaction);
  if(immutable)weights_bytes+=n;else{state.push_back(id);names[id]=name;state_bytes+=n;zero(id);}return id;
 }
 void setup(){
  e.owned_bytes={0};e.buffers.resize(1);e.weights.resize(1);e.selected.resize(1);e.loaded_layer={-1};
  e.fp32_sources={0};e.fp32_extents={0};e.submission_card=0;
  e.slab={e.allocate(0,"bounded-copy",4*1024*1024,Category::pinned_slab,Lifetime::transfer,Memory::pinned)};
  e.controls={alloc("parallel-controls",12)};e.scores={alloc("scores",24*(e.p.g.budget+3)*4)};e.probabilities={alloc("probabilities",24*(e.p.g.budget+3)*4)};
  e.workspace={alloc("gemv-workspace",8*1024*1024)};
  e.scratch={alloc("operator-scratch",e.a.mini?2*1024*1024:256*1024*1024)};
  e.mixture_out={alloc("mixture",e.p.g.h*2)};e.compact_routes={alloc("compact-routes",e.p.g.top*sizeof(iq3::Route))};
  e.fp32_inputs={alloc("fp32-input",174080*4)};
  e.one={alloc("one",4,true)};float one=1;if(!census)e.upload(0,e.one[0],0,&one,4);
  e.ropes={alloc("rope",rope_constants::bytes,true)};
  if(!census){std::ifstream f(fs::path(__FILE__).parent_path()/"../packet29-merged/rope.bf16",std::ios::binary);std::vector<uint8_t> b((std::istreambuf_iterator<char>(f)),{});require(b.size()==rope_constants::bytes&&hash(b)==rope_constants::sha256,"rope bytes");e.upload(0,e.ropes[0],0,b.data(),b.size());}
  for(const auto& b:e.p.buffers){auto n=count(b.shape);auto id=alloc(b.name,n*flash::scalar_bytes(b.type));e.buffers[0][b.name]={id,n,b.type};}
  control=alloc("host-control",sizeof(Control));banks=alloc("ping-pong-inputs",2*4*e.p.g.h*2);
  std::map<std::string,Allocation> unique;
  for(const auto& l:e.p.launches)for(const auto& name:l.weights){
   auto key=fixture34::canonical(name);if(!unique.contains(key)){
    const auto& t=e.w.directory.at(key);auto variant=e.weight_variant(name);auto type=flash::grid_type(t.grid);
    bool expanded=arithmetic::is_expanded(variant);
    size_t bytes=expanded?size_t(t.shape[0])*arithmetic::row_bytes(type,t.shape[1],variant):t.bytes;
    auto id=alloc("weight:"+key,bytes,true);unique[key]=id;
    if(!census&&expanded){
     auto fmt=iq3::layout(type);size_t rb=t.shape[1]/fmt.elements*fmt.bytes,er=arithmetic::row_bytes(type,t.shape[1],variant);
     size_t rows_per=std::max(size_t(1),size_t(4*1024*1024)/std::max(rb,er));
     for(size_t row=0;row<size_t(t.shape[0]);row+=rows_per){auto nr=std::min(rows_per,size_t(t.shape[0])-row);auto raw=fixture34::generated(t,row*rb,nr*rb);auto v=iq3::expanded::expand(type,raw.data(),raw.size(),t.shape[1]);e.upload(0,id,row*er,v.data(),v.size());}
    }else if(!census)for(size_t off=0;off<t.bytes;off+=4*1024*1024){auto v=fixture34::generated(t,off,std::min(t.bytes-off,size_t(4*1024*1024)));e.upload(0,id,off,v.data(),v.size());}
   }e.weights[0][name]=unique.at(key);
  }
  e.prepare_plan();
 }
 void boundary(unsigned k){
  Control c{k,k%unsigned(e.p.g.context-1),k%2,0x34u+k};e.upload(0,control,0,&c,sizeof c);
  size_t n=4*e.p.g.h;std::vector<uint16_t> slots(2*n);
  for(size_t i=0;i<slots.size();++i)slots[i]=iq3::bf16_bits(float(int(fixture34::mix(c.seed+i)%257)-128)/128.f);
  e.upload(0,banks,0,slots.data(),slots.size()*2);
  Boundary op(n);std::array ids{control,banks,e.buffers[0].at("streams").id,e.buffers[0].at("position").id,e.buffers[0].at("active").id};
  e.wait(0,e.dev(0).compute(op,ids,{}));e.dev(0).retire_completed_events();
  auto actual=e.readback(0,e.buffers[0].at("streams").id,n*2);
  require(std::memcmp(actual.data(),slots.data()+c.parity*n,n*2)==0,"device parity selector did not choose uploaded bank");
  require(e.integer(0,"position")==int(c.position),"boundary position not device data");
  require(e.integer(0,"active")==1,"boundary active control");
  parities.insert(c.parity);boundary_hash=hash(actual);
 }
 std::string dynamic(unsigned k,std::ofstream& log){
  unsigned pos=k%unsigned(e.p.g.context-1);
  const unsigned expected=std::min((pos+1)/4,unsigned(e.p.g.budget/4))*4+(pos+1)%4;
  std::vector<unsigned> counts;
  for(const auto& [name,b]:e.buffers[0])if(name.ends_with(".ids")&&name.find("qsa")!=std::string::npos){
   require(b.type==Scalar::i32,"QSA ids type");
   auto raw=e.readback(0,b.id,b.n*4);unsigned count=0;bool sentinel=false;
   for(size_t j=0;j<b.n;++j){int32_t id;std::memcpy(&id,raw.data()+j*4,4);
    if(id==-1){sentinel=true;continue;}
    require(!sentinel&&id>=0&&unsigned(id)<=pos,"invalid/non-prefix dynamic attention ids");++count;
   }
   require(count==expected,"attention slot count not derived from changing device position");
   attention_counts.insert(count);counts.push_back(count);
  }
  require(counts.size()==6,"six QSA dynamic slot lists required");
  auto route=routes();std::vector<uint8_t> set_bytes;
  for(const auto& [name,b]:e.buffers[0])if(name.ends_with(".ids")&&name.find("qsa")==std::string::npos){
   auto raw=e.readback(0,b.id,b.n*4);std::vector<uint32_t> ids(b.n);std::memcpy(ids.data(),raw.data(),raw.size());std::sort(ids.begin(),ids.end());
   require(std::adjacent_find(ids.begin(),ids.end())==ids.end()&&ids.back()<unsigned(e.p.g.experts),"route IDs must be distinct and valid");
   auto at=set_bytes.size();set_bytes.resize(at+raw.size());std::memcpy(set_bytes.data()+at,ids.data(),raw.size());
  }
  auto set_hash=hash(set_bytes);routed_sets.insert(set_hash);
  log<<"{\"iteration\":"<<k<<",\"position\":"<<pos<<",\"parity\":"<<k%2
     <<",\"selected_input_sha256\":"<<ownrt::quote(boundary_hash)<<",\"route_sha256\":"<<ownrt::quote(route)<<",\"routed_set_sha256\":"<<ownrt::quote(set_hash)<<",\"attention_counts\":[";
  for(size_t i=0;i<counts.size();++i)log<<(i?",":"")<<counts[i];log<<"]}\n";log.flush();require(bool(log),"dynamic evidence write");
  return route;
 }
 using Snapshot=std::vector<std::vector<uint8_t>>;
 Snapshot snapshot(){Snapshot out;for(auto id:state)out.push_back(e.readback(0,id,e.dev(0).arena.row(id).bytes));return out;}
 void restore(const Snapshot& v){require(v.size()==state.size(),"snapshot extent");for(size_t i=0;i<state.size();++i)e.upload(0,state[i],0,v[i].data(),v[i].size());}
 size_t compare(const Snapshot& expected){size_t checks=0;for(size_t i=0;i<state.size();++i){auto bytes=e.readback(0,state[i],expected[i].size());require(bytes==expected[i],"byte mismatch: "+names.at(state[i]));++checks;}return checks;}
 std::string digest(const Snapshot& v){EVP_MD_CTX* ctx=EVP_MD_CTX_new();require(ctx,"SHA context");EVP_DigestInit_ex(ctx,EVP_sha256(),nullptr);for(auto& b:v)EVP_DigestUpdate(ctx,b.data(),b.size());unsigned char out[32];unsigned n;EVP_DigestFinal_ex(ctx,out,&n);EVP_MD_CTX_free(ctx);std::string s;for(auto b:out){s+="0123456789abcdef"[b>>4];s+="0123456789abcdef"[b&15];}return s;}
 std::string routes(){std::vector<uint8_t> all;for(const auto& [name,b]:e.buffers[0])if(name.ends_with(".ids")&&name.find("qsa")==std::string::npos){auto v=e.readback(0,b.id,b.n*flash::scalar_bytes(b.type));all.insert(all.end(),v.begin(),v.end());}return hash(all);}
 void validate(unsigned k){require(e.integer(0,"error")==0,"sticky runtime error");require(e.integer(0,"position")==int(k%unsigned(e.p.g.context-1)+1),"commit position did not change");auto v=e.readback(0,e.buffers[0].at("streams").id,4*e.p.g.h*2);for(size_t i=0;i<v.size();i+=2){uint16_t bits;std::memcpy(&bits,v.data()+i,2);require((bits&0x7f80)!=0x7f80,"nonfinite output");}}
};
// Deep clone immutable launch commands, including their strings and vectors.
// This is a CPU model of value capture, not an ABI claim about SYCL closures.
struct MockRecording {
 std::vector<flash::Launch> commands;
 std::vector<std::pair<size_t,size_t>> groups;
 explicit MockRecording(Engine& e):commands(e.p.launches){
  for(size_t i=0;i<commands.size();++i){auto* original=&e.p.launches[i];auto* copy=&commands[i];
   if(e.gemv_choices.contains(original))e.gemv_choices[copy]=e.gemv_choices.at(original);
   if(e.matrices.contains(original))e.matrices[copy]=e.matrices.at(original);
   if(e.prepared.contains(original))e.prepared[copy]=e.prepared.at(original);
  }
  int previous=-1;
  for(size_t i=0;i<commands.size();++i){
   const auto& l=commands[i];int layer=l.label.starts_with("blk.")?std::stoi(l.label.substr(4)):l.op=="begin"?24:47;
   if(layer!=previous){if(!groups.empty())groups.back().second=i;groups.emplace_back(i,commands.size());previous=layer;}
  }
  require(groups.size()==24,"mock per-layer graph partition");
 }
 void replay(Engine& e,bool layers){
  if(layers){for(const auto& [begin,end]:groups)for(size_t i=begin;i<end;++i)e.enqueue(commands[i],e.logical);}
  else for(const auto& command:commands)e.enqueue(command,e.logical);
 }
};
static void execute(Engine& e){for(const auto& l:e.p.launches)e.enqueue(l,e.logical);}
struct Measurement {uint64_t wall=0,cpu=0,gpu=0;size_t submissions=0;std::vector<uint64_t> kernels;};
static Measurement direct(Engine& e){
 auto first=e.submitted;auto c=cpu_ns(),w=ns();execute(e);
 if(e.tail)e.wait(0,e.tail);Measurement m;m.wall=ns()-w;m.cpu=cpu_ns()-c;m.submissions=e.submitted-first;
#ifndef OWN_RT_HOST_ONLY
 for(const auto& item:e.pending)for(auto id=item.launch.first;id<=item.launch.last;++id){auto t=e.dev(0).timing(id);require(t.start_ns&&t.end_ns>=t.start_ns,"direct GPU profiling unavailable");auto dt=t.end_ns-t.start_ns;require(dt<=4000000000ull,"individual kernel budget 4s exceeded");m.kernels.push_back(dt);m.gpu+=dt;}
 require(m.kernels.size()==m.submissions,"physical launch/event count");
#endif
 e.pending.clear();e.tail=0;e.dev(0).retire_completed_events();return m;
}
static void row(std::ofstream& f,const char* mode,unsigned k,const Measurement& m,const std::string& digest){
 f<<"{\"mode\":"<<ownrt::quote(mode)<<",\"iteration\":"<<k<<",\"warmup\":"<<(k<10?"true":"false")<<",\"wall_ns\":"<<m.wall<<",\"thread_cpu_ns\":"<<m.cpu<<",\"submissions\":"<<m.submissions<<",\"direct_gpu_ns\":";
#ifdef OWN_RT_HOST_ONLY
 f<<"null";
#else
 if(std::string(mode)=="direct")f<<m.gpu;else f<<"null";
#endif
 f<<",\"state_sha256\":"<<ownrt::quote(digest)<<",\"kernel_ns\":[";for(size_t j=0;j<m.kernels.size();++j)f<<(j?",":"")<<m.kernels[j];f<<"]}\n";f.flush();require(bool(f),"measurement write");
}
#ifndef OWN_RT_HOST_ONLY
static std::vector<size_t> record(Engine& e,Native& native,bool layers,std::ofstream& log,int repetition){
 std::vector<size_t> ids;size_t first=e.submitted;uint64_t start=ns();size_t before=rss();auto driver_before=native.driver_memory();int previous=-1;
 for(size_t i=0;i<e.p.launches.size();++i){auto& l=e.p.launches[i];int layer=l.label.starts_with("blk.")?std::stoi(l.label.substr(4)):l.op=="begin"?24:47;
  if(i==0||(layers&&layer!=previous)){
   if(i){native.end();e.pending.clear();e.tail=0;e.dev(0).retire_completed_events();}
   ids.push_back(native.begin());
  }
  e.enqueue(l,e.logical);previous=layer;
 }
 native.end();e.pending.clear();e.tail=0;e.dev(0).retire_completed_events();
 size_t nodes=0;for(auto i:ids)nodes+=native.nodes(i);require(nodes==e.submitted-first,"graph physical node count");
 log<<"{\"mode\":"<<ownrt::quote(layers?"graph-layer":"graph-whole")<<",\"recording\":"<<repetition<<",\"record_finalize_ns\":"<<ns()-start<<",\"host_rss_before\":"<<before<<",\"host_rss_after\":"<<rss()<<",\"application_device_bytes\":"<<e.dev(0).arena.total(Memory::device)<<",\"graph_required_bytes_total\":"<<native.graph_bytes()<<",\"graphs_retained\":"<<native.graph_count()<<",\"nodes\":"<<nodes<<",\"driver_memory_before\":"<<driver_before<<",\"driver_memory_after\":"<<native.driver_memory()<<"}\n";log.flush();return ids;
}
static Measurement replay(Native& n,const std::vector<size_t>& graphs){
 auto c=cpu_ns(),w=ns();for(auto id:graphs){require(!stopped,"cooperative stop before graph submit");n.replay(id);}require(n.drain_replay(Clock::now()+std::chrono::seconds(60)),"graph drain deadline");
 Measurement m;m.wall=ns()-w;m.cpu=cpu_ns()-c;m.submissions=graphs.size();require(m.wall<=60000000000ull,"half-token graph budget60s");return m;
}
#endif
} // namespace replay34
#ifndef BENCH_ENTRY
#define BENCH_ENTRY main
#endif
int BENCH_ENTRY(int argc,char** argv){
 using namespace replay34;Options a;a.mini=true;a.context=256;a.seconds=1800;a.wait_seconds=60;a.timing="class";
 bool census=false,cpu=false,authorized=false,teardown_attempted=false;int card=-1;fs::path output;std::unique_ptr<Engine> e;
#ifndef OWN_RT_HOST_ONLY
 Native* native=nullptr;
#endif
 try{
  for(int i=1;i<argc;++i){std::string arg=argv[i];auto value=[&]{require(i+1<argc,"argument value");return std::string(argv[++i]);};
   if(arg=="--card")card=std::stoi(value());else if(arg=="--output")output=value();else if(arg=="--cpu-test")cpu=true;else if(arg=="--census")census=true;else if(arg=="--authorized-device-window")authorized=true;else throw std::runtime_error("unknown/unsupported argument: "+arg);
  }
  require(!output.empty(),"output required");fs::create_directories(output);a.output=output;
  require(getenv("OMP_NUM_THREADS")&&std::string(getenv("OMP_NUM_THREADS"))=="2","OMP_NUM_THREADS=2");
#ifdef OWN_RT_HOST_ONLY
  require(!authorized&&(cpu!=census),"CPU gate/census only");
#else
  require(authorized&&!cpu&&!census&&card>=0&&card<4,"single-card authorization");
#endif
  std::signal(SIGTERM,stop);std::signal(SIGINT,stop);
  packet26::dispatch.load((fs::path(__FILE__).parent_path()/"dispatch-measured.json").string());
  Weights w(a);auto p=fixture34::make_plan(w,a,cpu);size_t generator_checks=fixture34::generator_gate(w,p);
  e=std::make_unique<Engine>(w,a,std::move(p));
#ifdef OWN_RT_HOST_ONLY
  e->devices.push_back(std::make_unique<ownrt::Device>(std::make_unique<Cpu>(census)));
#else
  auto backend=std::make_unique<Native>(card);native=backend.get();e->devices.push_back(std::make_unique<ownrt::Device>(std::move(backend)));
#endif
  Fixture f(*e,census);f.setup();
  save(output/"allocations.json",e->dev(0).arena.census());
  if(census){
   size_t native_extra=0;std::ofstream plan_rows(output/"launch-plan.jsonl");
   for(const auto& l:e->p.launches){auto before=e->submitted;e->enqueue(l,e->logical);size_t extra=0;
    if(l.op=="gemv"){const auto& choice=e->gemv_choices.at(&l);if(choice.first.starts_with("p28.")&&choice.first.ends_with("wg32")&&(choice.second[0]==7||choice.second[0]==4))extra=1;}
    native_extra+=extra;
    plan_rows<<"{\"label\":"<<ownrt::quote(l.label)<<",\"op\":"<<ownrt::quote(l.op)<<",\"host_submissions\":"<<e->submitted-before<<",\"native_submissions\":"<<e->submitted-before+extra<<",\"native_extra_reason\":"<<ownrt::quote(extra?"p28 split4 wg32 Finish kernel compiled only in device branch":"same host/device submission count")<<"}\n";
   }
   auto count=e->submitted;e->drain();save(output/"census.json","{\"device_executed\":false,\"launches\":"+std::to_string(count)+",\"native_launches_source_census\":"+std::to_string(count+native_extra)+",\"plan_sites\":"+std::to_string(e->p.launches.size())+",\"weights_bytes\":"+std::to_string(f.weights_bytes)+",\"state_bytes\":"+std::to_string(f.state_bytes)+",\"device_bytes\":"+std::to_string(e->dev(0).arena.total(Memory::device))+",\"generator_checks\":"+std::to_string(generator_checks)+"}\n");teardown_attempted=true;e->shutdown();e.reset();return 0;}
  std::ofstream rows(output/"iterations.jsonl"),recordings(output/"recordings.jsonl"),dynamics(output/"dynamic.jsonl");
#ifdef OWN_RT_HOST_ONLY
  MockRecording mock(*e);auto original=e->p.launches.front().label;e->p.launches.front().label="mutation-after-value-clone";require(mock.commands.front().label==original,"mock clone aliases source");e->p.launches.front().label=original;
#else
  std::vector<size_t> whole,layer;
#endif
  std::set<std::string> routes;size_t comparisons=0,launches=0;std::string final_hash;
  // Every direct/graph pair starts from the same full writable state, then
  // the direct result supplies canonical cumulative state for the next token.
  for(unsigned k=0;k<210;++k){
   e->guard();f.boundary(k);auto initial=f.snapshot();auto d=direct(*e);launches=d.submissions;
#ifndef OWN_RT_HOST_ONLY
   require(launches==1142,"physical launch count differs from source census");
#endif
   f.validate(k);auto expected=f.snapshot();final_hash=f.digest(expected);routes.insert(f.dynamic(k,dynamics));row(rows,"direct",k,d,final_hash);
#ifndef OWN_RT_HOST_ONLY
   if(!k){
    for(int repeat=1;repeat<=3;++repeat){auto ids=record(*e,*native,false,recordings,repeat);if(repeat==1)whole=ids;}
    for(int repeat=1;repeat<=3;++repeat){auto ids=record(*e,*native,true,recordings,repeat);if(repeat==1)layer=ids;}
   }
   for(auto mode:{0,1}){f.restore(initial);auto m=replay(*native,mode?layer:whole);comparisons+=f.compare(expected);f.validate(k);row(rows,mode?"graph-layer":"graph-whole",k,m,final_hash);}
#else
   for(auto mode:{0,1}){f.restore(initial);auto before=e->submitted;auto c=cpu_ns(),start=ns();mock.replay(*e,mode!=0);e->drain();Measurement m;m.wall=ns()-start;m.cpu=cpu_ns()-c;m.submissions=e->submitted-before;comparisons+=f.compare(expected);f.validate(k);row(rows,mode?"mock-layer":"mock-whole",k,m,final_hash);}
#endif
   f.restore(expected);
  }
  require(routes.size()>1&&f.routed_sets.size()>1,"no varying routed expert sets: dynamic-state qualification failed");
  require(f.parities.size()==2&&f.attention_counts.size()>1,"missing parity/attention dynamic coverage");
#ifndef OWN_RT_HOST_ONLY
  teardown_attempted=true;
  native->clear_recordings();
#endif
  teardown_attempted=true;
  auto receipts=e->shutdown();
  save(output/"receipt.json","{\"passed\":true,\"safe_to_exit\":true,\"device_executed\":"+std::string(cpu?"false":"true")+",\"launches\":"+std::to_string(launches)+",\"iterations_per_mode\":210,\"warmups\":10,\"measured\":200,\"buffer_byte_comparisons\":"+std::to_string(comparisons)+",\"generator_checks\":"+std::to_string(generator_checks)+",\"route_hashes\":"+std::to_string(routes.size())+",\"routed_sets\":"+std::to_string(f.routed_sets.size())+",\"parities\":"+std::to_string(f.parities.size())+",\"attention_counts\":"+std::to_string(f.attention_counts.size())+",\"final_state_sha256\":"+ownrt::quote(final_hash)+",\"teardown\":"+receipts.at(0)+"}\n");e.reset();return 0;
 }catch(const std::exception& ex){
  std::cerr<<ex.what()<<std::endl;
  if(!output.empty())save(output/"failure.json","{\"passed\":false,\"error\":"+ownrt::quote(ex.what())+",\"recorded_before_teardown\":true}\n");
  if(e&&!e->devices.empty()){
   // A failed clear/shutdown is terminal. Do not retry native destruction from
   // this catch handler or let owner destructors start a second cleanup.
   if(teardown_attempted){
    save(output/"retained-owner.json","{\"retained\":true,\"error\":\"prior teardown failed; cleanup not retried\"}\n");
    ownrt::hold_for_supervisor();
   }
   teardown_attempted=true;
   try{
#ifndef OWN_RT_HOST_ONLY
    if(native){require(native->drain_replay(Clock::now()+std::chrono::seconds(60)),"busy graph retained");native->clear_recordings();}
#endif
    auto r=e->dev(0).shutdown(std::chrono::seconds(60));save(output/"teardown.json",r.json());if(!r.safe_to_exit)throw std::runtime_error("busy owner retained");
   }catch(const std::exception& err){save(output/"retained-owner.json","{\"retained\":true,\"error\":"+ownrt::quote(err.what())+"}\n");ownrt::hold_for_supervisor();}
  }
  e.reset();return 1;
 }
}
