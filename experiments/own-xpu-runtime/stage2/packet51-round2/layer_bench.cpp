#define main packet45_unused_entry
#include "../packet45-merged3/main.cpp"
#undef main
#include "candidate.hpp"
#include "../packet48b-production/candidate.hpp"
#ifndef OWN_RT_HOST_ONLY
#include <sycl/ext/oneapi/backend/level_zero.hpp>
#endif
#include "fixture_bytes.hpp"
#include <numeric>
namespace p51bench {
using iq3::Type;
std::vector<std::string> capture_manifest;
unsigned current_m=1,current_row=0;
void compare_bytes(const std::vector<uint8_t>&actual,const std::vector<uint8_t>&expected,const std::string&name){require(actual.size()==expected.size(),"byte extent mismatch "+name);for(size_t k=0;k<actual.size();++k)if(actual[k]!=expected[k])throw std::runtime_error("raw byte mismatch "+name+" offset="+std::to_string(k)+" expected="+std::to_string(expected[k])+" actual="+std::to_string(actual[k]));}
void compare_maps(const std::map<std::string,std::vector<uint8_t>>&actual,const std::map<std::string,std::vector<uint8_t>>&expected,const std::string&where){require(actual.size()==expected.size(),"capture map extent "+where);for(const auto&[name,b]:expected)compare_bytes(actual.at(name),b,where+":"+name);}
void record_comparison(std::ofstream&out,int layer,unsigned iteration,unsigned pos,unsigned control,const std::string&boundary,const std::string&name,const std::vector<uint8_t>&b,const char*scope){std::ostringstream meta;meta<<"{\"m\":"<<current_m<<",\"token_row\":"<<current_row<<",\"layer\":"<<layer<<",\"iteration\":"<<iteration<<",\"position\":"<<pos<<",\"control_case\":"<<control<<",\"boundary\":"<<ownrt::quote(boundary)<<",\"buffer\":"<<ownrt::quote(name)<<",\"bytes\":"<<b.size()<<",\"scope\":"<<ownrt::quote(scope)<<"}";capture_manifest.push_back(meta.str());auto prefix=meta.str();prefix.pop_back();out<<prefix<<",\"sha256\":"<<ownrt::quote(hash(b))<<",\"equal\":true}\n";}
const fs::path packet=fs::path(__FILE__).parent_path();
struct Group {size_t first,last;std::string kind;std::vector<std::string> outputs;};
struct Fixture {
 Engine&e;std::string prefix;std::vector<Allocation> mutable_ids;std::map<Allocation,std::string>names;
 std::vector<Group> groups;std::map<std::string,Allocation> packed;
 Fixture(Engine&v,int layer):e(v),prefix("blk."+std::to_string(layer)+"."){}
 Allocation id(const std::string&n)const{return e.buffers[0].at(n).id;}
 void zero(Allocation a){size_t n=e.dev(0).arena.row(a).bytes;std::vector<uint8_t>b(std::min(n,size_t(4*1024*1024)),0);for(size_t off=0;off<n;off+=b.size())e.upload(0,a,off,b.data(),std::min(b.size(),n-off));}
 Allocation alloc(std::string n,size_t bytes,bool weight=false){auto a=e.allocate(0,n,bytes,weight?Category::weights:Category::scratch,weight?Lifetime::process:Lifetime::transaction);if(!weight){mutable_ids.push_back(a);names[a]=n;zero(a);}return a;}
 void setup(){
  e.owned_bytes={0};e.buffers.resize(1);e.weights.resize(1);e.selected.resize(1);e.loaded_layer={-1};e.fp32_sources={0};e.fp32_extents={0};e.submission_card=0;e.context_extent=4096;
  e.slab={e.allocate(0,"bounded-copy",4*1024*1024,Category::pinned_slab,Lifetime::transfer,Memory::pinned)};
  e.controls={alloc("control",12)};e.scores={alloc("scores",24*(e.p.g.budget+3)*4)};e.probabilities={alloc("probabilities",24*(e.p.g.budget+3)*4)};
  e.workspace={alloc("gemv-workspace",8*1024*1024)};e.scratch={alloc("operator-scratch",8*1024*1024)};
  e.mixture_out={alloc("mixture",2560*2)};e.compact_routes={alloc("compact-routes",10*sizeof(iq3::Route))};e.fp32_inputs={alloc("fp32-input",174080*4)};
  e.one={alloc("one",4,true)};float one=1;e.upload(0,e.one[0],0,&one,4);
  e.ropes={alloc("rope",rope_constants::bytes,true)};std::ifstream rope(packet/"../packet45-merged3/rope.bf16",std::ios::binary);std::vector<uint8_t>rb((std::istreambuf_iterator<char>(rope)),{});require(rb.size()==rope_constants::bytes&&hash(rb)==rope_constants::sha256,"P45 rope identity");e.upload(0,e.ropes[0],0,rb.data(),rb.size());
  for(const auto& b:e.p.buffers){size_t n=count(b.shape);e.buffers[0][b.name]={alloc(b.name,n*flash::scalar_bytes(b.type)),n,b.type};}
  for(const auto& l:e.p.launches)for(const auto& name:l.weights){if(e.weights[0].contains(name))continue;const auto&t=e.w.directory.at(name);auto type=flash::grid_type(t.grid);auto variant=e.weight_variant(name);bool expanded=arithmetic::is_expanded(variant);size_t bytes=expanded?size_t(t.shape[0])*arithmetic::row_bytes(type,t.shape[1],variant):t.bytes;auto a=alloc("weight:"+name,bytes,true);e.weights[0][name]=a;
   if(expanded){auto fmt=iq3::layout(type);size_t raw_stride=t.shape[1]/fmt.elements*fmt.bytes,expanded_stride=arithmetic::row_bytes(type,t.shape[1],variant),chunk=std::max(size_t(1),size_t(4*1024*1024)/std::max(raw_stride,expanded_stride));for(size_t r=0;r<size_t(t.shape[0]);r+=chunk){size_t rows=std::min(chunk,size_t(t.shape[0])-r);auto raw=fixture46::generated(t,r*raw_stride,rows*raw_stride);auto data=iq3::expanded::expand(type,raw.data(),raw.size(),t.shape[1]);e.upload(0,a,r*expanded_stride,data.data(),data.size());}}
   else for(size_t off=0;off<bytes;off+=4*1024*1024){auto data=fixture46::generated(t,off,std::min(bytes-off,size_t(4*1024*1024)));e.upload(0,a,off,data.data(),data.size());}
  }
  e.prepare_plan();
  for(size_t i=0;i<e.p.launches.size();++i){const auto&l=e.p.launches[i];auto cls=packet26::Dispatch::class_name(l.label);
   Group g{i,i+1,"baseline",l.outputs};
   if(cls=="expsgate"||cls=="expsdown") {
    g.kind="p48";
    for(const auto&name:l.weights){if(packed.contains(name))continue;const auto&t=e.w.directory.at(name);auto type=flash::grid_type(t.grid);unsigned K=t.shape.back();
     require(type==Type::IQ2_S||type==Type::IQ4_NL||type==Type::Q6_K,"registered primary format");auto fmt=iq3::layout(type);size_t raw_stride=K/fmt.elements*fmt.bytes,new_stride=p48::layout(type,K).row_bytes;
     size_t total_rows=t.bytes/raw_stride;auto dest=alloc("p48-weight:"+name,total_rows*new_stride,true);packed[name]=dest;
     size_t chunk=std::max(size_t(1),size_t(4*1024*1024)/std::max(raw_stride,new_stride));
     for(size_t row=0;row<total_rows;row+=chunk){size_t n=std::min(chunk,total_rows-row);auto raw=fixture46::generated(t,row*raw_stride,n*raw_stride);
      if(type==Type::Q6_K)raw=iq3::expanded::expand(type,raw.data(),raw.size(),K);
      std::vector<uint8_t>data(n*new_stride);size_t old_stride=p48::source_row_bytes(type,K);
      for(size_t r=0;r<n;++r)p48::repack_row(type,K,raw.data()+r*old_stride,data.data()+r*new_stride);
      e.upload(0,dest,row*new_stride,data.data(),data.size());
     }
    }
   }
   groups.push_back(g);
  }
 }
 using Snapshot=std::vector<std::vector<uint8_t>>;
 Snapshot snapshot(){Snapshot s;for(auto a:mutable_ids)s.push_back(e.readback(0,a,e.dev(0).arena.row(a).bytes));return s;}
 void restore(const Snapshot&s){require(s.size()==mutable_ids.size(),"snapshot extent");for(size_t i=0;i<s.size();++i)e.upload(0,mutable_ids[i],0,s[i].data(),s[i].size());e.fp32_sources[0]=0;}
 // Every named buffer is compared, including dead/fused intermediates. Internal
 // workspaces are checked at the changed norm boundaries; they are not model state.
 std::map<std::string,std::vector<uint8_t>> logical(){std::map<std::string,std::vector<uint8_t>>out;for(const auto&[n,b]:e.buffers[0])out[n]=e.readback(0,b.id,b.n*flash::scalar_bytes(b.type));out["mixture"]=e.readback(0,e.mixture_out[0],5120);out["scores"]=e.readback(0,e.scores[0],24*(e.p.g.budget+3)*4);out["probabilities"]=e.readback(0,e.probabilities[0],24*(e.p.g.budget+3)*4);return out;}
 void input(unsigned seed,unsigned pos,unsigned control_case=0){for(auto a:mutable_ids)zero(a);for(const auto&[n,b]:e.buffers[0])if(b.type==Scalar::bf16){std::vector<uint16_t>v(b.n);for(size_t k=0;k<v.size();++k)v[k]=iq3::bf16_bits(float(int(fixture46::mix(seed*104729ull+k+fixture46::seed_for(n))%257)-128)/1024.f);e.upload(0,b.id,0,v.data(),v.size()*2);}uint32_t active=control_case==1?0:1,error=control_case==2?1:0;e.upload(0,id("position"),0,&pos,4);e.upload(0,id("active"),0,&active,4);e.upload(0,id("error"),0,&error,4);e.fp32_sources[0]=0;}
 template<Type T,unsigned K, bool New=false>void issue(const flash::Launch&l){
  const auto&ms=e.matrices.at(&l);auto m=ms.at(0),peer=ms.size()==2?ms.at(1):m;
  std::conditional_t<New,p51::GateKernel,p48b::Kernel<T,K>> op;op.rows=m.rows;op.count=m.count;op.experts=m.experts;
  require(m.columns==K,"candidate columns");
  std::array<Allocation,10>a{packed.at(l.weights[0]),packed.at(l.weights[ms.size()==2?1:0]),m.x,m.y,peer.y,m.routes?m.routes:m.x,m.status?m.status:m.y,peer.status?peer.status:peer.y,id("error"),id("active")};
  auto ev=e.dev(0).compute(op,a,{});e.finish(0,ev);
 }
 template<Type T,unsigned K,unsigned Split,p39::Kind E>void dense_issue(const flash::Launch&l){
  const auto&m=e.matrices.at(&l).at(0);require(m.type==T&&m.columns==K&&m.count==1&&m.experts==1,"dense production shape");
  require(e.variant(l)==unsigned(T==Type::F32?(Split==4?4:0):(Split==4?7:6)),"dense exact arithmetic identity");
  auto out=E==p39::Kind::silu_div4?id(l.label.substr(0,l.label.size()-3)+"act"):m.y;
  auto streams=E==p39::Kind::attention_combine?id("streams"):m.y;
  auto inject=E==p39::Kind::attention_combine?id(prefix+"hc.a.inject"):m.x;
  std::array<Allocation,19> ids{m.w,m.w,m.x,m.y,m.y,m.x,m.y,m.y,m.workspace,m.x,out,streams,inject,m.x,m.x,m.x,id("error"),id("active"),id("position")};
  p51::DenseKernel<T,K,Split,E>op;op.shape.rows=m.rows;op.shape.count=1;op.shape.experts=1;op.shape.capacity=e.p.g.context;op.shape.rb=arithmetic::row_bytes(T,K,e.variant(l));
  auto first=e.dev(0).compute(op,ids,{});integrated::Launch result{first,first,1};
#ifndef OWN_RT_HOST_ONLY
  if constexpr(E==p39::Kind::attention_combine){p51::DenseKernel<T,K,Split,E,1>finish;finish.shape=op.shape;std::array after{first};result.last=e.dev(0).compute(finish,ids,after);result.passes=2;}
#endif
  e.finish(0,result,true);
 }
 void execute(const Group&g,bool candidate){const auto&l=e.p.launches[g.first];e.guard();e.set_class(l.label);
  auto cls=packet26::Dispatch::class_name(l.label);
  if(candidate&&cls=="route") {const auto&b=e.prepared.at(&l);e.finish(0,p51::route_submit(e.dev(0),b.spec,b.bindings),false);return;}
  if(candidate){
   if(cls=="hc.a.low"||cls=="hc.f.low"){dense_issue<Type::Q8_0,10240,4,p39::Kind::silu_div4>(l);return;}
   if(cls=="hc.a.gate"||cls=="hc.f.gate"){dense_issue<Type::Q8_0,320,1,p39::Kind::expert_checks>(l);return;}
   if(cls=="gdn.qkv"){dense_issue<Type::Q6_K,2560,1,p39::Kind::expert_checks>(l);return;}
   if(cls=="attention"){dense_issue<Type::Q6_K,6144,4,p39::Kind::attention_combine>(l);return;}
  }
  if(g.kind=="baseline"){e.execute_site(l);return;}
  auto type=e.matrices.at(&l).at(0).type;
  if(type==Type::IQ2_S){if(candidate)issue<Type::IQ2_S,2560,true>(l);else issue<Type::IQ2_S,2560>(l);}
  else if(type==Type::IQ4_NL)issue<Type::IQ4_NL,640>(l);
  else throw std::runtime_error("unregistered control type");
 }
 std::map<std::string,std::vector<uint8_t>> boundary(const Group&g){std::map<std::string,std::vector<uint8_t>>r;for(const auto&n:g.outputs){auto b=e.buffers[0].at(n);r[n]=e.readback(0,b.id,b.n*flash::scalar_bytes(b.type));}if(g.kind=="norm")r["norm.fp32.partials"]=e.readback(0,e.scratch[0],4*80*4);if(g.kind=="qsa_projections")r["qsa.ik.fp32.partials"]=e.readback(0,e.workspace[0],128*8*4);if(g.kind=="moe_tail")r["mixture"]=e.readback(0,e.mixture_out[0],5120);return r;}
 std::string routes(){auto v=e.readback(0,id(prefix+"ids"),40);std::array<uint32_t,10>ids{};std::memcpy(ids.data(),v.data(),40);std::sort(ids.begin(),ids.end());require(ids.back()<512&&std::adjacent_find(ids.begin(),ids.end())==ids.end(),"valid distinct route set");std::memcpy(v.data(),ids.data(),40);return hash(v);}
};
static flash::Plan layer_plan(Weights&w,Options&a,int layer){std::ifstream f(packet/"../packet34-replay-bench/directory.tsv");require(bool(f),"fixture metadata");w.directory=flash::read_directory(f);auto p=::plan(w,a);std::string prefix="blk."+std::to_string(layer)+".";std::erase_if(p.launches,[&](const auto&l){return !l.label.starts_with(prefix);});for(auto&l:p.launches){l.card=0;l.source_card=-1;}std::set<std::string>used{"error","active","position","streams"};for(const auto&l:p.launches){used.insert(l.inputs.begin(),l.inputs.end());used.insert(l.outputs.begin(),l.outputs.end());}std::erase_if(p.buffers,[&](const auto&b){return !used.contains(b.name);});for(auto&b:p.buffers)b.card=0;return p;}
struct EventRow {std::string cls;uint64_t start,end,id;};
struct Measure {uint64_t launches=0,gpu_ns=0;std::map<std::string,uint64_t>classes;std::vector<EventRow>events;};
static Measure measure(Fixture&f,bool candidate){auto&e=f.e;auto first=e.submitted;for(const auto&g:f.groups)f.execute(g,candidate);if(e.tail)e.wait(0,e.tail);Measure m;m.launches=e.submitted-first;
#ifndef OWN_RT_HOST_ONLY
 for(const auto&p:e.pending)for(auto i=p.launch.first;i<=p.launch.last;++i){auto t=e.dev(0).timing(i);require(t.start_ns&&t.end_ns>t.start_ns&&t.end_ns-t.start_ns<=4000000000ull,"valid bounded GPU-event timing");auto dt=t.end_ns-t.start_ns;m.gpu_ns+=dt;m.classes[e.class_names.at(p.cls)]+=dt;m.events.push_back({e.class_names.at(p.cls),t.start_ns,t.end_ns,i});}
 uint64_t events=0;for(const auto&p:e.pending)events+=p.launch.passes;require(events==m.launches,"complete per-class event coverage");
#endif
 e.pending.clear();e.tail=0;e.dev(0).retire_completed_events();return m;}
static void timing_row(std::ofstream&out,int layer,unsigned iteration,bool candidate,Measure m){out<<"{\"m\":"<<current_m<<",\"token_row\":"<<current_row<<",\"layer\":"<<layer<<",\"mode\":\""<<(candidate?"specialized":"current")<<"\",\"iteration\":"<<iteration<<",\"warmup\":"<<(iteration<10?"true":"false")<<",\"position\":4095,\"occupied_context\":4096,\"submissions\":"<<m.launches<<",\"gpu_ns\":"<<m.gpu_ns<<",\"classes_ns\":{";bool first=true;for(const auto&[n,ns]:m.classes){out<<(first?"":",")<<ownrt::quote(n)<<":"<<ns;first=false;}out<<"},\"events\":[";for(size_t j=0;j<m.events.size();++j){auto v=m.events[j];out<<(j?",":"")<<"{\"id\":"<<v.id<<",\"class\":"<<ownrt::quote(v.cls)<<",\"start_ns\":"<<v.start<<",\"end_ns\":"<<v.end<<"}";}out<<"]}\n";out.flush();require(bool(out),"timing write");}
}
int main(int argc,char**argv){using namespace p51bench;std::string mode;fs::path output;bool cpu=false,authorized=false,device_executed=false;size_t owners_started=0;int card=-1;std::vector<std::string>teardown;std::string error;std::unique_ptr<Engine>e;size_t checks=0,timing_pair_checks=0;std::vector<uint8_t>digest_bytes;std::map<int,std::set<std::string>>routes;std::map<int,std::array<uint64_t,2>>launch_counts;try{
 for(int i=1;i<argc;++i){std::string k=argv[i];auto v=[&]{require(i+1<argc,"missing argument");return std::string(argv[++i]);};if(k=="--mode")mode=v();else if(k=="--output")output=v();else if(k=="--card")card=std::stoi(v());else if(k=="--authorized-device-window")authorized=true;else if(k=="--cpu-test")cpu=true;else throw std::runtime_error("unsupported argument: "+k);}
 require(!output.empty()&&(mode=="exact"||mode=="timing"),"--mode exact|timing --output required");fs::create_directories(output);require(getenv("OMP_NUM_THREADS")&&std::string(getenv("OMP_NUM_THREADS"))=="2","OMP_NUM_THREADS=2 required");
#ifdef OWN_RT_HOST_ONLY
 require(cpu&&!authorized&&card==-1&&mode=="exact","CPU exact mock only");
#else
 require(!cpu&&authorized&&card==0,"explicit card 0 device window only");
#endif
 std::signal(SIGTERM,stop);std::signal(SIGINT,stop);packet26::dispatch.load((packet/"dispatch-baseline.json").string());std::ofstream comparisons(output/"comparisons.jsonl"),timings(output/"iterations.jsonl");
 for(int layer:{4,3}){Options a;a.mini=true;Weights w(a);a.mini=false;a.cards=2;a.context=4096;a.memory="resident";a.legacy=true;a.timing="class";a.seconds=1800;a.output=output;auto p=layer_plan(w,a,layer);e=std::make_unique<Engine>(w,a,p);
#ifdef OWN_RT_HOST_ONLY
 e->devices.push_back(std::make_unique<ownrt::Device>(std::make_unique<Host>()));
#else
 device_executed=true;{std::vector<sycl::device> cards;for(const auto&platform:sycl::platform::get_platforms())if(platform.get_backend()==sycl::backend::ext_oneapi_level_zero)for(const auto&d:platform.get_devices(sycl::info::device_type::gpu))cards.push_back(d);require(!cards.empty()&&cards[0].get_info<sycl::ext::intel::info::device::pci_address>()=="0000:23:00.0","physical card0 PCI mismatch");}e->devices.push_back(std::make_unique<ownrt::Device>(ownrt::make_sycl_device(0,true)));
#endif
 ++owners_started;Fixture f(*e,layer);f.setup();unsigned total=mode=="timing"?210:6;
 for(unsigned m:{1u,2u}) for(unsigned iteration=0;iteration<total;++iteration)for(current_row=0;current_row<m;++current_row){current_m=m;unsigned pos=mode=="timing"?4095:std::array<unsigned,6>{0,127,4095,4095,4095,4096}[iteration],control=mode=="timing"?0:iteration==3?1:iteration==4?2:0;f.input(0x4600+iteration+current_row*7919,pos,control);auto start=f.snapshot();
  if(mode=="exact"){
   std::vector<std::map<std::string,std::vector<uint8_t>>>oracle;
   for(const auto&g:f.groups){f.execute(g,false);oracle.push_back(f.boundary(g));}
   auto expected=f.logical();auto complete_expected=f.snapshot();
   if(!control&&pos<4096)routes[layer].insert(f.routes());f.restore(start);
   for(size_t j=0;j<f.groups.size();++j){const auto&g=f.groups[j];f.execute(g,true);auto actual=f.boundary(g);auto site=e->p.launches[g.first].label;
    compare_maps(actual,oracle[j],"layer="+std::to_string(layer)+" group="+g.kind+" site="+site);
    for(const auto&[name,b]:actual){record_comparison(comparisons,layer,iteration,pos,control,site,name,b,"producer");++checks;}
   }
   auto actual=f.logical();compare_maps(actual,expected,"complete logical state");
   auto complete_actual=f.snapshot();require(complete_actual.size()==complete_expected.size(),"full snapshot count");
   for(size_t n=0;n<complete_actual.size();++n){const auto&b=complete_actual[n];auto name=f.names.at(f.mutable_ids[n]);compare_bytes(b,complete_expected[n],"full mutable "+name);record_comparison(comparisons,layer,iteration,pos,control,"full-mutable",name,b,"all-mutable-allocation");++checks;}
   for(const auto&[name,b]:actual){record_comparison(comparisons,layer,iteration,pos,control,"complete-state",name,b,"logical-state");++checks;}
   comparisons.flush();
  }
  else { // Alternate AB/BA; restored inputs/state never enter the timing interval.
   std::optional<Fixture::Snapshot> pair_oracle;
   for(bool candidate:iteration%2?std::array{true,false}:std::array{false,true}){f.restore(start);auto m=measure(f,candidate);launch_counts[layer][candidate?1:0]=m.launches;require(m.launches==unsigned(layer==4?35:41),"native matched physical launch count");timing_row(timings,layer,iteration,candidate,m);require(e->integer(0,"error")==0,"timing arm sticky error");auto actual=f.snapshot();if(pair_oracle){require(actual.size()==pair_oracle->size(),"timing snapshot count");for(size_t j=0;j<actual.size();++j)compare_bytes(actual[j],pair_oracle->at(j),"timing pair "+f.names.at(f.mutable_ids[j]));++timing_pair_checks;}else pair_oracle=std::move(actual);}
  }
 }
 if(mode=="exact")require(routes[layer].size()>=2,"changing expert sets required");auto r=e->shutdown();teardown.insert(teardown.end(),r.begin(),r.end());e.reset();
 }
 }catch(const std::exception&ex){error=ex.what();if(!output.empty())save(output/"failure.txt",error+"\n");if(e){try{auto r=e->shutdown();teardown.insert(teardown.end(),r.begin(),r.end());}catch(const std::exception&close){error+="; "+std::string(close.what());if(!output.empty())save(output/"unsafe-teardown.txt",error);ownrt::hold_for_supervisor();}e.reset();}}
 if(!output.empty()){std::ostringstream manifest;manifest<<"[";for(size_t i=0;i<capture_manifest.size();++i)manifest<<(i?",\n":"")<<capture_manifest[i];manifest<<"]\n";save(output/"exact-capture-manifest.json",manifest.str());std::ifstream in(output/"comparisons.jsonl",std::ios::binary);digest_bytes.assign(std::istreambuf_iterator<char>(in),{});}
 bool safe=teardown.size()==owners_started;
 std::ostringstream result;
 result<<"{\"schema\":\"ownrt.packet51.layer.v1\",\"passed\":"<<(error.empty()?"true":"false")
 <<",\"cpu_mock\":"<<(cpu?"true":"false")<<",\"device_executed\":"<<(device_executed?"true":"false")
 <<",\"safe_to_exit\":"<<(safe?"true":"false")<<",\"mode\":"<<ownrt::quote(mode)<<",\"card\":"<<card
 <<",\"context_capacity\":4096,\"occupied_context\":"<<(mode=="timing"?4096:0)
 <<",\"arithmetic\":\"iq3-p17-detmath-v2\",\"checks\":"<<checks
 <<",\"timing_pair_checks\":"<<timing_pair_checks<<",\"exact_output_identity\":"<<ownrt::quote(hash(digest_bytes))
 <<",\"error\":"<<ownrt::quote(error)<<",\"route_set_counts\":{";
 bool first=true;for(auto&[layer,r]:routes){result<<(first?"":",")<<ownrt::quote(std::to_string(layer))<<":"<<r.size();first=false;}
 result<<"},\"launch_counts\":{";first=true;for(auto&[layer,c]:launch_counts){result<<(first?"":",")<<ownrt::quote(std::to_string(layer))<<":{\"current\":"<<c[0]<<",\"specialized\":"<<c[1]<<"}";first=false;}
 result<<"},\"teardown\":[";for(size_t i=0;i<teardown.size();++i)result<<(i?",":"")<<teardown[i];result<<"]}";
 if(!output.empty())save(output/"receipt.json",result.str());std::cout<<result.str()<<"\n";return error.empty()?0:1;}
