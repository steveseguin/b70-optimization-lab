#include "p39_submit.hpp"
#include "p39_fixture_data.hpp"
#include "adapter_fixture.hpp"
#include "adapter.hpp"
#include "p33_submit.hpp"
#include "fixture_validation.hpp"
#include <fstream>
#include <openssl/sha.h>
namespace {
using namespace ownrt;using integrated::Launch;using integrated::Matrix;
#ifdef OWN_RT_HOST_ONLY
struct Cpu:Backend {
 std::string identity()const override{return "CPU p39 merged fixture";}
 void* allocate(size_t n,Memory)override{return ::operator new(n);}void release(void*p,Memory)override{::operator delete(p);}
 Event copy(void*a,const void*b,size_t n,std::span<const Event>)override{std::memcpy(a,b,n);return next_handle();}
 Event marker(std::span<const Event>)override{return next_handle();}
 Event compute(const Operation&op,std::span<void*const>p,std::span<const Event>)override{if(!fixture_validation::only)dynamic_cast<const integrated::HostOperation&>(op).run(p);return next_handle();}
 bool complete(Event)override{return true;}bool wait(Event,Deadline)override{return true;}EventTiming timing(Event)override{return {0,0};}
 void synchronize()override{}void clear_events()override{}void close_queue()override{}void close_context()override{}
};
#endif
struct OwnerBackend {
 static constexpr bool binding_only=false;
 Device d;CopyEngine copier;std::map<const void*,Allocation> ids;size_t serial=0;uint64_t maximum=0;
 static std::unique_ptr<Backend> backend(unsigned card){
#ifdef OWN_RT_HOST_ONLY
 (void)card;return std::make_unique<Cpu>();
#else
 return make_sycl_device(card,true);
#endif
 }
 explicit OwnerBackend(unsigned card):d(backend(card)),copier(d){}
#ifdef OWN_RT_HOST_ONLY
 explicit OwnerBackend(std::unique_ptr<Backend> backend):d(std::move(backend)),copier(d){}
#endif
 Allocation allocate(size_t n,Memory m=Memory::device){return d.arena.allocate("p39-fixture-"+std::to_string(serial++),std::max(n,size_t(4)),m,Category::scratch,Lifetime::transaction);}
 template<class T>T* alloc(size_t n){auto id=allocate(n*sizeof(T));auto ptr=d.arena.row(id).pointer;ids.emplace(ptr,id);return static_cast<T*>(ptr);}
 Allocation id(const void*p){return ids.at(p);}
 void copy(void*dst,const void*src,size_t n){
  if(!n)return;
  auto to=ids.find(dst),from=ids.find(src);
  if(to==ids.end()&&from==ids.end()){std::memcpy(dst,src,n);return;}
  // A production expert bank exceeds CopyEngine's single-copy bound.
  // Reuse one bounded pinned slab only after each transfer has completed.
  constexpr size_t slab_bytes=4*1024*1024;
  auto host=allocate(std::min(n,slab_bytes),Memory::pinned);
  auto hp=d.arena.row(host).pointer;
  for(size_t offset=0;offset<n;offset+=slab_bytes){
   const size_t bytes=std::min(n-offset,slab_bytes);
   if(from==ids.end())std::memcpy(hp,static_cast<const uint8_t*>(src)+offset,bytes);
   auto e=copier.copy(to==ids.end()?host:to->second,to==ids.end()?0:offset,
                      from==ids.end()?host:from->second,from==ids.end()?0:offset,bytes,{});
   if(!d.wait(e,std::chrono::seconds(300)))throw std::runtime_error("p39 fixture copy deadline");
   if(to==ids.end())std::memcpy(static_cast<uint8_t*>(dst)+offset,hp,bytes);
   d.retire_completed_events();
  }
  d.arena.release(host);
 }
 void wait(){d.retire_completed_events();}
 void free(void*p){d.arena.release(ids.at(p));ids.erase(p);}
 void finish(Launch l){if(!d.wait(l.last,std::chrono::seconds(300)))throw std::runtime_error("p39 fixture launch deadline");}
};
struct BoundFixture {
 OwnerBackend&q;p39::Bound b;std::vector<Matrix> matrices;p39::Bindings tails;Allocation scratch,control,rope;
 BoundFixture(OwnerBackend&v,p39::Bound value,Type t,unsigned k):q(v),b(value){
 Matrix m{};m.type=t;m.w=q.id(b.w);m.x=q.id(b.x);m.y=q.id(b.y);m.rows=b.rows;m.columns=k;m.span=b.rows;m.count=b.count;m.experts=b.experts;m.workspace=q.id(b.scratch);if(b.experts>1){m.routes=q.id(b.routes);m.status=q.id(b.status);}matrices={m};
 if(t==Type::IQ2_S||t==Type::IQ3_S){m.w=q.id(b.peer);m.y=q.id(b.py);m.status=q.id(b.peer_status);matrices.push_back(m);}
 tails={q.id(b.other),q.id(b.out),q.id(b.streams),q.id(b.inject),q.id(b.mixture),q.id(b.shared_gate),q.id(b.one),q.id(b.error),q.id(b.active),q.id(b.position),b.capacity};
 scratch=q.allocate(4*1024*1024);control=q.allocate(12);rope=q.allocate(rope_constants::bytes);
 }
 ~BoundFixture(){q.d.retire_completed_events();q.d.arena.release(rope);q.d.arena.release(control);q.d.arena.release(scratch);}
 Launch tail(integrated::Spec s,std::vector<const void*> inputs,std::vector<const void*>outputs){
 s.g.h=2560;s.g.context=b.capacity;s.ni=inputs.size();s.no=outputs.size();std::vector<Allocation>a;
 auto append=[&](const void*p){auto id=q.id(p);auto j=a.size();a.push_back(id);s.sizes[j]=q.d.arena.row(id).bytes/flash::scalar_bytes(s.types[j]);};
 for(auto p:inputs)append(p);for(auto p:outputs)append(p);
 a.insert(a.end(),{scratch,q.id(b.error),q.id(b.position),q.id(b.active),rope});return packet18::submit_parallel(q.d,s,a,control,scratch,scratch);
 }
 Launch unfused(p39::Kind kind,unsigned split){
 unsigned v=(matrices[0].type==Type::Q6_K||matrices[0].type==Type::Q8_0)?(split==4?7:6):2;
 auto result=kind==Kind::down_status?p33::submit(q.d,matrices,"p33.down.select",false,v):p28::submit(q.d,matrices,kind==Kind::expert_checks?"p28.paired.wg32":kind==Kind::silu_div4||kind==Kind::shared_act?"p28.dense.rows4":"p28.dense.wg32",kind==Kind::expert_checks,v);
 auto append=[&](Launch l){result.last=l.last;result.passes+=l.passes;};
 auto status=[&](const uint32_t*p){integrated::Spec s{};s.special=integrated::Special::check_status;s.types[0]=flash::Scalar::u32;append(tail(s,{p},{}));};
 auto combine=[&](const uint16_t*p){integrated::Spec s{};s.op=integrated::Op::hc_combine;s.site.shape[1]=b.rows;s.implementation=1;append(tail(s,{b.streams,p,b.inject},{b.streams}));};
 if(kind==Kind::expert_checks){status(b.status);status(b.peer_status);}
 else if(kind==Kind::down_status)status(b.status);
 else if(kind==Kind::attention_combine)combine(b.y);
 else if(kind==Kind::shared_combine){integrated::Spec s{};s.op=integrated::Op::moe_combine;s.site.shape[0]=1;s.site.shape[1]=b.rows;s.types[1]=flash::Scalar::f32;append(tail(s,{b.mixture,b.one,b.y,b.shared_gate},{b.out}));combine(b.out);}
 else {integrated::Spec s{};s.op=kind==Kind::silu_div4?integrated::Op::silu_div4:integrated::Op::silu_product;s.site.shape[0]=b.rows*b.count;append(tail(s,kind==Kind::silu_div4?std::vector<const void*>{b.y}:std::vector<const void*>{b.other,b.y},{b.out}));}
 return result;
 }
};
}
AdapterFixtureReceipt p39_fixture_gate(unsigned card,const std::filesystem::path&out,bool timing){
 OwnerBackend q(card);std::ofstream events(out/"events.jsonl",std::ios::app);std::ofstream outputs(out/"output.bin",std::ios::binary|std::ios::app);unsigned gates=0;
 try {g4_cases([&]<Type T,unsigned K,Kind E,unsigned Split>(const char* name,unsigned rows,double frequency,unsigned removed){
  if constexpr(E==Kind::expert_act||E==Kind::gdn_conv)return;
  else {P39Fixture<OwnerBackend> f(q);f.template init<T,K,E>(timing&&!fixture_validation::only?rows:E==Kind::down_status?2560:4,timing&&!fixture_validation::only);
   BoundFixture bound(q,f.b,T,K);
   auto perform=[&](bool fused){bound.matrices[0].w=q.id(f.b.w);if(bound.matrices.size()==2)bound.matrices[1].w=q.id(f.b.peer);return fused?p39::submit(q.d,bound.matrices,E,bound.tails):bound.unfused(E,Split);};
   for(unsigned scenario=0;scenario<7;++scenario){std::vector<uint8_t> expected;
    for(unsigned arm=0;arm<2;++arm){f.reset();uint32_t v=1;
     if(scenario==1&&f.b.experts>1){iq3::Route bad{f.b.experts,0,f.b.rows};q.copy(const_cast<iq3::Route*>(f.b.routes),&bad,sizeof bad);}
     if(scenario==2){v=0;q.copy(const_cast<uint32_t*>(f.b.active),&v,4);}
     if(scenario==3){v=7;q.copy(f.b.error,&v,4);}
     if(scenario==4){uint16_t nan=0x7fc1;q.copy(const_cast<uint16_t*>(f.b.x),&nan,2);}
     if(scenario>=5){v=scenario==5?f.b.capacity:UINT32_MAX;q.copy(const_cast<uint32_t*>(f.b.position),&v,4);}
     auto l=perform(arm);q.finish(l);auto bytes=f.snapshot();if(!arm)expected=bytes;else if(bytes!=expected)throw std::runtime_error(std::string("p39 integrated byte mismatch ")+name+" scenario="+std::to_string(scenario));if(arm){uint64_t length=bytes.size();unsigned char digest[32];SHA256(bytes.data(),bytes.size(),digest);outputs.write(reinterpret_cast<const char*>(&length),sizeof length);outputs.write(reinterpret_cast<const char*>(digest),sizeof digest);}q.d.retire_completed_events();
    }++gates;
   }
   if(timing&&!fixture_validation::only){for(unsigned repeat=0;repeat<200;++repeat)for(unsigned arm=0;arm<2;++arm){unsigned copy=(repeat+(arm?4:0))%f.rotations;f.b.w=f.weights[copy];f.b.peer=f.peers[copy];f.reset();auto l=perform(arm);q.finish(l);
    for(auto event=l.first;event<=l.last;++event){auto t=q.d.timing(event);q.maximum=std::max(q.maximum,t.end_ns-t.start_ns);events<<"{\"class\":\"fusion:p39."<<name<<"\",\"candidate\":\"p39.epilogue\",\"implementation\":\""<<(arm?"p39.epilogue":"packet18")<<"\",\"variant\":\""<<(arm?"specialised":"packet18")<<"\",\"kernel_identity\":\"p39."<<name<<(arm?".fused":".unfused")<<"\",\"exact\":true,\"candidate_available\":true,\"repetition\":"<<repeat<<",\"event\":"<<event<<",\"stage_count\":"<<l.passes<<",\"start_ns\":"<<t.start_ns<<",\"end_ns\":"<<t.end_ns<<",\"timing_mode\":\""<<(f.rotations==8?"rotated":"reread")<<"\",\"rotation_copies\":"<<f.rotations<<",\"buffer_copy\":"<<copy<<",\"payload_bytes\":"<<f.weight_bytes*(E==Kind::expert_checks?2:1)<<",\"full_payload_bytes\":"<<f.weight_bytes*(E==Kind::expert_checks?2:1)<<"}\n";}q.d.retire_completed_events();
   }}f.release();
  }
 });auto shutdown=q.d.shutdown(std::chrono::seconds(60));if(!shutdown.safe_to_exit||shutdown.exit_code)throw std::runtime_error("p39 fixture teardown");return {gates,q.maximum,shutdown.json()};
 }catch(const std::exception&e){std::ofstream(out/"p39-failure.json")<<"{\"passed\":false,\"error\":"<<ownrt::quote(e.what())<<"}\n";auto shutdown=q.d.shutdown(std::chrono::seconds(60));throw;}
}
