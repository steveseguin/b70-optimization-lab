#define main packet107_unused_entry
#include "main.cpp"
#undef main
// Current production operators only; packet107 specialised arms remain closed.
#include "fixture_bytes.hpp"
#include "recurrence_cases.hpp"
#include <numeric>
namespace p107bench {
using iq3::Type;
std::vector<std::string> capture_manifest;
void compare_bytes(const std::vector<uint8_t>&actual,const std::vector<uint8_t>&expected,const std::string&name){require(actual.size()==expected.size(),"byte extent mismatch "+name);for(size_t k=0;k<actual.size();++k)if(actual[k]!=expected[k])throw std::runtime_error("raw byte mismatch "+name+" offset="+std::to_string(k)+" expected="+std::to_string(expected[k])+" actual="+std::to_string(actual[k]));}
void compare_maps(const std::map<std::string,std::vector<uint8_t>>&actual,const std::map<std::string,std::vector<uint8_t>>&expected,const std::string&where){require(actual.size()==expected.size(),"capture map extent "+where);for(const auto&[name,b]:expected)compare_bytes(actual.at(name),b,where+":"+name);}
void record_comparison(std::ofstream&out,int layer,unsigned iteration,unsigned pos,unsigned control,const std::string&boundary,const std::string&name,const std::vector<uint8_t>&b,const char*scope){std::ostringstream meta;meta<<"{\"layer\":"<<layer<<",\"iteration\":"<<iteration<<",\"position\":"<<pos<<",\"control_case\":"<<control<<",\"boundary\":"<<ownrt::quote(boundary)<<",\"buffer\":"<<ownrt::quote(name)<<",\"bytes\":"<<b.size()<<",\"scope\":"<<ownrt::quote(scope)<<"}";capture_manifest.push_back(meta.str());auto prefix=meta.str();prefix.pop_back();out<<prefix<<",\"sha256\":"<<ownrt::quote(hash(b))<<",\"equal\":true}\n";}
const fs::path packet=fs::path(__FILE__).parent_path();
struct Group {size_t first,last;std::string kind;std::vector<std::string> outputs;};
struct Fixture {
 Engine&e;std::string prefix;std::vector<Allocation> mutable_ids;std::map<Allocation,std::string>names;
 std::vector<Group> groups; Allocation prep=0;
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
  e.ropes={alloc("rope",rope_constants::bytes,true)};std::ifstream rope(packet/"rope.bf16",std::ios::binary);std::vector<uint8_t>rb((std::istreambuf_iterator<char>(rope)),{});require(rb.size()==rope_constants::bytes&&hash(rb)==rope_constants::sha256,"P45 rope identity");e.upload(0,e.ropes[0],0,rb.data(),rb.size());
  for(const auto& b:e.p.buffers){size_t n=count(b.shape);e.buffers[0][b.name]={alloc(b.name,n*flash::scalar_bytes(b.type)),n,b.type};}
  for(const auto& l:e.p.launches)for(const auto& name:l.weights){if(e.weights[0].contains(name))continue;const auto&t=e.w.directory.at(name);auto type=flash::grid_type(t.grid);auto variant=e.weight_variant(name);
   bool planes=p49b_weight(e.w,e.a,e.p,name),cached=e.p90_expert_weight(name),expanded=!planes&&arithmetic::is_expanded(variant);
   const unsigned k=t.shape.back();auto fmt=iq3::layout(type);size_t raw_stride=k/fmt.elements*fmt.bytes;
   size_t stride=planes?(cached?p90::expert_stride(k):p49bgemv::layout(type,k).row_bytes):expanded?arithmetic::row_bytes(type,k,variant):raw_stride;
   size_t rows=t.bytes/raw_stride,bytes=rows*stride;auto a=alloc("weight:"+name,bytes,true);e.weights[0][name]=a;
   const size_t chunk=std::max(size_t(1),size_t(4*1024*1024)/std::max(stride,raw_stride));
   for(size_t r=0;r<rows;r+=chunk){size_t nr=std::min(chunk,rows-r);auto raw=fixture46::generated(t,r*raw_stride,nr*raw_stride);std::vector<uint8_t> data;
    if(planes){data.resize(nr*stride);for(size_t j=0;j<nr;++j){if(cached)p90::expert_repack(k,raw.data()+j*raw_stride,data.data()+j*stride);else p49bgemv::repack_row(type,k,raw.data()+j*raw_stride,data.data()+j*stride);}}
    else data=expanded?iq3::expanded::expand(type,raw.data(),raw.size(),k):std::move(raw);
    e.upload(0,a,r*stride,data.data(),data.size());
   }
  }
  e.prepare_plan();
  for(size_t i=0;i<e.p.launches.size();++i){const auto&l=e.p.launches[i];Group g{i,i+1,"baseline",l.outputs};if(l.op=="gdn")g.kind="gdn";if(l.op=="qsa_attention")g.kind="qsa";groups.push_back(g);}

 }
 using Snapshot=std::vector<std::vector<uint8_t>>;
 Snapshot snapshot(){Snapshot s;for(auto a:mutable_ids)s.push_back(e.readback(0,a,e.dev(0).arena.row(a).bytes));return s;}
 void restore(const Snapshot&s){require(s.size()==mutable_ids.size(),"snapshot extent");for(size_t i=0;i<s.size();++i)e.upload(0,mutable_ids[i],0,s[i].data(),s[i].size());e.fp32_sources[0]=0;}
 // Every named buffer is compared, including dead/fused intermediates. Internal
 // workspaces are checked at the changed norm boundaries; they are not model state.
 std::map<std::string,std::vector<uint8_t>> logical(){std::map<std::string,std::vector<uint8_t>>out;for(const auto&[n,b]:e.buffers[0])out[n]=e.readback(0,b.id,b.n*flash::scalar_bytes(b.type));out["mixture"]=e.readback(0,e.mixture_out[0],5120);out["scores"]=e.readback(0,e.scores[0],24*(e.p.g.budget+3)*4);out["probabilities"]=e.readback(0,e.probabilities[0],24*(e.p.g.budget+3)*4);return out;}
 void input(unsigned seed,unsigned pos,unsigned control_case=0){for(auto a:mutable_ids)zero(a);for(const auto&[n,b]:e.buffers[0])if(b.type==Scalar::bf16){std::vector<uint16_t>v(b.n);for(size_t k=0;k<v.size();++k)v[k]=iq3::bf16_bits(float(int(fixture46::mix(seed*104729ull+k+fixture46::seed_for(n))%257)-128)/1024.f);e.upload(0,b.id,0,v.data(),v.size()*2);}uint32_t active=control_case==1?0:1,error=control_case==2?1:0;e.upload(0,id("position"),0,&pos,4);e.upload(0,id("active"),0,&active,4);e.upload(0,id("error"),0,&error,4);e.fp32_sources[0]=0;}
 void execute(const Group&g,bool candidate){const auto&l=e.p.launches[g.first];e.guard();e.set_class(l.label);
  if(!candidate||g.kind!="gdn"){e.execute_site(l);return;}
  const auto&bound=e.prepared.at(&l);auto b=p49drec::recurrence_bindings(bound.spec,bound.bindings);
  require(b.shape.flags==14&&b.shape.tokens==1&&b.shape.capacity==4096,"fixed GDN identity");
  p113rec::Kernel op;op.shape=b.shape;auto event=e.dev(0).compute(op,b.ids,{});e.finish(0,event);
 }

 std::map<std::string,std::vector<uint8_t>> boundary(const Group&g){std::map<std::string,std::vector<uint8_t>>r;for(const auto&n:g.outputs){auto b=e.buffers[0].at(n);r[n]=e.readback(0,b.id,b.n*flash::scalar_bytes(b.type));}return r;}
 std::string routes(){auto v=e.readback(0,id(prefix+"ids"),40);std::array<uint32_t,10>ids{};std::memcpy(ids.data(),v.data(),40);std::sort(ids.begin(),ids.end());require(ids.back()<512&&std::adjacent_find(ids.begin(),ids.end())==ids.end(),"valid distinct route set");std::memcpy(v.data(),ids.data(),40);return hash(v);}
};
static unsigned recurrence_cases(Engine&e,const fs::path&out){
 std::array<Allocation,19> ids;ids.fill(e.controls[0]);
 const std::array<size_t,19> sizes{4*10240*2,4*48*2,4*48*2,48*4,48*4,786432*2,4*6144*2,786432*2,0,0,0,0,0,0,0,4,0,4,4};
 for(unsigned i=0;i<19;++i)if(sizes[i])ids[i]=e.allocate(0,"p113-leaf-"+std::to_string(i),sizes[i],Category::scratch,Lifetime::transaction);
 std::ofstream transcript(out/"recurrence-cases.jsonl");
 auto run=[&](bool candidate,ng::Shape s,p113test::Data&d,bool alias){
  e.guard();auto a=d.args(false);auto bound=ids;auto n=sizes;n[0]=s.tokens*10240*2;n[1]=n[2]=s.tokens*48*2;n[6]=s.tokens*6144*2;
  for(unsigned i=0;i<19;++i)if(n[i])e.upload(0,ids[i],0,a.p[i],n[i]);
  if(alias)bound[5]=bound[7];e.set_class("p113.selftest");
  if(candidate){p113rec::Kernel op;op.shape=s;e.finish(0,e.dev(0).compute(op,bound,{}));}
  else{p82brec::Kernel<true> op;op.shape=s;e.finish(0,e.dev(0).compute(op,bound,{}));}
  for(unsigned i=0;i<19;++i)if(n[i]){auto bytes=e.readback(0,ids[i],n[i]);
   if(i==6||i==7||i==15)std::memcpy(a.p[i],bytes.data(),bytes.size());
   else require(std::memcmp(a.p[i],bytes.data(),bytes.size())==0,"recurrence mutated input "+std::to_string(i));}
  e.drain();e.pending.clear();e.tail=0;e.dev(0).retire_completed_events();
 };
 auto compare=[&](const p113test::Data&a,const p113test::Data&b,const std::string&desc,unsigned tokens){
  auto x=a.bytes(),y=b.bytes();compare_bytes(y,x,"recurrence "+desc);
  transcript<<"{\"case\":"<<ownrt::quote(desc)<<",\"tokens\":"<<tokens<<",\"bytes\":"<<x.size()<<",\"sha256\":"<<ownrt::quote(hash(x))<<",\"equal\":true}\n";
 };
 auto count=p113test::cases(run,compare);require(count==768&&bool(transcript),"recurrence case coverage/write");return count;
}
static flash::Plan layer_plan(Weights&w,Options&a,int layer){std::ifstream f(packet/"../packet34-replay-bench/directory.tsv");require(bool(f),"fixture metadata");w.directory=flash::read_directory(f);auto p=::plan(w,a);std::string prefix="blk."+std::to_string(layer)+".";std::erase_if(p.launches,[&](const auto&l){return !l.label.starts_with(prefix);});for(auto&l:p.launches){l.card=0;l.source_card=-1;}std::set<std::string>used{"error","active","position","streams"};for(const auto&l:p.launches){used.insert(l.inputs.begin(),l.inputs.end());used.insert(l.outputs.begin(),l.outputs.end());}std::erase_if(p.buffers,[&](const auto&b){return !used.contains(b.name);});for(auto&b:p.buffers)b.card=0;return p;}
struct EventRow {std::string cls;uint64_t start,end,id;};
struct Measure {uint64_t launches=0,gpu_ns=0;std::map<std::string,uint64_t>classes;std::vector<EventRow>events;};
static Measure measure(Fixture&f,bool candidate){auto&e=f.e;auto first=e.submitted;for(const auto&g:f.groups)f.execute(g,candidate);if(e.tail)e.wait(0,e.tail);Measure m;m.launches=e.submitted-first;
#ifndef OWN_RT_HOST_ONLY
 for(const auto&p:e.pending)for(auto i=p.launch.first;i<=p.launch.last;++i){auto t=e.dev(0).timing(i);require(t.start_ns&&t.end_ns>t.start_ns&&t.end_ns-t.start_ns<=4000000000ull,"valid bounded GPU-event timing");auto dt=t.end_ns-t.start_ns;m.gpu_ns+=dt;m.classes[e.class_names.at(p.cls)]+=dt;m.events.push_back({e.class_names.at(p.cls),t.start_ns,t.end_ns,i});}
 uint64_t events=0;for(const auto&p:e.pending)events+=p.launch.passes;require(events==m.launches,"complete per-class event coverage");
#endif
 e.pending.clear();e.tail=0;e.dev(0).retire_completed_events();return m;}
static void timing_row(std::ofstream&out,int layer,unsigned iteration,unsigned pos,bool candidate,Measure m){out<<"{\"layer\":"<<layer<<",\"mode\":\""<<(candidate?"specialized":"current")<<"\",\"iteration\":"<<iteration<<",\"warmup\":"<<(iteration<10?"true":"false")<<",\"position\":"<<pos<<",\"occupied_context\":"<<pos+1<<",\"submissions\":"<<m.launches<<",\"gpu_ns\":"<<m.gpu_ns<<",\"classes_ns\":{";bool first=true;for(const auto&[n,ns]:m.classes){out<<(first?"":",")<<ownrt::quote(n)<<":"<<ns;first=false;}out<<"},\"events\":[";for(size_t j=0;j<m.events.size();++j){auto v=m.events[j];out<<(j?",":"")<<"{\"id\":"<<v.id<<",\"class\":"<<ownrt::quote(v.cls)<<",\"start_ns\":"<<v.start<<",\"end_ns\":"<<v.end<<"}";}out<<"]}\n";out.flush();require(bool(out),"timing write");}
}
int main(int argc,char**argv){using namespace p107bench;std::string mode,layer_choice="both";fs::path output;bool cpu=false,authorized=false,device_executed=false;size_t owners_started=0;int card=-1;std::vector<std::string>teardown;std::string error;std::unique_ptr<Engine>e;size_t checks=0,timing_pair_checks=0,recurrence_checks=0;std::vector<uint8_t>digest_bytes;std::map<int,std::set<std::string>>routes;std::map<int,std::array<uint64_t,2>>launch_counts;try{
 for(int i=1;i<argc;++i){std::string k=argv[i];auto v=[&]{require(i+1<argc,"missing argument");return std::string(argv[++i]);};if(k=="--mode")mode=v();else if(k=="--layer")layer_choice=v();else if(k=="--output")output=v();else if(k=="--card")card=std::stoi(v());else if(k=="--authorized-device-window")authorized=true;else if(k=="--cpu-test")cpu=true;else throw std::runtime_error("unsupported argument: "+k);}
 require(!output.empty()&&(mode=="exact"||mode=="timing"),"--mode exact|timing --output required");fs::create_directories(output);require(getenv("OMP_NUM_THREADS")&&std::string(getenv("OMP_NUM_THREADS"))=="2","OMP_NUM_THREADS=2 required");
#ifdef OWN_RT_HOST_ONLY
 require(cpu&&!authorized&&card==-1&&mode=="exact","CPU exact mock only");
#else
 require(!cpu&&authorized&&card==0&&layer_choice=="gdn","device admission: GDN row micro only");
#endif
 std::signal(SIGTERM,stop);std::signal(SIGINT,stop);packet26::dispatch.load((packet/"dispatch-speed6.json").string());std::ofstream comparisons(output/"comparisons.jsonl"),timings(output/"iterations.jsonl");
 const std::string requested_mode=mode;
 for(int layer:{4}){if(layer_choice=="qsa"&&layer!=3)continue;if(layer_choice=="gdn"&&layer!=4)continue;require(layer_choice=="both"||layer_choice=="qsa"||layer_choice=="gdn","layer choice");Options a;a.mini=true;Weights w(a);a.mini=false;a.cards=2;a.context=4096;a.memory="resident";a.legacy=false;a.rank=0;a.draft_rank=1;a.timing="class";a.seconds=3600;a.selection=(packet/"selection.json").string();a.selection_sha256="6c58206cad748a8385b41389d5b9c05ff1891340b4bd0b12ce3611b5cddca739";a.output=output;auto p=layer_plan(w,a,layer);e=std::make_unique<Engine>(w,a,p);
#ifdef OWN_RT_HOST_ONLY
 e->devices.push_back(std::make_unique<ownrt::Device>(std::make_unique<Host>()));
#else
 device_executed=true;e->devices.push_back(std::make_unique<ownrt::Device>(ownrt::make_sycl_device(0,true)));
#endif
 ++owners_started;Fixture f(*e,layer);f.setup();recurrence_checks=recurrence_cases(*e,output);unsigned total=requested_mode=="timing"?104:4;
 for(unsigned iteration=0;iteration<total;++iteration){mode=iteration<4?"exact":"timing";unsigned timing_index=(iteration-4)%50;
  unsigned pos=mode=="exact"?std::array<unsigned,4>{126,127,128,129}[iteration]:(iteration<54?127:4095),control=0;
  if(iteration==0||mode=="timing")f.input(0x10700+iteration,pos,control);
  else {e->upload(0,f.id("position"),0,&pos,4);auto stream=e->buffers[0].at("streams");std::vector<uint16_t>x(stream.n);for(size_t j=0;j<x.size();++j)x[j]=iq3::bf16_bits(float(int(fixture46::mix(j+iteration*104729)%257)-128)/1024.f);e->upload(0,stream.id,0,x.data(),x.size()*2);}
  e->context_extent=((pos+32)/32)*32;
  for(const auto&l:e->p.launches)if(l.op=="qsa_attention"||l.op=="qsa_select")e->prepared[&l]=e->prepare_site(l);
  auto start=f.snapshot();
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
   e->drain();e->pending.clear();e->tail=0;e->dev(0).retire_completed_events();
   comparisons.flush();
  }
  else { // Alternating current/candidate; snapshots and comparisons stay outside event timing.
   std::optional<Fixture::Snapshot> pair_oracle;
   for(unsigned repeat=0;repeat<2;++repeat){f.restore(start);bool candidate=(repeat+timing_index)%2;auto m=measure(f,candidate);launch_counts[layer][candidate]=m.launches;require(m.launches>0,"nonempty complete layer");timing_row(timings,layer,timing_index,pos,candidate,m);require(e->integer(0,"error")==0,"timing arm sticky error");auto actual=f.snapshot();if(pair_oracle){require(actual.size()==pair_oracle->size(),"timing snapshot count");for(size_t j=0;j<actual.size();++j)compare_bytes(actual[j],pair_oracle->at(j),"timing pair "+f.names.at(f.mutable_ids[j]));++timing_pair_checks;}else pair_oracle=std::move(actual);}
  }
 }
 require(routes[layer].size()>=2,"changing expert sets required");auto r=e->shutdown();teardown.insert(teardown.end(),r.begin(),r.end());e.reset();
 }
 }catch(const std::exception&ex){error=ex.what();if(!output.empty())save(output/"failure.txt",error+"\n");if(e){try{auto r=e->shutdown();teardown.insert(teardown.end(),r.begin(),r.end());}catch(const std::exception&close){error+="; "+std::string(close.what());if(!output.empty())save(output/"unsafe-teardown.txt",error);ownrt::hold_for_supervisor();}e.reset();}}
 if(!output.empty()){std::ostringstream manifest;manifest<<"[";for(size_t i=0;i<capture_manifest.size();++i)manifest<<(i?",\n":"")<<capture_manifest[i];manifest<<"]\n";save(output/"exact-capture-manifest.json",manifest.str());std::ifstream in(output/"comparisons.jsonl",std::ios::binary);digest_bytes.assign(std::istreambuf_iterator<char>(in),{});}
 bool safe=teardown.size()==owners_started;
 std::ostringstream result;
 result<<"{\"schema\":\"ownrt.packet113.layer.v1\",\"passed\":"<<(error.empty()?"true":"false")
 <<",\"cpu_mock\":"<<(cpu?"true":"false")<<",\"device_executed\":"<<(device_executed?"true":"false")
 <<",\"safe_to_exit\":"<<(safe?"true":"false")<<",\"mode\":"<<ownrt::quote(mode)<<",\"card\":"<<card
 <<",\"context_capacity\":4096,\"occupied_context\":"<<(mode=="timing"?4096:0)
 <<",\"arithmetic\":\"iq3-p49-split32-v1\",\"checks\":"<<checks
 <<",\"recurrence_checks\":"<<recurrence_checks<<",\"timing_pair_checks\":"<<timing_pair_checks<<",\"exact_output_identity\":"<<ownrt::quote(hash(digest_bytes))
 <<",\"error\":"<<ownrt::quote(error)<<",\"route_set_counts\":{";
 bool first=true;for(auto&[layer,r]:routes){result<<(first?"":",")<<ownrt::quote(std::to_string(layer))<<":"<<r.size();first=false;}
 result<<"},\"launch_counts\":{";first=true;for(auto&[layer,c]:launch_counts){result<<(first?"":",")<<ownrt::quote(std::to_string(layer))<<":{\"current\":"<<c[0]<<",\"specialized\":"<<c[1]<<"}";first=false;}
 result<<"},\"teardown\":[";for(size_t i=0;i<teardown.size();++i)result<<(i?",":"")<<teardown[i];result<<"]}";
 if(!output.empty())save(output/"receipt.json",result.str());std::cout<<result.str()<<"\n";return error.empty()?0:1;}
