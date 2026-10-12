#include <iostream>
#include "route42.hpp"
#include "gate_mode.hpp"
#include "stop.hpp"
#include "k2_failure.hpp"
#include "fixture_validation.hpp"

#include "adapter_fixture.hpp"
#include "adapter.hpp"
#include "failure.hpp"
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
 Event compute(const Operation& op,std::span<void* const> p,std::span<const Event>)override{if(!fixture_validation::only)dynamic_cast<const HostOperation&>(op).run(p);return next_handle();}
 bool complete(Event)override{return true;}bool wait(Event,Deadline)override{return true;}
 EventTiming timing(Event)override{return {0,0};}
 void synchronize()override{}void clear_events()override{}void close_queue()override{}void close_context()override{}
};
#endif
struct Buffer {Scalar type;size_t n;std::vector<uint8_t> data;};
struct Site {Spec spec;std::vector<int> ids;};
struct Case {
 Geometry g;std::vector<Buffer> buffers;std::vector<Site> sites,new_sites;std::set<int> outputs;int error,position,active,rope;bool rank=false;int rank_ids=-1,rank_prob=-1,rank_gate=-1,rank_down=-1;
 Case(){g.context=128;g.budget=2048;error=add(1,Scalar::u32,0,0);position=add(1,Scalar::u32,0,0);active=add(1,Scalar::u32,0,0);*reinterpret_cast<uint32_t*>(buffers[active].data.data())=1;
  std::ifstream in(std::filesystem::path("/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet29-merged/rope.bf16"),std::ios::binary);Buffer b{Scalar::bf16,262144,{}};b.data.assign(std::istreambuf_iterator<char>(in),{});if(b.data.size()!=b.n*2)throw std::runtime_error("adapter fixture RoPE bytes");rope=buffers.size();buffers.push_back(std::move(b));}
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
Case make_flat(bool broadcast){Case c;int a=c.add(broadcast?2560:10240),out=c.add(10240,Scalar::bf16,0,0);
 if(broadcast){auto site=c.site(Op::norm,{a},{out});site.spec.special=Special::broadcast;c.sites={site};}
 else{int b=c.add(10240),d=c.add(10240);c.sites={c.site(Op::ple_add,{a,b,d},{out})};}
 c.outputs.insert(c.error);return c;}
// These fixtures exercise exactly the plan-time folded producer ABI, rather
// than timing an equivalent ng fixture under the production class name.
void fold_pair(Case& c){
 if(c.sites.size()<2)throw std::runtime_error("folded fixture requires two sites");
 const auto first=c.sites[0],second=c.sites[1];
 if(first.spec.op==Op::hc_combine&&second.spec.op==Op::norm){
  Site folded=c.site(Op::hc_combine,
   {first.ids[0],first.ids[1],first.ids[2]},
   {first.ids[first.spec.ni],second.ids[second.spec.ni]},
   {second.ids[second.spec.ni+second.spec.no]},
   {first.spec.site.shape[0],first.spec.site.shape[1]});
  folded.spec.fused_combine_norm=true;
  folded.spec.site.parameter=second.spec.site.parameter;
  c.new_sites={folded};
 }else if(first.spec.op==Op::route&&second.spec.op==Op::expert_gather){
  Site folded=c.site(Op::route,{first.ids[0]},
   {first.ids[first.spec.ni],first.ids[first.spec.ni+1],second.ids[second.spec.ni],second.ids[second.spec.ni+1]},
   {},{first.spec.site.shape[0],first.spec.site.shape[1]});
  c.new_sites={folded};
  // The removed repeated row is no longer a model output or binding. Its
  // consumer reads the original input row; model oracle gates cover that path.
  c.outputs.erase(second.ids[second.spec.ni+2]);
 }else throw std::runtime_error("unsupported folded fixture pair");
 for(size_t i=2;i<c.sites.size();++i)c.new_sites.push_back(c.sites[i]);
}
struct Runner {
 Device d;CopyEngine copy;std::vector<Allocation> owned;Allocation scratch,control,score,probability;uint64_t max=0;size_t allocation_serial=0;std::ofstream* events=nullptr;std::string klass,variant,candidate,implementation;unsigned repetition=0;std::chrono::steady_clock::time_point host_start;
 static std::unique_ptr<Backend> backend(unsigned card){
 #ifdef OWN_RT_HOST_ONLY
 (void)card;return std::make_unique<Cpu>();
 #else
 return make_sycl_device(card,true);
 #endif
 }
 explicit Runner(unsigned card):d(backend(card)),copy(d){}
 void initialize(){scratch=alloc((64+1024)*4);control=alloc(12);score=alloc(24*2051*4);probability=alloc(24*2051*4);}
 Allocation alloc(size_t n,Memory mem=Memory::device){auto id=d.arena.allocate("actual-adapter-fixture-"+std::to_string(allocation_serial++),n,mem,Category::scratch,Lifetime::transaction);owned.push_back(id);return id;}
 Allocation upload(const std::vector<uint8_t>& data){auto h=alloc(data.size(),Memory::pinned),v=alloc(data.size());std::memcpy(d.arena.row(h).pointer,data.data(),data.size());auto e=copy.copy(v,0,h,0,data.size(),{});if(!d.wait(e,std::chrono::seconds(300)))throw std::runtime_error("adapter fixture upload incomplete");return v;}
 void put(Allocation id,uint32_t v){std::vector<uint8_t>b(4);std::memcpy(b.data(),&v,4);auto h=alloc(4,Memory::pinned);std::memcpy(d.arena.row(h).pointer,b.data(),4);auto e=copy.copy(id,0,h,0,4,{});if(!d.wait(e,std::chrono::seconds(300)))throw std::runtime_error("adapter fixture control upload incomplete");}
 void finish(Launch launch){if(!d.wait(launch.last,std::chrono::seconds(300)))throw std::runtime_error("adapter fixture event incomplete");double host_us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-host_start).count();for(auto e=launch.first;e<=launch.last;++e){auto t=d.timing(e);if(t.end_ns>t.start_ns)max=std::max(max,t.end_ns-t.start_ns);if(events)*events<<"{\"class\":"<<quote(klass)<<",\"variant\":"<<quote(variant)<<",\"candidate\":"<<quote(candidate)<<",\"implementation\":"<<quote(implementation)<<",\"kernel_identity\":"<<quote(klass+":"+implementation)<<",\"repetition\":"<<repetition<<",\"event\":"<<e<<",\"host_wall_us\":"<<host_us<<",\"bytes_equal\":true,\"stage_count\":"<<(launch.last-launch.first+1)<<",\"start_ns\":"<<t.start_ns<<",\"end_ns\":"<<t.end_ns<<",\"exact\":true}\n";}}
 std::vector<uint8_t> get(Allocation id,size_t n){auto h=alloc(n,Memory::pinned);auto e=copy.copy(h,0,id,0,n,{});if(!d.wait(e,std::chrono::seconds(300)))throw std::runtime_error("adapter fixture copy incomplete");std::vector<uint8_t> bytes(n);std::memcpy(bytes.data(),d.arena.row(h).pointer,n);return bytes;}
 std::vector<Allocation> binding(const Site& s,const Case& c,const std::vector<Allocation>& buffers){std::vector<Allocation> out;for(auto id:s.ids)out.push_back(buffers[id]);out.insert(out.end(),{scratch,buffers[c.error],buffers[c.position],buffers[c.active],buffers[c.rope]});return out;}
};
}

AdapterFixtureReceipt route42_timing(unsigned card,const std::filesystem::path&out){Runner runner(card);try{runner.initialize();std::ofstream events,failures;events.exceptions(std::ios::badbit|std::ios::failbit);failures.exceptions(std::ios::badbit|std::ios::failbit);events.open(out/"events.jsonl");failures.open(out/"candidate-failures.jsonl");auto c=make_case(3);for(int id:{c.rank_ids,c.rank_gate,c.rank_down})c.buffers[id].type=Scalar::u32;int logits=c.sites[0].ids[0];c.sites={c.site(Op::route,{logits,c.active,c.error},{c.rank_ids,c.rank_prob,c.rank_gate,c.rank_down},{},{512,10})};c.outputs={c.rank_ids,c.rank_prob,c.rank_gate,c.rank_down,c.error};auto host=c.buffers;std::vector<float>scratch(262144);for(auto&site:c.sites){std::vector<void*>ptr;for(auto id:site.ids)ptr.push_back(host[id].data.data());ptr.insert(ptr.end(),{scratch.data(),host[c.error].data.data(),host[c.position].data.data(),host[c.active].data.data(),host[c.rope].data.data()});integrated::evaluate(site.spec,ptr.data());View ids{host[c.rank_ids].data.data(),10,Scalar::u32},gates{host[c.rank_gate].data.data(),30,Scalar::u32},downs{host[c.rank_down].data.data(),30,Scalar::u32};for(int k=0;k<10;++k)for(int z=0;z<3;++z){gates.put(k*3+z,z==0?ids.get(k):z==1?0:c.g.mid);downs.put(k*3+z,z==0?ids.get(k):z==1?0:c.g.h);}}
 std::vector<Allocation>prepared[2];for(int version:{0,1})for(auto&b:c.buffers)prepared[version].push_back(runner.upload(b.data));bool excluded[2]{};unsigned checks=0;
 for(unsigned repeat=0;repeat<200;++repeat)for(int version:{0,1})if(!excluded[version]){p42::check_stop();try{runner.events=&events;runner.klass="route";runner.variant=version?"specialised":"packet18";runner.candidate="p42.route.production_rank32";runner.implementation=version?"p42.route.production_rank32":"specialised";runner.repetition=repeat;auto site=c.sites[0];site.spec.implementation=1;auto bound=runner.binding(site,c,prepared[version]);runner.host_start=std::chrono::steady_clock::now();auto launch=version?route42::submit(runner.d,site.spec,bound):packet18::submit_parallel(runner.d,site.spec,bound,runner.control,runner.score,runner.probability);runner.finish(launch);runner.events=nullptr;
 for(int id:c.outputs)if(!p42gate::bindings_only&&runner.get(prepared[version][id],host[id].data.size())!=host[id].data)throw std::invalid_argument("route42 output bytes differ from reference core");runner.d.retire_completed_events();++checks;
 }catch(const std::invalid_argument&e){runner.events=nullptr;failures<<"{\"class\":\"route\",\"candidate\":\"p42.route.production_rank32\",\"implementation\":\"p42.route.production_rank32\",\"variant\":\""<<(version?"specialised":"packet18")<<"\",\"error\":"<<ownrt::quote(e.what())<<"}\n";failures.flush();excluded[version]=true;runner.d.retire_completed_events();}}
 events.close();failures.close();auto state=runner.d.shutdown(std::chrono::seconds(300));if(!state.safe_to_exit||state.exit_code)throw std::runtime_error("route42 teardown failed");return {checks,runner.max,state.json()};
 }catch(const std::exception&e){try{std::ofstream failure;failure.exceptions(std::ios::badbit|std::ios::failbit);failure.open(out/"failure.json");failure<<"{\"infrastructure_passed\":false,\"error\":"<<ownrt::quote(e.what())<<"}\n";failure.close();}catch(const std::exception&s){std::cerr<<"FAILED route42 receipt write: "<<s.what()<<'\n';}runner.d.shutdown(std::chrono::seconds(300));throw;}}
