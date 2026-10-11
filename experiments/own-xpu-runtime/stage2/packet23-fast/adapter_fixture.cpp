#include "adapter_fixture.hpp"
#include "adapter.hpp"
#include <fstream>
#include <cstring>
#include <set>
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif
namespace {
using namespace ownrt;using namespace integrated;
#ifdef OWN_RT_HOST_ONLY
struct Cpu:Backend {
 std::string identity()const override{return "CPU actual-adapter fixture";}
 void* allocate(size_t n,Memory)override{return ::operator new(n);}
 void release(void* p,Memory)override{::operator delete(p);}
 Event copy(void* a,const void* b,size_t n,std::span<const Event>)override{std::memcpy(a,b,n);return next_handle();}
 Event marker(std::span<const Event>)override{return next_handle();}
 Event compute(const Operation& op,std::span<void* const> p,std::span<const Event>)override{dynamic_cast<const HostOperation&>(op).run(p);return next_handle();}
 bool complete(Event)override{return true;}bool wait(Event,Deadline)override{return true;}
 EventTiming timing(Event)override{return {0,0};}
 void synchronize()override{}void clear_events()override{}void close_queue()override{}void close_context()override{}
};
#endif
// Rank intentionally stops before top-k normalization; the runtime folds this
// adjacent-tree step into its GEMV. Its independent GEMV fixture covers that
// fused finish. Here the standalone finish makes direct Core route comparison.
void finish_rank(float* p,unsigned count){float tree[32]{};for(unsigned i=0;i<count;++i)tree[i]=p[i];unsigned n=count;while(n>1){if(n%2)tree[n++]=0;for(unsigned i=0;i<n/2;++i)tree[i]=tree[2*i]+tree[2*i+1];n/=2;}for(unsigned i=0;i<count;++i)p[i]=p[i]/tree[0];}
#ifdef OWN_RT_HOST_ONLY
struct Finish:HostOperation {unsigned count;void run(std::span<void*const> p)const override{finish_rank(static_cast<float*>(p[0]),count);}};
#else
struct Finish:ownrt::SyclOperation {unsigned count;sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{auto prob=static_cast<float*>(p[0]);auto n=count;return q.submit([&](sycl::handler& h){h.depends_on(deps);h.single_task([=]{finish_rank(prob,n);});});}};
#endif
struct Buffer {Scalar type;size_t n;std::vector<uint8_t> data;};
struct Site {Spec spec;std::vector<int> ids;};
struct Case {
 Geometry g;std::vector<Buffer> buffers;std::vector<Site> sites;std::set<int> outputs;int error,position,active,rope;bool rank=false;int rank_ids=-1,rank_prob=-1,rank_gate=-1,rank_down=-1;
 Case(){g.context=128;g.budget=2048;error=add(1,Scalar::u32,0,0);position=add(1,Scalar::u32,0,0);active=add(1,Scalar::u32,0,0);*reinterpret_cast<uint32_t*>(buffers[active].data.data())=1;
  std::ifstream in(std::filesystem::path(__FILE__).parent_path()/"rope.bf16",std::ios::binary);Buffer b{Scalar::bf16,262144,{}};b.data.assign(std::istreambuf_iterator<char>(in),{});if(b.data.size()!=b.n*2)throw std::runtime_error("adapter fixture RoPE bytes");rope=buffers.size();buffers.push_back(std::move(b));}
 int add(size_t n,Scalar type=Scalar::bf16,float base=0,float scale=0.03125f){Buffer b{type,n,std::vector<uint8_t>(n*flash::scalar_bytes(type))};View view{b.data.data(),n,type};unsigned salt=buffers.size();for(size_t i=0;i<n;++i)view.put(i,base+scale*float(int((i*13+salt*7)%31)-15));int id=buffers.size();buffers.push_back(std::move(b));return id;}
 Site site(Op op,std::vector<int> inputs,std::vector<int> outs,std::vector<int> weights={},std::initializer_list<int> shape={}){Site r;r.spec.g=g;r.spec.packed_heads=true;r.spec.op=op;r.spec.ni=inputs.size();r.spec.no=outs.size();r.spec.nw=weights.size();r.ids=inputs;r.ids.insert(r.ids.end(),outs.begin(),outs.end());r.ids.insert(r.ids.end(),weights.begin(),weights.end());unsigned j=0;for(auto id:r.ids){r.spec.sizes[j]=buffers[id].n;r.spec.types[j++]=buffers[id].type;}j=0;for(auto id:weights){r.spec.grids[j]=buffers[id].type==Scalar::f32?iq3::Type::F32:iq3::Type::BF16;r.spec.weight_elements[j++]=buffers[id].n;}j=0;for(int v:shape)r.spec.site.shape[j++]=v;outputs.insert(outs.begin(),outs.end());return r;}
};
Case make_case(unsigned kind){Case c;auto add=[&](size_t n,Scalar type=Scalar::bf16,float base=0,float scale=0.03125f){return c.add(n,type,base,scale);};
 if(kind==0){int streams=add(10240),branch=add(2560),inject=add(4),combined=add(10240,Scalar::bf16,0,0),normed=add(10240,Scalar::bf16,0,0),gain=add(10240,Scalar::f32,1),gates=add(10240),mix=add(2560,Scalar::bf16,0,0);
  c.sites={c.site(Op::hc_combine,{streams,branch,inject},{combined},{},{4,2560}),c.site(Op::norm,{combined},{normed},{gain},{4,2560}),c.site(Op::hc_mix,{normed,gates},{mix},{},{4,2560})};
 }else if(kind==1){int input=add(10240),hist=add(30720),convw=add(40960,Scalar::f32,0,0.01f),qkv=add(10240,Scalar::bf16,0,0),a=add(48),b=add(48),decay=add(48,Scalar::f32,-1,0.01f),dt=add(48,Scalar::f32,0,0.01f),state=add(48*128*128),y=add(6144,Scalar::bf16,0,0),gate=add(6144),gain=add(128,Scalar::f32,1),out=add(6144,Scalar::bf16,0,0);
  auto conv=c.site(Op::conv,{input,hist},{qkv,hist},{convw},{10240});conv.spec.site.parameter=1;
  c.sites={conv,c.site(Op::gdn,{qkv,a,b,state},{y,state},{decay,dt},{16,48,128}),c.site(Op::gdn_norm_gate,{y,gate},{out},{gain},{48,128})};
 }else if(kind==2){int qgate=add(12288),k=add(512),iq=add(512),qw=add(256,Scalar::f32,1),kw=add(256,Scalar::f32,1),iw=add(128,Scalar::f32,1),qout=add(6144,Scalar::bf16,0,0),gate=add(6144,Scalar::bf16,0,0),kout=add(512,Scalar::bf16,0,0),iout=add(512,Scalar::bf16,0,0),value=add(512),raw=add(128),pw=add(128,Scalar::f32,1),kc=add(128*512),vc=add(128*512),rc=add(128*128),pool=add(32*128,Scalar::bf16,0,0),indices=add(2051,Scalar::i32,-1,0),out=add(6144,Scalar::bf16,0,0);
  c.sites={c.site(Op::qsa_prepare,{qgate,k,iq},{qout,gate,kout,iout},{qw,kw,iw}),c.site(Op::qsa_append_pool,{kout,value,raw},{kc,vc,rc,pool},{pw}),c.site(Op::qsa_select,{iout,pool},{indices}),c.site(Op::qsa_attention,{qout,gate,kc,vc,indices},{out})};
 }else{c.rank=true;int logits=add(512);c.rank_ids=add(10,Scalar::i32,0,0);c.rank_prob=add(10,Scalar::f32,0,0);c.rank_gate=add(30,Scalar::i32,0,0);c.rank_down=add(30,Scalar::i32,0,0);int input=add(2560),repeated=add(25600,Scalar::bf16,0,0);c.sites={c.site(Op::route,{logits},{c.rank_ids,c.rank_prob},{},{512,10}),c.site(Op::expert_gather,{c.rank_ids,input},{c.rank_gate,c.rank_down,repeated})};c.outputs.erase(repeated);}
 c.outputs.insert(c.error);return c;
}
struct Runner {
 Device d;CopyEngine copy;std::vector<Allocation> owned;Allocation scratch,control,score,probability;uint64_t max=0;size_t allocation_serial=0;
 static std::unique_ptr<Backend> backend(unsigned card){
 #ifdef OWN_RT_HOST_ONLY
 (void)card;return std::make_unique<Cpu>();
 #else
 return make_sycl_device(card,true);
 #endif
 }
 explicit Runner(unsigned card):d(backend(card)),copy(d){scratch=alloc(64ull*1024*1024*4);control=alloc(12);score=alloc(24*2051*4);probability=alloc(24*2051*4);}
 Allocation alloc(size_t n,Memory mem=Memory::device){auto id=d.arena.allocate("actual-adapter-fixture-"+std::to_string(allocation_serial++),n,mem,Category::scratch,Lifetime::transaction);owned.push_back(id);return id;}
 Allocation upload(const std::vector<uint8_t>& data){auto h=alloc(data.size(),Memory::pinned),v=alloc(data.size());std::memcpy(d.arena.row(h).pointer,data.data(),data.size());auto e=copy.copy(v,0,h,0,data.size(),{});if(!d.wait(e,std::chrono::minutes(20)))throw std::runtime_error("adapter fixture upload incomplete");return v;}
 void put(Allocation id,uint32_t v){std::vector<uint8_t>b(4);std::memcpy(b.data(),&v,4);auto h=alloc(4,Memory::pinned);std::memcpy(d.arena.row(h).pointer,b.data(),4);auto e=copy.copy(id,0,h,0,4,{});if(!d.wait(e,std::chrono::minutes(20)))throw std::runtime_error("adapter fixture control upload incomplete");}
 void finish(Launch launch){if(!d.wait(launch.last,std::chrono::minutes(20)))throw std::runtime_error("adapter fixture event incomplete");for(auto e:{launch.first,launch.last}){auto t=d.timing(e);max=std::max(max,t.end_ns-t.start_ns);}}
 std::vector<uint8_t> get(Allocation id,size_t n){auto h=alloc(n,Memory::pinned);auto e=copy.copy(h,0,id,0,n,{});if(!d.wait(e,std::chrono::minutes(20)))throw std::runtime_error("adapter fixture copy incomplete");std::vector<uint8_t> bytes(n);std::memcpy(bytes.data(),d.arena.row(h).pointer,n);return bytes;}
 std::vector<Allocation> binding(const Site& s,const Case& c,const std::vector<Allocation>& buffers){std::vector<Allocation> out;for(auto id:s.ids)out.push_back(buffers[id]);out.insert(out.end(),{scratch,buffers[c.error],buffers[c.position],buffers[c.active],buffers[c.rope]});return out;}
};
}
AdapterFixtureReceipt adapter_fixture_gate(unsigned card,const std::filesystem::path& output){
 Runner runner(card);std::ofstream bytes(output,std::ios::binary|std::ios::app);std::vector<float> host_scratch(64ull*1024*1024);unsigned checks=0;
 for(unsigned m:{1u,3u})for(unsigned kind=0;kind<4;++kind){auto c=make_case(kind);auto host=c.buffers;std::vector<ownrt::Allocation> reference,candidate;for(auto& b:c.buffers){reference.push_back(runner.upload(b.data));candidate.push_back(runner.upload(b.data));}
  for(unsigned step=0;step<m;++step){uint32_t position=3+step;std::memcpy(host[c.position].data.data(),&position,4);runner.put(reference[c.position],position);runner.put(candidate[c.position],position);
   for(const auto& site:c.sites){std::vector<void*> p;for(auto id:site.ids)p.push_back(host[id].data.data());p.insert(p.end(),{host_scratch.data(),host[c.error].data.data(),host[c.position].data.data(),host[c.active].data.data(),host[c.rope].data.data()});integrated::evaluate(site.spec,p.data());
    auto bindings=runner.binding(site,c,reference);auto e=iq3::step_operator(runner.d,site.spec,bindings);runner.finish({e,e,1});}
   if(c.rank){auto site=c.sites[0];site.spec.no=4;site.ids.push_back(c.rank_gate);site.ids.push_back(c.rank_down);site.spec.sizes[3]=30;site.spec.sizes[4]=30;site.spec.types[3]=site.spec.types[4]=Scalar::i32;auto e=packet18::submit_rank(runner.d,site.spec,runner.binding(site,c,candidate));runner.finish(e);
    // Raw selected probabilities agree with the v2 max/exp/adjacent-tree path.
    auto logits=reinterpret_cast<const uint16_t*>(host[site.ids[0]].data.data());std::vector<float> exp(512);float maximum=-INFINITY;for(unsigned i=0;i<512;++i)maximum=std::max(maximum,iq3::bits_float(uint32_t(logits[i])<<16));for(unsigned i=0;i<512;++i)exp[i]=detmath::exp(iq3::bits_float(uint32_t(logits[i])<<16)-maximum);auto sums=exp;for(unsigned n=512;n>1;n/=2)for(unsigned i=0;i<n/2;++i)sums[i]=sums[2*i]+sums[2*i+1];auto raw=runner.get(candidate[c.rank_prob],40);auto ids=reinterpret_cast<const int32_t*>(host[c.rank_ids].data.data());for(unsigned i=0;i<10;++i){float expected=exp[ids[i]]/sums[0];if(std::memcmp(raw.data()+i*4,&expected,4))throw std::runtime_error("actual adapter raw rank probability mismatch");}bytes.write(reinterpret_cast<const char*>(raw.data()),raw.size());
    Finish finish;finish.count=10;std::array b{candidate[c.rank_prob]};auto done=runner.d.compute(finish,b,{});runner.finish({done,done,1});

   }else{std::vector<Spec> specs;std::vector<std::vector<Allocation>> bindings;for(auto& site:c.sites){specs.push_back(site.spec);bindings.push_back(runner.binding(site,c,candidate));}runner.finish(packet18::submit_chain(runner.d,specs,bindings,runner.control,runner.score,runner.probability));}
   for(int id:c.outputs){auto actual=runner.get(candidate[id],host[id].data.size());if(actual!=host[id].data)throw std::runtime_error("actual adapter host parity kind="+std::to_string(kind)+" M="+std::to_string(m)+" step="+std::to_string(step)+" buffer="+std::to_string(id));auto original=runner.get(reference[id],host[id].data.size());if(original!=host[id].data)throw std::runtime_error("actual adapter original device reference parity");bytes.write(reinterpret_cast<const char*>(actual.data()),actual.size());}
   ++checks;runner.d.retire_completed_events();
  }
 }
 auto receipt=runner.d.shutdown(std::chrono::minutes(20));if(!receipt.safe_to_exit)throw std::runtime_error("actual adapter fixture teardown");return {checks,runner.max,receipt.json()};
}
