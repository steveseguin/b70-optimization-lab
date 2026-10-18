#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet142-class-layout/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p49d_fixture.cpp"
// Actual production submission ABI. Every selectable path is exercised regardless
// of selection.json; the device coordinator separately gates captured full-model use.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet142-class-layout/build/checked/experiments/own-xpu-runtime/stage2/packet142-class-layout/p49d_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet142-class-layout/build/checked/experiments/own-xpu-runtime/stage2/packet142-class-layout/p49c_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet142-class-layout/build/checked/experiments/own-xpu-runtime/stage2/packet142-class-layout/p49b_expert_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet142-class-layout/build/checked/experiments/own-xpu-runtime/stage2/packet142-class-layout/p30_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet142-class-layout/build/checked/experiments/own-xpu-runtime/stage2/packet142-class-layout/adapter.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet142-class-layout/build/checked/experiments/own-xpu-runtime/stage2/packet142-class-layout/rope.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet142-class-layout/build/checked/experiments/own-xpu-runtime/stage2/packet142-class-layout/failure.hpp"
#include <array>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>
#include <map>
#include <vector>
namespace {
using namespace ownrt;using namespace integrated;
void check(bool v,const std::string&s){if(!v)throw std::runtime_error(s);}
#ifdef OWN_RT_HOST_ONLY
struct Cpu final:Backend {
 std::string identity()const override{return "CPU packet49d actual submitters";}
 void* allocate(size_t n,Memory)override{return ::operator new(n,std::align_val_t(64));}
 void release(void*p,Memory)override{::operator delete(p,std::align_val_t(64));}
 Event copy(void*a,const void*b,size_t n,std::span<const Event>)override{std::memcpy(a,b,n);return next_handle();}
 Event marker(std::span<const Event>)override{return next_handle();}
 Event compute(const Operation&op,std::span<void*const>p,std::span<const Event>)override{dynamic_cast<const HostOperation&>(op).run(p);return next_handle();}
 bool complete(Event)override{return true;}bool wait(Event,Deadline)override{return true;}
 EventTiming timing(Event)override{return {};}
 void synchronize()override{}void clear_events()override{}void close_queue()override{}void close_context()override{}
};
#endif
struct Runner {
 Device d;CopyEngine copy;std::vector<Allocation>owned;size_t serial=0;std::chrono::steady_clock::time_point deadline;
 static std::unique_ptr<Backend>backend(unsigned card){
#ifdef OWN_RT_HOST_ONLY
 (void)card;return std::make_unique<Cpu>();
#else
 return make_sycl_device(card,true);
#endif
 }
 explicit Runner(unsigned card,unsigned seconds):d(backend(card)),copy(d),deadline(std::chrono::steady_clock::now()+std::chrono::seconds(seconds)){}
 Allocation alloc(size_t n,Memory m=Memory::device){auto id=d.arena.allocate("p49d-fixture-"+std::to_string(serial++),n,m,Category::scratch,Lifetime::transaction);owned.push_back(id);return id;}
 void finish(Event e){auto left=std::chrono::duration_cast<std::chrono::milliseconds>(deadline-std::chrono::steady_clock::now());check(left.count()>0,"fixture total deadline");check(d.wait(e,std::min(left,std::chrono::milliseconds(300000))),"fixture submission timeout");}
 void write(Allocation id,const void*p,size_t n){auto h=alloc(n,Memory::pinned);std::memcpy(d.arena.row(h).pointer,p,n);finish(copy.copy(id,0,h,0,n,{}));d.arena.release(h);owned.pop_back();}
 Allocation upload(const void*p,size_t n){auto id=alloc(n);write(id,p,n);return id;}
 template<class T>Allocation vec(const std::vector<T>&v){return upload(v.data(),v.size()*sizeof(T));}
 Allocation word(uint32_t v){return upload(&v,4);}
 std::vector<uint8_t>read(Allocation id){size_t n=d.arena.row(id).bytes;auto h=alloc(n,Memory::pinned);finish(copy.copy(h,0,id,0,n,{}));auto p=static_cast<uint8_t*>(d.arena.row(h).pointer);std::vector<uint8_t>v(p,p+n);d.arena.release(h);owned.pop_back();return v;}
 using Snap=std::vector<std::vector<uint8_t>>;
 Snap snapshot(const std::vector<Allocation>&ids){Snap out;for(auto id:ids)out.push_back(read(id));return out;}
 void restore(const std::vector<Allocation>&ids,const Snap&v){for(size_t j=0;j<ids.size();++j)write(ids[j],v[j].data(),v[j].size());}
 void clear(){d.retire_completed_events();for(auto id:owned)d.arena.release(id);owned.clear();}
};
std::vector<uint16_t>activation(size_t n,unsigned scenario,unsigned row){std::vector<uint16_t>v(n);for(size_t i=0;i<n;++i)v[i]=iq3::bf16_bits(float(int((i*37+row*73)%257)-128)/512.f);if(scenario==6)v[0]=0x7fc1;if(scenario==7){v[0]=0x7f80;v[8]=0xff80;}if(scenario==8){v[0]=0x0001;v[1]=0x8001;v[2]=0x8000;}return v;}
struct Suite {
 Runner&r;std::ofstream bytes,cases,events;bool timing;size_t checks=0;std::map<std::string,size_t>coverage;
 Suite(Runner&rr,const std::filesystem::path&p,bool t):r(rr),bytes(p/"output.bin",std::ios::binary),cases(p/"cases.jsonl"),events(p/"timings.jsonl"),timing(t){check(bool(bytes)&&bool(cases)&&bool(events),"open fixture outputs");}
 using Call=std::function<Launch()>;
 // Each returned production state is restored last. Therefore the next serial
 // M2 row observes exactly the rounded BF16 state produced by row zero.
 void compare(const std::string&cls,unsigned m,unsigned row,unsigned scenario,const std::vector<Allocation>&ids,const Call&production,const std::vector<std::pair<std::string,Call>>&choices){
  auto initial=r.snapshot(ids);r.finish(production().last);auto expected=r.snapshot(ids);
  const unsigned repeats=timing?210:1;
  for(unsigned iteration=0;iteration<repeats;++iteration)for(const auto&[name,call]:choices){
   r.restore(ids,initial);auto launch=call();r.finish(launch.last);
   if(timing){uint64_t ns=0;events<<"{\"class\":"<<quote(cls)<<",\"candidate\":"<<quote(name)<<",\"m\":1,\"row\":0,\"iteration\":"<<iteration<<",\"warmup\":"<<(iteration<10?"true":"false")<<",\"events\":[";unsigned count=0;for(auto e=launch.first;e<=launch.last;++e){auto t=r.d.timing(e);check(t.start_ns&&t.end_ns>t.start_ns,"valid GPU timing");ns+=t.end_ns-t.start_ns;events<<(count++?",":"")<<"{\"event\":"<<e<<",\"start_ns\":"<<t.start_ns<<",\"end_ns\":"<<t.end_ns<<"}";}check(count==launch.passes,"complete timing launch coverage");events<<"],\"gpu_ns\":"<<ns<<",\"passes\":"<<launch.passes<<",\"byte_exact\":true}\n";}
   auto actual=r.snapshot(ids);for(size_t j=0;j<actual.size();++j)check(actual[j]==expected[j],"byte mismatch class="+cls+" candidate="+name+" scenario="+std::to_string(scenario)+" row="+std::to_string(row)+" allocation="+std::to_string(j));
   if(!timing){if(scenario!=6&&scenario!=7)for(const auto&v:actual){auto digest=packet26::hash(v.data(),v.size());bytes.write(digest.data(),digest.size());}cases<<"{\"class\":"<<quote(cls)<<",\"candidate\":"<<quote(name)<<",\"m\":"<<m<<",\"row\":"<<row<<",\"scenario\":"<<scenario<<",\"passed\":true}\n";}
   ++checks;++coverage[cls+":"+name];r.d.retire_completed_events();
  }
  r.restore(ids,expected);
 }
 template<class F>void reject(F f,const std::string&what){bool refused=false;try{f();}catch(const std::invalid_argument&){refused=true;}check(refused,what+" must refuse");++checks;}
 std::vector<unsigned>ms()const{return timing?std::vector<unsigned>{1}:std::vector<unsigned>{1,2};}
 unsigned scenarios()const{return timing?1:9;}
 void route(){for(unsigned m:ms())for(unsigned scenario=0;scenario<scenarios();++scenario){
  uint32_t ac=scenario==1?0:1,er=scenario==2?7:0;auto active=r.word(ac),error=r.word(er),pos=r.word(0),control=r.alloc(12),dummy=r.alloc(4);
  Spec s{};s.op=Op::route;s.ni=3;s.no=4;s.implementation=6;s.g.h=2560;s.g.mid=640;s.g.context=4096;s.site.shape[0]=512;s.site.shape[1]=10;
  s.sizes[0]=512;s.sizes[1]=s.sizes[2]=1;s.sizes[3]=s.sizes[4]=10;s.sizes[5]=s.sizes[6]=30;s.types[0]=flash::Scalar::bf16;s.types[1]=s.types[2]=flash::Scalar::u32;s.types[3]=s.types[5]=s.types[6]=flash::Scalar::i32;s.types[4]=flash::Scalar::f32;
  auto x=r.vec(activation(512,scenario,0));std::vector<Allocation>a{x,error,active,r.vec(std::vector<int32_t>(10,-7)),r.vec(std::vector<float>(10,-6)),r.vec(std::vector<int32_t>(30,-5)),r.vec(std::vector<int32_t>(30,-4)),r.vec(std::vector<float>(1088,-7.25f)),error,pos,active,dummy};
  std::vector<Allocation>watch(a.begin()+3,a.begin()+8);watch.insert(watch.end(),{error,active,pos});
  auto baseline=[&]{return p49c::route(r.d,s,a);};std::vector<std::pair<std::string,Call>>choices;
  for(std::string name:{"production","route-rank4","route-exp32-rank4"}){auto f=p49d::resolve("route",name);choices.emplace_back(name,[&,f]{return f(r.d,s,a,control,dummy,dummy,{});});}
  for(unsigned row=0;row<m;++row){auto v=activation(512,scenario,row);if(scenario==3)std::fill(v.begin(),v.end(),0);if(scenario==4)std::fill(v.begin(),v.end(),iq3::bf16_bits(-40.f));r.write(x,v.data(),v.size()*2);uint32_t p=scenario==5?4096:row;r.write(pos,&p,4);compare("route",m,row,scenario,watch,baseline,choices);}
  if(!timing)for(std::string name:{"production","route-rank4","route-exp32-rank4"}){auto f=p49d::resolve("route",name);auto bad=a;bad[3]=bad[0];reject([&]{f(r.d,s,bad,control,dummy,dummy,{});},"route output alias");}
  r.clear();
 }}
 void recurrence(){for(unsigned m:ms())for(unsigned scenario=0;scenario<scenarios();++scenario){
  auto active=r.word(scenario==1?0:1),error=r.word(scenario==2?7:0),pos=r.word(0),control=r.alloc(12),scratch=r.vec(std::vector<float>(16,-3.f)),dummy=r.vec(std::vector<uint8_t>(rope_constants::bytes,0));
  Spec s{};s.op=Op::gdn;s.ni=6;s.no=2;s.nw=2;s.implementation=2;s.packed_heads=true;s.g.h=2560;s.g.context=4096;s.grids[0]=s.grids[1]=iq3::Type::F32;
  for(unsigned j=0;j<8;++j)s.types[j]=flash::Scalar::bf16;s.types[4]=s.types[5]=flash::Scalar::u32;s.sizes[0]=10240;s.sizes[1]=s.sizes[2]=48;s.sizes[3]=6144*128;s.sizes[4]=s.sizes[5]=1;s.sizes[6]=6144;s.sizes[7]=6144*128;
  auto qkv=r.vec(activation(10240,scenario,0)),a1=r.vec(activation(48,0,0)),b=r.vec(activation(48,0,1)),state=r.vec(activation(6144*128,0,0)),y=r.vec(std::vector<uint16_t>(6144,0x7e31));
  std::vector<float>decay(48),dt(48);for(unsigned j=0;j<48;++j){decay[j]=-0.125f-float(j)/512;dt[j]=float(int(j%9)-4)/16;}
  std::vector<Allocation>a{qkv,a1,b,state,active,error,y,state,r.vec(decay),r.vec(dt),scratch,error,pos,active,dummy};
  std::vector<Allocation>watch{state,y,scratch,error,pos,active};auto baseline=[&]{return packet18::submit_parallel(r.d,s,a,control,dummy,dummy);};std::vector<std::pair<std::string,Call>>choices;
  for(std::string name:{"production","rows4-shared","rows8-shared"}){auto f=p49d::resolve("recurrence",name);choices.emplace_back(name,[&,f]{return f(r.d,s,a,control,dummy,dummy,{});});}
  for(unsigned row=0;row<m;++row){auto v=activation(10240,scenario,row);r.write(qkv,v.data(),v.size()*2);uint32_t p=scenario==3?4096:scenario==4?0xffffffff:scenario==5?4096-m+row:row;r.write(pos,&p,4);compare("recurrence",m,row,scenario,watch,baseline,choices);}
  if(!timing)for(std::string name:{"rows4-shared","rows8-shared"}){auto f=p49d::resolve("recurrence",name);auto bad=a;bad[0]=control;reject([&]{f(r.d,s,bad,control,dummy,dummy,{});},"recurrence short QKV");bad=a;bad[6]=bad[0];reject([&]{f(r.d,s,bad,control,dummy,dummy,{});},"recurrence output input alias");}
  r.clear();
 }}
 void mix(){for(unsigned m:ms())for(unsigned scenario=0;scenario<scenarios();++scenario){
  auto active=r.word(scenario==1?0:1),error=r.word(scenario==2?7:0),pos=r.word(0),control=r.alloc(12),scratch=r.vec(std::vector<float>(16,-3.f)),dummy=r.vec(std::vector<uint8_t>(rope_constants::bytes,0));
  Spec s{};s.op=Op::hc_mix;s.ni=4;s.no=1;s.implementation=2;s.g.h=2560;s.g.context=4096;s.site.shape[1]=2560;s.sizes[0]=s.sizes[1]=10240;s.sizes[2]=s.sizes[3]=1;s.sizes[4]=2560;s.types[0]=s.types[1]=s.types[4]=flash::Scalar::bf16;s.types[2]=s.types[3]=flash::Scalar::u32;
  auto x=r.vec(activation(10240,scenario,0)),g=r.vec(activation(10240,0,1)),y=r.vec(std::vector<uint16_t>(2560,0x7e31));std::vector<Allocation>a{x,g,active,error,y,scratch,error,pos,active,dummy};std::vector<Allocation>watch{y,scratch,error,pos,active};
  auto baseline=[&]{return packet18::submit_parallel(r.d,s,a,control,dummy,dummy);};std::vector<std::pair<std::string,Call>>choices;
  for(std::string name:{"production","mix-vector4"}){auto f=p49d::resolve("hc",name);choices.emplace_back(name,[&,f]{return f(r.d,s,a,control,dummy,dummy,{});});}
  // The HC class is the two sequential production sides. Both bindings are
  // exercised separately; intervening engine work is covered by model windows.
  for(unsigned row=0;row<m;++row)for(std::string side:{"hc.a.mix","hc.f.mix"}){auto v=activation(10240,scenario,row+(side=="hc.f.mix"?19:0));r.write(x,v.data(),v.size()*2);uint32_t p=scenario==3?4096:scenario==4?0xffffffff:scenario==5?4095:row;r.write(pos,&p,4);compare(side,m,row,scenario,watch,baseline,choices);}
  if(!timing){auto f=p49d::resolve("hc","mix-vector4");auto bad=a;bad[4]=bad[0];reject([&]{f(r.d,s,bad,control,dummy,dummy,{});},"HC output input alias");}
  r.clear();
 }}
 template<iq3::Type T,unsigned K,p39::Kind Kind>void expert(){constexpr bool gate=Kind==p39::Kind::expert_checks;constexpr unsigned rows=gate?640:2560,count=10,experts=10;const std::string cls=gate?"expsgate":"expsdown",name=gate?"virtual8-split-stream":"virtual16";
  const size_t raw_stride=p49bgemv::source_row_bytes(T,K),stride=p49bgemv::layout(T,K).row_bytes;std::vector<uint8_t>raw(raw_stride),packed(size_t(rows)*experts*stride),peer(packed.size());uint32_t seed=0x49d;
  for(unsigned which=0;which<(gate?2u:1u);++which){for(auto&v:raw){seed=seed*1664525u+1013904223u;v=seed>>24;}auto block=iq3::layout(T);for(size_t i=0;i<raw.size();i+=block.bytes){raw[i]=0;raw[i+1]=0x24;}std::vector<uint8_t>one(stride);p49bgemv::repack_row(T,K,raw.data(),one.data());auto&dest=which?peer:packed;for(size_t i=0;i<size_t(rows)*experts;++i)std::memcpy(dest.data()+i*stride,one.data(),stride);}
  for(unsigned m:ms())for(unsigned scenario=0;scenario<scenarios();++scenario){
   auto ac=r.word(scenario==1?0:1),er=r.word(scenario==2?7:0),pos=r.word(0);std::vector<iq3::Route>routes(count);for(unsigned j=0;j<count;++j)routes[j]={j,0,rows};if(scenario==3)routes[2].expert_id=experts;if(scenario==4){routes[0].row_count=0;routes[1].row_begin=1;routes[1].row_count=rows-1;}
   Matrix a{};a.type=T;a.w=r.vec(packed);a.x=r.vec(activation(K*(gate?1:count),scenario,0));a.y=r.vec(std::vector<uint16_t>(rows*count,0x7e31));a.rows=rows;a.columns=K;a.span=rows;a.count=count;a.experts=experts;a.routes=r.vec(routes);a.status=r.vec(std::vector<uint32_t>(count,9));a.workspace=r.vec(std::vector<float>(rows*count*8,-3));auto b=a;if constexpr(gate){b.w=r.vec(peer);b.y=r.vec(std::vector<uint16_t>(rows*count,0x7e32));b.status=r.vec(std::vector<uint32_t>(count,8));}
   std::vector<Matrix>matrices{a};if constexpr(gate)matrices.push_back(b);p39::Bindings controls;controls.active=ac;controls.error=er;controls.position=pos;controls.capacity=4096;
   std::vector<Allocation>watch{a.y,a.status,a.workspace,ac,er,pos};if constexpr(gate){watch.push_back(b.y);watch.push_back(b.status);}
   auto baseline=[&]{return p49b::submit(r.d,matrices,Kind,controls);};std::vector<std::pair<std::string,Call>>choices{{"production",baseline},{name,[&]{return p49d::expert(r.d,matrices,Kind,controls);}}};
   for(unsigned row=0;row<m;++row){auto v=activation(K*(gate?1:count),scenario,row);r.write(a.x,v.data(),v.size()*2);uint32_t p=scenario==5?4096:row;r.write(pos,&p,4);compare(cls,m,row,scenario,watch,baseline,choices);}
   if(!timing){auto bad=matrices;bad[0].columns++;reject([&]{p49d::expert(r.d,bad,Kind,controls);},"expert wrong shape");bad=matrices;bad[0].y=bad[0].x;reject([&]{p49d::expert(r.d,bad,Kind,controls);},"expert output alias");}
   r.clear();
  }
 }
 void small(){auto shapes=packet27::small::shapes("small.ffn.q6");for(unsigned m:ms())for(unsigned scenario:timing?std::vector<unsigned>{0}:std::vector<unsigned>{0,6,7,8}){
  auto x=r.vec(activation(2560,scenario,0));std::vector<Matrix>matrices;std::vector<unsigned>variants;std::vector<Allocation>watch;uint32_t seed=0x49d;
  for(const auto&s:shapes){const auto rb=arithmetic::row_bytes(s.type,s.columns,s.variant);std::vector<uint8_t>row(rb);if(s.type==iq3::Type::F32){for(unsigned j=0;j<s.columns;++j){float v=float(int((j*37+seed)%127)-63)/1024;std::memcpy(row.data()+j*4,&v,4);}}else{for(unsigned j=0;j<s.columns;++j){seed=seed*1664525u+1013904223u;row[j]=seed>>24;}for(unsigned j=0;j<s.columns/16;++j){float v=0.015625f;std::memcpy(row.data()+s.columns+j*4,&v,4);}}
   std::vector<uint8_t>w(size_t(s.rows)*rb);for(unsigned j=0;j<s.rows;++j)std::memcpy(w.data()+size_t(j)*rb,row.data(),rb);Matrix a{};a.type=s.type;a.rows=s.rows;a.columns=s.columns;a.span=s.rows;a.count=a.experts=1;a.w=r.vec(w);a.x=x;a.y=r.vec(std::vector<uint16_t>(s.rows,0x7e31));a.workspace=r.alloc(s.rows*16);matrices.push_back(a);variants.push_back(s.variant);watch.push_back(a.y);
  }
  auto baseline=[&]{return p30integrated::small(r.d,"small.ffn.q6",matrices,variants);};std::vector<std::pair<std::string,Call>>choices{{"production",baseline},{"virtual4",[&]{return p49d::small(r.d,"small.ffn.q6",matrices,variants);}}};
  for(unsigned row=0;row<m;++row){auto v=activation(2560,scenario,row);r.write(x,v.data(),v.size()*2);compare("small.ffn.q6",m,row,scenario,watch,baseline,choices);}
  if(!timing){auto bad=matrices;bad[1].y=bad[0].x;reject([&]{p49d::small(r.d,"small.ffn.q6",bad,variants);},"small tuple alias");auto wrong=variants;wrong[1]=6;reject([&]{p49d::small(r.d,"small.ffn.q6",matrices,wrong);},"small tuple arithmetic variant");}
  r.clear();
 }}
 };
size_t selection_cases(const std::filesystem::path&out){
 size_t checks=0;auto path=out/"selection-parser-fixture.json";
 auto parse=[&](const std::string&text,bool accepted){std::ofstream(path)<<text;p49d::Selection s;bool ok=true;try{s.load(path.string());}catch(const std::invalid_argument&){ok=false;}check(ok==accepted,"selection parser admission");++checks;};
 auto make=[](const std::string&r,const std::string&g,const std::string&h,const std::string&decision){return "{\"schema\":\"packet49d.selection.v1\",\"choices\":{\"route\":"+quote(r)+",\"recurrence\":"+quote(g)+",\"hc\":"+quote(h)+"},\"decision\":"+decision+"}";};
 const std::string valid_decision="{\"path\":\"selection-decision.json\",\"sha256\":\""+std::string(64,'a')+"\"}";
 for(std::string r:{"production","route-rank4","route-exp32-rank4"})for(std::string g:{"production","rows4-shared","rows8-shared"})for(std::string h:{"production","mix-vector4"})for(std::string d:{std::string("null"),valid_decision})parse(make(r,g,h,d),true);
 auto good=make("production","production","production","null");parse(good+"tail",false);parse(make("unknown","production","production","null"),false);parse(make("production","production","norm-subgroup128","null"),false);
 for(std::string bad:std::vector<std::string>{"{}","{\"path\":\"../selection-decision.json\",\"sha256\":\""+std::string(64,'a')+"\"}","{\"path\":\"selection-decision.json\",\"sha256\":\""+std::string(64,'z')+"\"}","{\"path\":\"selection-decision.json\",\"sha256\":\"a\"}"})parse(make("production","production","production",bad),false);
 auto duplicate=good;duplicate.insert(1,"\"decision\":null,");parse(duplicate,false);
 duplicate=good;duplicate.insert(duplicate.find("\"route\""),"\"route\":\"production\",");parse(duplicate,false);
 auto missing=good;auto pos=missing.find("\"hc\":\"production\"");missing.erase(pos-1,18);parse(missing,false);
 std::ofstream(path)<<good;auto expected=packet26::hash(good.data(),good.size());p49d::Selection bound;bound.load(path.string(),expected);check(bound.observed_sha256==expected,"selection same-byte hash binding");++checks;
 std::ofstream(path)<<good+" ";bool stale_refused=false;try{bound.load(path.string(),expected);}catch(const std::invalid_argument&){stale_refused=true;}check(stale_refused,"selection stale expected hash refusal");++checks;
 std::filesystem::remove(path);return checks;
}
}
int main(int argc,char**argv){std::filesystem::path out;std::unique_ptr<Runner>r;bool authorized=false,timing=false;try{unsigned card=0,seconds=1800;for(int i=1;i<argc;++i){std::string k=argv[i];if(k=="--output"&&i+1<argc)out=argv[++i];else if(k=="--card"&&i+1<argc)card=std::stoul(argv[++i]);else if(k=="--authorized-device-window")authorized=true;else if(k=="--timing")timing=true;else if(k=="--seconds"&&i+1<argc){seconds=std::stoul(argv[++i]);check(seconds>=300&&seconds<=86400,"bounded seconds");}else if(k=="--repetitions"&&i+1<argc){check(std::stoul(argv[++i])==200,"exactly 200 measured repetitions");}else if(k=="--stop-fd"&&i+1<argc)ownrt::set_stop_channel(std::stoi(argv[++i]));else throw std::invalid_argument("p49d fixture arguments");}check(!out.empty(),"--output required");
#ifdef OWN_RT_HOST_ONLY
 check(!authorized&&!timing,"CPU binary accepts exact fixtures only");
#else
 check(authorized,"device authorization required");
#endif
 std::filesystem::create_directories(out);r=std::make_unique<Runner>(card,seconds);Suite s(*r,out,timing);s.checks+=selection_cases(out);s.route();s.recurrence();s.mix();s.expert<iq3::Type::IQ2_S,2560,p39::Kind::expert_checks>();s.expert<iq3::Type::IQ4_NL,640,p39::Kind::down_status>();s.small();s.bytes.close();s.cases.close();s.events.close();check(bool(s.bytes)&&bool(s.cases)&&bool(s.events),"fixture flush");auto shutdown=r->d.shutdown(std::chrono::seconds(60));check(shutdown.safe_to_exit&&shutdown.exit_code==0,"fixture safe teardown");std::ifstream in(out/"output.bin",std::ios::binary);std::vector<uint8_t>b((std::istreambuf_iterator<char>(in)),{});std::ofstream receipt(out/"receipt.json");receipt<<"{\"schema\":\"packet49d.all-choice-fixtures.v1\",\"passed\":true,\"device_executed\":"<<(authorized?"true":"false")<<",\"card\":"<<card<<",\"timing\":"<<(timing?"true":"false")<<",\"reference_exact\":true,\"serial_m2_state_carried\":true,\"canonical_excluded_scenarios\":[6,7],\"output_format\":\"ordered-sha256-per-compared-allocation\",\"arithmetic\":\"iq3-p49-split32-v1\",\"checks\":"<<s.checks<<",\"output_sha256\":"<<quote(packet26::hash(b.data(),b.size()))<<",\"coverage\":{";bool first=true;for(auto&[name,n]:s.coverage){receipt<<(first?"":",")<<quote(name)<<":"<<n;first=false;}receipt<<"},\"teardown\":"<<shutdown.json()<<"}\n";receipt.close();check(bool(receipt),"receipt flush");std::cout<<s.checks<<" packet49d all-choice byte checks PASS\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';if(r){std::ofstream(out/"receipt.json")<<"{\"passed\":false,\"error\":"<<quote(e.what())<<"}\n";packet26::failure(r->d,out,e.what());}return 1;}}
