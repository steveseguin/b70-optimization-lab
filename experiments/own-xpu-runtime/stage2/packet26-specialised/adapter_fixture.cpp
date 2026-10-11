
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
 Event compute(const Operation& op,std::span<void* const> p,std::span<const Event>)override{dynamic_cast<const HostOperation&>(op).run(p);return next_handle();}
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
 Device d;CopyEngine copy;std::vector<Allocation> owned;Allocation scratch,control,score,probability;uint64_t max=0;size_t allocation_serial=0;std::ofstream* events=nullptr;std::string klass,variant;unsigned repetition=0;
 static std::unique_ptr<Backend> backend(unsigned card){
 #ifdef OWN_RT_HOST_ONLY
 (void)card;return std::make_unique<Cpu>();
 #else
 return make_sycl_device(card,true);
 #endif
 }
 explicit Runner(unsigned card):d(backend(card)),copy(d){}
 void initialize(){scratch=alloc(64ull*1024*1024*4);control=alloc(12);score=alloc(24*2051*4);probability=alloc(24*2051*4);}
 Allocation alloc(size_t n,Memory mem=Memory::device){auto id=d.arena.allocate("actual-adapter-fixture-"+std::to_string(allocation_serial++),n,mem,Category::scratch,Lifetime::transaction);owned.push_back(id);return id;}
 Allocation upload(const std::vector<uint8_t>& data){auto h=alloc(data.size(),Memory::pinned),v=alloc(data.size());std::memcpy(d.arena.row(h).pointer,data.data(),data.size());auto e=copy.copy(v,0,h,0,data.size(),{});if(!d.wait(e,std::chrono::seconds(300)))throw std::runtime_error("adapter fixture upload incomplete");return v;}
 void put(Allocation id,uint32_t v){std::vector<uint8_t>b(4);std::memcpy(b.data(),&v,4);auto h=alloc(4,Memory::pinned);std::memcpy(d.arena.row(h).pointer,b.data(),4);auto e=copy.copy(id,0,h,0,4,{});if(!d.wait(e,std::chrono::seconds(300)))throw std::runtime_error("adapter fixture control upload incomplete");}
 void finish(Launch launch){if(!d.wait(launch.last,std::chrono::seconds(300)))throw std::runtime_error("adapter fixture event incomplete");for(auto e=launch.first;e<=launch.last;++e){auto t=d.timing(e);if(t.end_ns>t.start_ns)max=std::max(max,t.end_ns-t.start_ns);if(events)*events<<"{\"class\":"<<quote(klass)<<",\"variant\":"<<quote(variant)<<",\"repetition\":"<<repetition<<",\"event\":"<<e<<",\"start_ns\":"<<t.start_ns<<",\"end_ns\":"<<t.end_ns<<",\"exact\":true}\n";}}
 std::vector<uint8_t> get(Allocation id,size_t n){auto h=alloc(n,Memory::pinned);auto e=copy.copy(h,0,id,0,n,{});if(!d.wait(e,std::chrono::seconds(300)))throw std::runtime_error("adapter fixture copy incomplete");std::vector<uint8_t> bytes(n);std::memcpy(bytes.data(),d.arena.row(h).pointer,n);return bytes;}
 std::vector<Allocation> binding(const Site& s,const Case& c,const std::vector<Allocation>& buffers){std::vector<Allocation> out;for(auto id:s.ids)out.push_back(buffers[id]);out.insert(out.end(),{scratch,buffers[c.error],buffers[c.position],buffers[c.active],buffers[c.rope]});return out;}
};
}
AdapterFixtureReceipt adapter_fixture_gate(unsigned card,const std::filesystem::path& output){
 Runner runner(card);try {runner.initialize();size_t base_owned=runner.owned.size();std::ofstream bytes(output,std::ios::binary|std::ios::app);std::vector<float> scratch(64ull*1024*1024);unsigned checks=0;
 std::vector<Case> cases;for(unsigned kind=0;kind<4;++kind)cases.push_back(make_case(kind));cases.push_back(make_flat(true));cases.push_back(make_flat(false));
 for(int unit:{0,1}){auto c=make_case(0);c.sites[1].spec.site.parameter=unit;fold_pair(c);cases.push_back(std::move(c));}
 for(int mode=0;mode<3;++mode){auto c=make_case(3);auto id=c.sites[0].ids[0];
  if(mode==1)std::fill(c.buffers[id].data.begin(),c.buffers[id].data.end(),0);
  if(mode==2){uint16_t nan=0x7fc0;std::memcpy(c.buffers[id].data.data()+512,&nan,2);}
  fold_pair(c);cases.push_back(std::move(c));}
 for(int n:{1,3,17,255,512})for(int mode=0;mode<3;++mode){Case c;c.g.experts=n;c.g.top=std::min(n,10);int logits=c.add(n),ids=c.add(c.g.top,Scalar::i32,0,0),prob=c.add(c.g.top,Scalar::f32,0,0);
  if(mode==1)std::fill(c.buffers[logits].data.begin(),c.buffers[logits].data.end(),0);
  if(mode==2){uint16_t nan=0x7fc0;std::memcpy(c.buffers[logits].data.data()+2*(n/2),&nan,2);}
  c.sites={c.site(Op::route,{logits},{ids,prob},{},{n,c.g.top})};c.outputs.insert(c.error);cases.push_back(std::move(c));
 }
 for(int n:{1,3,17,255,512,153600})for(int mode=0;mode<3;++mode){Case c;int input=c.add(n),out=c.add(1,Scalar::i32,0,0);
  if(mode==1)std::fill(c.buffers[input].data.begin(),c.buffers[input].data.end(),0);
  if(mode==2){uint16_t nan=0x7fc0;std::memcpy(c.buffers[input].data.data()+2*(n/2),&nan,2);}
  c.sites={c.site(Op::argmax,{input},{out,c.error})};c.outputs.insert(c.error);cases.push_back(std::move(c));
 }
 for(auto& c:cases){auto host=c.buffers;uint32_t position=3;std::memcpy(host[c.position].data.data(),&position,4);
  for(auto& site:c.sites){std::vector<void*> ptr;for(auto id:site.ids)ptr.push_back(host[id].data.data());ptr.insert(ptr.end(),{scratch.data(),host[c.error].data.data(),host[c.position].data.data(),host[c.active].data.data(),host[c.rope].data.data()});integrated::evaluate(site.spec,ptr.data());}
  std::vector<std::vector<uint8_t>> old_bytes;
  for(int version:{0,1}){std::vector<Allocation> allocated;for(auto& b:c.buffers)allocated.push_back(runner.upload(b.data));runner.put(allocated[c.position],position);
   for(auto site:(version&&!c.new_sites.empty()?c.new_sites:c.sites)){site.spec.implementation=version;runner.finish(packet18::submit_parallel(runner.d,site.spec,runner.binding(site,c,allocated),runner.control,runner.score,runner.probability));}
   size_t j=0;for(int id:c.outputs){auto actual=runner.get(allocated[id],host[id].data.size());if(actual!=host[id].data)throw std::runtime_error("actual adapter core mismatch case="+std::to_string(checks)+" version="+std::to_string(version)+" buffer="+std::to_string(id));if(!version)old_bytes.push_back(actual);else if(actual!=old_bytes[j])throw std::runtime_error("actual adapter p18/new mismatch");++j;bytes.write(reinterpret_cast<const char*>(actual.data()),actual.size());}
   runner.d.retire_completed_events();while(runner.owned.size()>base_owned){runner.d.arena.release(runner.owned.back());runner.owned.pop_back();}
  }++checks;
 }
 auto state=runner.d.shutdown(std::chrono::seconds(60));if(!state.safe_to_exit||state.exit_code)throw std::runtime_error("adapter fixture teardown");return {checks,runner.max,state.json()};
 }catch(const std::exception& e){std::ofstream(output.parent_path()/"adapter-failure.json")<<"{\"passed\":false,\"error\":"<<ownrt::quote(e.what())<<"}\n";packet26::failure(runner.d,output.parent_path(),e.what());throw;}}

AdapterFixtureReceipt adapter_timing_gate(unsigned card,const std::filesystem::path& output){
 Runner runner(card);try{runner.initialize();size_t retained=runner.owned.size();std::ofstream events(output/"events.jsonl",std::ios::app);std::vector<float> scratch(64ull*1024*1024);unsigned checks=0;
 std::vector<std::pair<std::string,Case>> cases;cases.emplace_back("streams",make_flat(true));cases.emplace_back("ple.add",make_flat(false));
 for(auto label:{"attn.combine","ffn.combine"}){auto c=make_case(0);c.sites.resize(1);c.outputs.clear();for(auto id:c.sites[0].ids){}c.outputs.insert(c.sites[0].ids[c.sites[0].spec.ni]);c.outputs.insert(c.error);cases.emplace_back(label,std::move(c));}
 {auto c=make_case(3);cases.emplace_back("route",c);cases.back().second.sites.resize(1);auto& route=cases.back().second;route.outputs={route.rank_ids,route.rank_prob,route.error};
  auto gather=c;gather.sites.erase(gather.sites.begin());View ids{gather.buffers[gather.rank_ids].data.data(),10,Scalar::i32};for(int j=0;j<10;++j)ids.put(j,j);gather.outputs={gather.rank_gate,gather.rank_down,gather.sites[0].ids[gather.sites[0].spec.ni+2],gather.error};cases.emplace_back("gather",std::move(gather));}
 {Case c;int input=c.add(153600),out=c.add(1,Scalar::i32,0,0);c.sites={c.site(Op::argmax,{input},{out,c.error})};c.outputs.insert(c.error);cases.emplace_back("argmax",std::move(c));}
 for(auto label:{"attn.combine+norm","ffn.combine+norm"}){auto c=make_case(0);c.sites.resize(2);c.outputs.clear();c.outputs.insert(c.sites[0].ids[c.sites[0].spec.ni]);c.outputs.insert(c.sites[1].ids[c.sites[1].spec.ni]);c.outputs.insert(c.error);fold_pair(c);cases.emplace_back(label,std::move(c));}
 {auto c=make_case(3);fold_pair(c);cases.emplace_back("route+gather",std::move(c));}
 for(auto& [label,c]:cases){auto host=c.buffers;for(auto& site:c.sites){std::vector<void*> ptr;for(auto id:site.ids)ptr.push_back(host[id].data.data());ptr.insert(ptr.end(),{scratch.data(),host[c.error].data.data(),host[c.position].data.data(),host[c.active].data.data(),host[c.rope].data.data()});integrated::evaluate(site.spec,ptr.data());}
  for(unsigned repeat=0;repeat<200;++repeat)for(int version:{0,1}){std::vector<Allocation> allocated;for(auto& b:c.buffers)allocated.push_back(runner.upload(b.data));runner.events=&events;runner.klass=label;runner.variant=version?"specialised":"packet18";runner.repetition=repeat;
   for(auto site:(version&&!c.new_sites.empty()?c.new_sites:c.sites)){site.spec.implementation=version;runner.finish(packet18::submit_parallel(runner.d,site.spec,runner.binding(site,c,allocated),runner.control,runner.score,runner.probability));}runner.events=nullptr;
   for(int id:c.outputs)if(runner.get(allocated[id],host[id].data.size())!=host[id].data)throw std::runtime_error("K2 actual adapter mismatch: "+label);
   runner.d.retire_completed_events();while(runner.owned.size()>retained){runner.d.arena.release(runner.owned.back());runner.owned.pop_back();}++checks;
  }
 }
 auto state=runner.d.shutdown(std::chrono::seconds(60));if(!state.safe_to_exit||state.exit_code)throw std::runtime_error("adapter timing teardown");return {checks,runner.max,state.json()};
 }catch(const std::exception& e){std::ofstream(output/"adapter-failure.json")<<"{\"passed\":false,\"error\":"<<ownrt::quote(e.what())<<"}\n";packet26::failure(runner.d,output,e.what());throw;}}
