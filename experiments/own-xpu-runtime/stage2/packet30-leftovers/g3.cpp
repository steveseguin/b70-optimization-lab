#include "route.hpp"
#include "attention.hpp"
#include "small.hpp"
#include "fusion.hpp"
#include "../packet27-round2/adapter.hpp"
#include "../packet27-round2/small_gemv.hpp"
#include "../packet27-round2/failure.hpp"
#ifdef OWN_RT_HOST_ONLY
#else
#include "sycl_operation.hpp"
#endif
#include <filesystem>
#include <fstream>
#include <iostream>
#include <csignal>
#include <set>
#include <cstring>
#include <cstdlib>
namespace p30 {integrated::Launch dense_incumbent(ownrt::Device&,const integrated::Matrix&,unsigned);}
namespace {
using namespace ownrt;using namespace integrated;
volatile std::sig_atomic_t stopped=0;
void signal_stop(int){stopped=1;}
void check(bool b,const std::string& why){if(!b)throw std::runtime_error(why);}
void stop(){check(!stopped,"cooperative stop requested");}
bool validation=false,cpu_fixtures=false,device_contacted=false;
struct Options{unsigned card=0;std::string mode="G3";std::filesystem::path output;};
Options options(int argc,char** argv){Options o;for(int i=1;i<argc;++i){std::string a=argv[i];if(a=="--validate")validation=true;else if(a=="--cpu-fixtures")cpu_fixtures=true;else if((a=="--card"||a=="--mode"||a=="--output")&&i+1<argc){std::string v=argv[++i];if(a=="--card"){size_t n;auto card=std::stoul(v,&n);check(n==v.size()&&card<4,"card must be0..3");o.card=card;}else if(a=="--mode")o.mode=v;else o.output=v;}else throw std::invalid_argument("unknown/missing option "+a);}check(!o.output.empty()&&(o.mode=="K0"||o.mode=="G3"),"output/mode required");
#ifdef OWN_RT_HOST_ONLY
 check(validation||cpu_fixtures,"host entry requires CPU mode");
#else
 check(!validation&&!cpu_fixtures,"native entry forbids CPU modes");
#endif
 return o;}
#ifdef OWN_RT_HOST_ONLY
struct Cpu final:Backend{
 std::string identity()const override{return "packet30 CPU: no accelerator libraries";}
 void* allocate(size_t n,Memory)override{void* p=nullptr;if(posix_memalign(&p,64,std::max(n,size_t(64))))throw std::bad_alloc();return p;}
 void release(void* p,Memory)override{free(p);}
 Event copy(void* a,const void* b,size_t n,std::span<const Event>)override{std::memcpy(a,b,n);return next_handle();}
 Event marker(std::span<const Event>)override{return next_handle();}
 Event compute(const Operation& op,std::span<void*const> p,std::span<const Event>)override{if(!validation)dynamic_cast<const HostOperation&>(op).run(p);return next_handle();}
 bool complete(Event)override{return true;}bool wait(Event,Deadline)override{return true;}EventTiming timing(Event)override{return {};}
 void synchronize()override{}void clear_events()override{}void close_queue()override{}void close_context()override{}
};
#endif
struct Runner{
 Device device;CopyEngine copy;std::vector<Allocation> owned;unsigned serial=0;
 static std::unique_ptr<Backend> backend(unsigned card){
#ifdef OWN_RT_HOST_ONLY
 (void)card;return std::make_unique<Cpu>();
#else
 return make_sycl_device(card,true);
#endif
 }
 explicit Runner(unsigned card):device(backend(card)),copy(device){}
 Allocation alloc(size_t n,Memory m=Memory::device){auto a=device.arena.allocate("p30-"+std::to_string(serial++),std::max(n,size_t(16)),m,Category::scratch,Lifetime::transaction);owned.push_back(a);return a;}
 void finish(Event e){check(device.wait(e,std::chrono::seconds(300)),"submission deadline300s");stop();}
 Allocation upload(const void* p,size_t n){auto h=alloc(n,Memory::pinned),a=alloc(n);std::memcpy(device.arena.row(h).pointer,p,n);finish(copy.copy(a,0,h,0,n,{}));return a;}
 std::vector<uint8_t> read(Allocation a,size_t n){auto h=alloc(n,Memory::pinned);finish(copy.copy(h,0,a,0,n,{}));std::vector<uint8_t> out(n);std::memcpy(out.data(),device.arena.row(h).pointer,n);return out;}
 void clear(){device.retire_completed_events();for(auto a:owned)device.arena.release(a);owned.clear();}
};
struct Site{Spec spec;std::vector<int> slots;};
struct Fixture{
 std::string klass,workload,family;ng::Shape shape{};std::array<std::vector<uint8_t>,19> data;std::array<size_t,19> sizes{};std::vector<int> outputs;std::vector<std::string> candidates;
 ng::Args args(){ng::Args a;for(int j=0;j<19;++j)a.p[j]=data[j].data();return a;}
 void allocate(){sizes=ng::required_bytes(shape);for(int j=0;j<19;++j)data[j].resize(std::max(sizes[j],size_t(4)));auto a=args();for(int j=0;j<15;++j)for(size_t k=0;k<data[j].size()/2;++k)a.put(j,k,float(int((k*17+j*11)%71)-35)/64.f);a.i(15)[0]=0;a.i(17)[0]=0;a.i(18)[0]=1;}
 Site site(Op op,std::vector<int> ins,std::vector<int> outs,std::vector<int> weights={},int implementation=1){Site t;auto& s=t.spec;s.op=op;s.implementation=implementation;s.g.context=shape.capacity;s.g.budget=shape.budget;s.packed_heads=true;s.ni=ins.size();s.no=outs.size();s.nw=weights.size();s.site.shape[0]=shape.heads;s.site.shape[1]=shape.width;s.site.parameter=shape.flags&1;t.slots=ins;t.slots.insert(t.slots.end(),outs.begin(),outs.end());t.slots.insert(t.slots.end(),weights.begin(),weights.end());for(size_t k=0;k<t.slots.size();++k){int j=t.slots[k];auto ty=Scalar::bf16;if(j==15||j==17||j==18)ty=Scalar::u32;if(family=="route"&&(j==2||j==5||j==6))ty=Scalar::i32;if(family=="route"&&j==3)ty=Scalar::f32;if(family=="attention"&&j==4)ty=Scalar::i32;if(k>=size_t(s.ni+s.no)&&(shape.flags&8))ty=Scalar::f32;s.types[k]=ty;s.sizes[k]=sizes[j]/flash::scalar_bytes(ty);}for(size_t k=0;k<weights.size();++k){s.grids[k]=(shape.flags&8)?iq3::Type::F32:iq3::Type::BF16;s.weight_elements[k]=sizes[weights[k]]/((shape.flags&8)?4:2);}return t;}
 std::vector<Site> sites(bool oracle=false){
  if(family=="route"){auto r=site(Op::route,{0,18,15},oracle?std::vector<int>{2,3}:std::vector<int>{2,3,5,6});r.spec.site.shape[0]=shape.width;r.spec.site.shape[1]=shape.extra;if(!oracle)return {r};auto g=site(Op::expert_gather,{2,1},{5,6,4});return {r,g};}
  if(family=="attention")return {site(Op::qsa_attention,{0,1,2,3,4},{5},{},0)};
  if(shape.op==ng::combine_norm)return {site(Op::hc_combine,{0,1,2},{4}),site(Op::norm,{4},{5},{3})};
  if(shape.op==ng::norm)return {site(Op::norm,{0},{2},{1})};
  return {site(Op::hc_mix,{0,1},{2},{},0)};
 }
 void oracle(){auto ss=sites(true);std::vector<float> scratch(64ull*1024*1024);auto a=args();for(auto& t:ss){std::vector<void*> p;for(int j:t.slots)p.push_back(a.p[j]);p.insert(p.end(),{scratch.data(),a.p[15],a.p[17],a.p[18],a.p[16]});evaluate(t.spec,p.data());}}
};
Fixture make_ng(std::string label,int pos=127,int mode=0){Fixture f;f.klass=label;f.workload=label;f.shape={ng::norm,1,2560,4,0,8,4096,2048};
 if(label=="route"){f.family="route";f.shape={ng::route_gather,1,512,4,10,0,4096,2048};f.outputs={2,3,5,6,15};for(auto v:p30::route::variants)f.candidates.push_back(v);}
 else if(label=="qsa.attention"){f.family="attention";f.shape.op=ng::attention_score;f.shape.flags=0;f.shape.extra=pos+1;f.outputs={5,15};for(int v=0;v<p30::attention::variants;++v)f.candidates.push_back(p30::attention::name(v));}
 else {f.family="fusion";if(label.find("combine")!=std::string::npos){f.shape.op=ng::combine_norm;f.outputs={4,5,15};}else if(label.find("mix")!=std::string::npos){f.shape.op=ng::mix;f.shape.flags=0;f.outputs={2,15};}else f.outputs={2,15};f.candidates={"sg32","tiled"};}
 f.allocate();auto a=f.args();a.i(17)[0]=pos;
 if(f.family=="route"){if(mode==1)std::fill_n(static_cast<uint16_t*>(a.p[0]),512,uint16_t(0));if(mode==2)static_cast<uint16_t*>(a.p[0])[257]=0x7fc1;}
 if(f.family=="attention"){std::fill_n(a.i(4),2051,-1);for(int j=0;j<=pos;++j)a.i(4)[j]=pos-j;}
 if(f.family=="fusion"&&(f.shape.flags&8)){int slot=f.shape.op==ng::combine_norm?3:1;for(size_t j=0;j<f.sizes[slot]/4;++j)a.f(slot)[j]=1.f+float(int(j%7)-3)/128;}
 return f;
}
struct BoundNg{
 Fixture source;std::array<Allocation,19> ids;Allocation scratch,control;
 BoundNg(Runner& r,Fixture f):source(std::move(f)){for(int j=0;j<19;++j)ids[j]=r.upload(source.data[j].data(),source.data[j].size());scratch=r.alloc(2*1024*1024);control=r.alloc(rope_constants::bytes);}
 ng::Args args(Runner& r)const{ng::Args a;for(int j=0;j<19;++j)a.p[j]=r.device.arena.row(ids[j]).pointer;return a;}
 Launch baseline(Runner& r){Launch result{};for(auto& t:source.sites()){std::vector<Allocation> b;for(int j:t.slots)b.push_back(ids[j]);b.insert(b.end(),{scratch,ids[15],ids[17],ids[18],ids[16]});auto e=packet18::submit_parallel(r.device,t.spec,b,control,ids[6],ids[7]);if(!result.first)result.first=e.first;result.last=e.last;result.passes+=e.passes;}return result;}
};
void validate_ng(BoundNg& b,Runner& r,const std::string& v){auto a=b.args(r);auto s=b.source.shape;if(b.source.family=="route")p30::route::validate(s,a,b.source.sizes,r.device.arena.row(b.scratch).pointer,2*1024*1024,v);else if(b.source.family=="attention")p30::attention::validate(s,a,b.source.sizes,v==p30::attention::name(0)?0:1);else p30::fusion::validate(s,a,b.source.sizes,v);}
#ifdef OWN_RT_HOST_ONLY
struct NewNg:HostOperation{Fixture f;std::string variant;void run(std::span<void*const> p)const override{ng::Args a;std::copy_n(p.begin(),19,a.p.begin());if(f.family=="route")p30::route::cpu(f.shape,a,variant);else if(f.family=="attention")p30::attention::cpu(f.shape,a,variant==p30::attention::name(0)?0:1);else p30::fusion::cpu(f.shape,a,f.sizes,variant);}};
#else
struct NewNg:SyclOperation{ng::Shape shape;std::array<size_t,19> sizes;std::string family,variant;std::vector<sycl::event>* events{};
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{ng::Args a;std::copy_n(p.begin(),19,a.p.begin());if(family=="route")*events=p30::route::submit(q,shape,a,static_cast<float*>(p[19]),variant,deps);else if(family=="attention")*events=p30::attention::submit(q,shape,a,static_cast<float*>(p[19]),variant==p30::attention::name(0)?0:1,deps);else *events=p30::fusion::submit(q,shape,a,sizes,variant,deps);return events->back();}
};
#endif
struct Group{Launch launch;
#ifndef OWN_RT_HOST_ONLY
 std::vector<sycl::event> stages;
#endif
};
Group run_ng(Runner& r,BoundNg& b,const std::string& v){Group g;if(v=="incumbent"){g.launch=b.baseline(r);return g;}validate_ng(b,r,v);NewNg op;
#ifdef OWN_RT_HOST_ONLY
 op.f=b.source;op.variant=v;
#else
 op.shape=b.source.shape;op.sizes=b.source.sizes;op.family=b.source.family;op.variant=v;op.events=&g.stages;
#endif
 std::vector<Allocation> ids(b.ids.begin(),b.ids.end());ids.push_back(b.scratch);auto e=r.device.compute(op,ids,{});g.launch={e,e,1};return g;}
std::vector<EventTiming> timings(Runner& r,Group& g){std::vector<EventTiming> out;
#ifndef OWN_RT_HOST_ONLY
 if(!g.stages.empty()){for(auto& e:g.stages)out.push_back({e.get_profiling_info<sycl::info::event_profiling::command_start>(),e.get_profiling_info<sycl::info::event_profiling::command_end>()});return out;}
#endif
 for(Event e=g.launch.first;e<=g.launch.last;++e)out.push_back(r.device.timing(e));return out;}
void record_timing(std::ofstream& out,const std::string& klass,const std::string& workload,const std::string& candidate,unsigned rep,unsigned copies,size_t payload,const std::vector<EventTiming>& ts){for(size_t j=0;j<ts.size();++j)out<<"{\"class\":"<<quote(klass)<<",\"workload\":"<<quote(workload)<<",\"candidate\":"<<quote(candidate)<<",\"repetition\":"<<rep<<",\"event_index\":"<<j<<",\"event_count\":"<<ts.size()<<",\"start_ns\":"<<ts[j].start_ns<<",\"end_ns\":"<<ts[j].end_ns<<",\"exact\":true,\"copies\":"<<copies<<",\"copy_index\":"<<rep%copies<<",\"payload_bytes\":"<<payload<<"}\n";}
bool finite_equal(const std::vector<uint8_t>& a,const std::vector<uint8_t>& b,Scalar type){if(a.size()!=b.size())return false;if(type!=Scalar::bf16&&type!=Scalar::f32)return a==b;size_t width=flash::scalar_bytes(type);for(size_t i=0;i<a.size();i+=width){if(std::memcmp(a.data()+i,b.data()+i,width)==0)continue;float x,y;if(width==2){uint16_t u,v;std::memcpy(&u,a.data()+i,2);std::memcpy(&v,b.data()+i,2);x=iq3::bits_float(uint32_t(u)<<16);y=iq3::bits_float(uint32_t(v)<<16);}else{std::memcpy(&x,a.data()+i,4);std::memcpy(&y,b.data()+i,4);}if(!(std::isnan(x)&&std::isnan(y)))return false;}return true;}
void exact_row(std::ofstream& o,const std::string& k,const std::string& w,const std::string& v,int mode,bool pass,bool bytes,const std::string& hashes){o<<"{\"class\":"<<quote(k)<<",\"workload\":"<<quote(w)<<",\"candidate\":"<<quote(v)<<",\"mode\":"<<mode<<",\"passed\":"<<(pass?"true":"false")<<",\"new_current_bytes_equal\":"<<(bytes?"true":"false")<<",\"output_hashes\":"<<quote(hashes)<<"}\n";o.flush();}
struct BoundSmall{
 std::string name;std::vector<Matrix> matrices;std::vector<unsigned> variants;std::vector<p30::small::Bound> raw;
 BoundSmall(Runner& r,const std::string& n,p30::small::Fixture& f):name(n){auto ss=p30::small::shapes(n);auto x=r.upload(f.inputs[0].data(),f.inputs[0].size()*2);for(size_t j=0;j<ss.size();++j){auto s=ss[j];Matrix m{};m.type=s.type;m.rows=s.rows;m.columns=s.cols;m.experts=1;m.count=1;m.span=s.rows;m.w=r.upload(f.weights[j].data(),f.weights[j].size());m.x=x;m.y=r.upload(f.outputs[j].data(),f.outputs[j].size()*2);m.workspace=r.alloc(s.rows*32);matrices.push_back(m);variants.push_back(s.type==iq3::Type::F32?4:s.split==4?7:6);raw.push_back({static_cast<const uint8_t*>(r.device.arena.row(m.w).pointer),static_cast<const uint16_t*>(r.device.arena.row(m.x).pointer),static_cast<uint16_t*>(r.device.arena.row(m.y).pointer),f.weights[j].size(),f.inputs[0].size(),f.outputs[j].size()});}}
 Launch baseline(Runner& r){if(name=="hc.gate"||name=="shexpdown")return p30::dense_incumbent(r.device,matrices[0],variants[0]);return packet27::small::submit(r.device,name,matrices,variants);}
};
#ifdef OWN_RT_HOST_ONLY
struct NewSmall:HostOperation{std::string name,variant;std::vector<p30::small::Bound> raw;void run(std::span<void*const>)const override{p30::small::cpu(name,raw,variant);}};
#else
struct NewSmall:SyclOperation{std::string name,variant;std::vector<p30::small::Bound> raw;std::vector<sycl::event>* events;sycl::event submit(sycl::queue& q,std::span<void*const>,const std::vector<sycl::event>& deps)const override{*events=p30::small::submit(q,name,raw,variant,deps);return events->back();}};
#endif
Group run_small(Runner& r,BoundSmall& b,const std::string& v){Group g;if(v=="incumbent"){g.launch=b.baseline(r);return g;}p30::small::validate(b.name,b.raw,v);NewSmall op;op.name=b.name;op.variant=v;op.raw=b.raw;
#ifndef OWN_RT_HOST_ONLY
 op.events=&g.stages;
#endif
 std::vector<Allocation> ids;for(auto& m:b.matrices)ids.insert(ids.end(),{m.w,m.x,m.y});auto e=r.device.compute(op,ids,{});g.launch={e,e,1};return g;}
void check_ng(Runner& r,Fixture& f,std::ofstream& exact,std::ofstream& timing,std::ofstream& validations,unsigned& checks,unsigned& failures,unsigned& negatives){
 auto oracle=f;if(!validation)oracle.oracle();std::set<std::string> excluded;std::vector<std::vector<uint8_t>> current;bool base_ok=true;int modes=f.family=="route"?3:1;
 for(int mode=0;mode<modes;++mode){auto source=mode?make_ng(f.klass,127,mode):f;auto host=source;if(!validation)host.oracle();std::vector<std::string> choices{"incumbent"};choices.insert(choices.end(),f.candidates.begin(),f.candidates.end());
 for(auto v:choices){if(excluded.contains(v))continue;BoundNg b(r,source);
  if(validation&&v!="incumbent"){validate_ng(b,r,v);++checks;validations<<"{\"class\":"<<quote(f.klass)<<",\"candidate\":"<<quote(v)<<",\"passed\":true}\n";
   auto saved=b.source.sizes;int output=f.outputs[0];b.source.sizes[output]=0;bool refused=false;try{validate_ng(b,r,v);}catch(const std::invalid_argument&){refused=true;}check(refused,"short candidate output accepted");++negatives;b.source.sizes=saved;
   auto id=b.ids[output];b.ids[output]=b.ids[0];refused=false;try{validate_ng(b,r,v);}catch(const std::invalid_argument&){refused=true;}check(refused,"candidate output alias accepted");++negatives;b.ids[output]=id;r.clear();continue;
  }
  try{auto g=run_ng(r,b,v);r.finish(g.launch.last);if(validation){++checks;r.clear();continue;}std::vector<std::vector<uint8_t>> actual;bool passed=true,bytes=true;std::string hashes;for(size_t j=0;j<f.outputs.size();++j){int slot=f.outputs[j];auto a=r.read(b.ids[slot],source.data[slot].size());auto type=slot==15?Scalar::i32:(f.family=="route"?slot==3?Scalar::f32:Scalar::i32:Scalar::bf16);passed&=finite_equal(a,host.data[slot],type);if(v!="incumbent")bytes&=j<current.size()&&a==current[j];hashes+=packet26::hash(a.data(),a.size())+":";actual.push_back(std::move(a));}if(v=="incumbent"){current=actual;base_ok&=passed;}else passed&=bytes&&base_ok;++checks;exact_row(exact,f.klass,f.workload,v,mode,passed,bytes,hashes);if(!passed){++failures;excluded.insert(v);std::cerr<<f.klass<<" "<<v<<" output mismatch mode"<<mode<<"\n";}}
  catch(const std::invalid_argument& e){if(v=="incumbent")base_ok=false;++failures;excluded.insert(v);exact_row(exact,f.klass,f.workload,v,mode,false,false,e.what());std::cerr<<e.what()<<"\n";}r.clear();
 }
 }
 if(validation||cpu_fixtures||!base_ok)return;
 size_t payload=0;for(auto n:f.sizes)payload+=n;unsigned copies=payload>8*1024*1024?8:1;std::vector<std::unique_ptr<BoundNg>> ring;for(unsigned i=0;i<copies;++i)ring.push_back(std::make_unique<BoundNg>(r,f));std::vector<std::string> names{"incumbent"};for(auto v:f.candidates)if(!excluded.contains(v))names.push_back(v);
 for(auto v:names){for(unsigned rep=0;rep<200;++rep){stop();auto g=run_ng(r,*ring[rep%copies],v);r.finish(g.launch.last);record_timing(timing,f.klass,f.workload,v,rep,copies,payload,timings(r,g));r.device.retire_completed_events();}timing.flush();}r.clear();
}
void check_small(Runner& r,const std::string& klass,const std::string& name,std::ofstream& exact,std::ofstream& timing,std::ofstream& validations,unsigned& checks,unsigned& failures,unsigned& negatives){p30::small::Fixture f(name);auto ss=p30::small::shapes(name);std::vector<std::vector<uint8_t>> host,current;for(size_t j=0;j<ss.size();++j){auto s=ss[j];std::vector<uint16_t> y(s.rows);unsigned variant=s.type==iq3::Type::F32?4:s.split==4?7:6;if(!validation)for(unsigned row=0;row<s.rows;++row)y[row]=iq3::bf16_bits(arithmetic::row(s.type,f.weights[j].data()+row*p30::small::row_bytes(s),f.inputs[j].data(),s.cols,variant));auto* p=reinterpret_cast<uint8_t*>(y.data());host.emplace_back(p,p+y.size()*2);}std::set<std::string> excluded;bool base_ok=true;
 for(std::string v:{"incumbent","sg32","rows4"}){BoundSmall b(r,name,f);if(validation&&v!="incumbent"){p30::small::validate(name,b.raw,v);++checks;validations<<"{\"class\":"<<quote(klass)<<",\"candidate\":"<<quote(v)<<",\"passed\":true}\n";for(int mode=0;mode<3;++mode){auto bad=b.raw;if(mode==0)bad[0].output_elements=0;if(mode==1)bad[0].y=const_cast<uint16_t*>(bad[0].x);if(mode==2)bad[0].weight_bytes=0;bool refused=false;try{p30::small::validate(name,bad,v);}catch(const std::invalid_argument&){refused=true;}check(refused,"small malformed argument accepted");++negatives;}r.clear();continue;}
  try{auto g=run_small(r,b,v);r.finish(g.launch.last);if(validation){++checks;r.clear();continue;}bool passed=true,bytes=true;std::string hashes;std::vector<std::vector<uint8_t>> actual;for(size_t j=0;j<b.matrices.size();++j){auto a=r.read(b.matrices[j].y,host[j].size());passed&=finite_equal(a,host[j],Scalar::bf16);if(v!="incumbent")bytes&=j<current.size()&&a==current[j];hashes+=packet26::hash(a.data(),a.size())+":";actual.push_back(std::move(a));}if(v=="incumbent"){current=actual;base_ok=passed;}else passed&=bytes&&base_ok;++checks;exact_row(exact,klass,klass,v,0,passed,bytes,hashes);if(!passed){++failures;excluded.insert(v);std::cerr<<klass<<" "<<v<<" output mismatch\n";}}catch(const std::invalid_argument& e){if(v=="incumbent")base_ok=false;++failures;excluded.insert(v);exact_row(exact,klass,klass,v,0,false,false,e.what());}r.clear();
 }
 if(validation||cpu_fixtures||!base_ok)return;size_t payload=0;for(auto& w:f.weights)payload+=w.size();for(auto& x:f.inputs)payload+=x.size()*2;unsigned copies=payload>8*1024*1024?8:1;std::vector<std::unique_ptr<BoundSmall>> ring;for(unsigned j=0;j<copies;++j)ring.push_back(std::make_unique<BoundSmall>(r,name,f));for(std::string v:{"incumbent","sg32","rows4"}){if(excluded.contains(v))continue;for(unsigned rep=0;rep<200;++rep){stop();auto g=run_small(r,*ring[rep%copies],v);r.finish(g.launch.last);record_timing(timing,klass,klass,v,rep,copies,payload,timings(r,g));r.device.retire_completed_events();}timing.flush();}r.clear();
}
}
int main(int argc,char** argv){Options o;std::unique_ptr<Runner> runner;unsigned checks=0,failures=0,negatives=0;try{std::signal(SIGTERM,signal_stop);std::signal(SIGINT,signal_stop);o=options(argc,argv);std::filesystem::create_directories(o.output);
#ifndef OWN_RT_HOST_ONLY
 std::vector<sycl::device> devices;
 for(auto p:sycl::platform::get_platforms())if(p.get_backend()==sycl::backend::ext_oneapi_level_zero)
  for(auto d:p.get_devices(sycl::info::device_type::gpu))devices.push_back(d);
 check(!devices.empty(),"no Level Zero GPU device visible (runtime adapter not loaded?)");
 check(o.card<devices.size(),"card index "+std::to_string(o.card)+" out of range ("+std::to_string(devices.size())+" devices)");
 // Conservatively mark contact before context/backend construction: it may
 // partially succeed and then throw. Empty enumeration never reaches this.
 device_contacted=true;
 if(o.mode=="K0"){auto ids=sycl::get_kernel_ids();check(!ids.empty(),"K0 kernels missing");{auto d=devices[o.card];sycl::context ctx(d);auto in=sycl::get_kernel_bundle<sycl::bundle_state::input>(ctx,{d},ids);auto exe=sycl::build(in,{d});for(auto id:ids)check(exe.has_kernel(id,d),"K0 missing executable kernel");}std::ofstream(o.output/"receipt.json")<<"{\"passed\":true,\"completed\":true,\"safe_to_exit\":true,\"device_executed\":true,\"device_contacted\":true,\"kernel_execution\":false,\"mode\":\"K0\",\"live_bytes\":0,\"in_flight\":0,\"finite_element_gate_failures\":0,\"kernels\":"<<ids.size()<<"}\n";return 0;}
#endif
 runner=std::make_unique<Runner>(o.card);auto& r=*runner;std::ofstream exact(o.output/"exactness.jsonl"),timing(o.output/"timing.jsonl"),validations(o.output/"validation-entries.jsonl");
 for(std::string label:{"route","qsa.attention","attn.combine+norm","ffn.combine+norm","hc.a.norm","hc.f.norm","hc.a.mix","hc.f.mix"}){auto f=make_ng(label);check_ng(r,f,exact,timing,validations,checks,failures,negatives);}
 for(auto [klass,name]:std::vector<std::pair<std::string,std::string>>{{"hc.a.gate","hc.gate"},{"hc.f.gate","hc.gate"},{"small.hc","small.hc"},{"small.ffn.q6","small.ffn.q6"},{"small.ffn.q8","small.ffn.q8"},{"shexpdown","shexpdown"}})check_small(r,klass,name,exact,timing,validations,checks,failures,negatives);
 if(failures)std::ofstream(o.output/"failures-before-teardown.json")<<"{\"failures\":"<<failures<<",\"reported_before_teardown\":true}\n";
 auto state=r.device.shutdown(std::chrono::seconds(60));check(state.safe_to_exit&&state.exit_code==0,"teardown incomplete");std::ofstream(o.output/"receipt.json")<<"{\"passed\":"<<(failures?"false":"true")<<",\"completed\":true,\"safe_to_exit\":true,\"device_executed\":"<<((validation||cpu_fixtures)?"false":"true")<<",\"device_contacted\":"<<(device_contacted?"true":"false")<<",\"mode\":"<<quote(o.mode)<<",\"live_bytes\":"<<state.live_bytes<<",\"in_flight\":"<<state.in_flight<<",\"finite_element_gate_failures\":"<<failures<<",\"checks\":"<<checks<<",\"negative_validation_checks\":"<<negatives<<",\"teardown\":"<<state.json()<<"}\n";return failures?2:0;
 }catch(const std::exception& e){std::cerr<<e.what()<<"\n";if(!o.output.empty())std::ofstream(o.output/"contact.json")<<"{\"device_contacted\":"<<(device_contacted?"true":"false")<<"}\n";if(runner)packet26::failure(runner->device,o.output,e.what());else if(!o.output.empty())std::ofstream(o.output/"failure.json")<<"{\"passed\":false,\"device_contacted\":"<<(device_contacted?"true":"false")<<",\"error\":"<<quote(e.what())<<"}\n";return 1;}}
