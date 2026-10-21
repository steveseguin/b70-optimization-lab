#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/native-portable/experiments/own-xpu-runtime/stage2/packet165-warm-prefill/two-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/native-portable/experiments/own-xpu-runtime/stage2/packet165-warm-prefill/two-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/p105_runtime.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/native-portable/experiments/own-xpu-runtime/stage2/packet165-warm-prefill/two-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/build/checked/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/round2_submit.hpp"
namespace p105 {
// Private auxiliary state. Never inserted in target/draft buffers or snapshots.
struct Runtime {
 Engine& e;bool bcs;Allocation hidden=0,logits=0,index=0,error=0,active=0,position=0,workspace=0,best=0,staging=0;
 ownrt::Event export_event=0;uint32_t export_sequence=0;int export_position=-1,export_fixture=-1;std::chrono::steady_clock::time_point export_started;
 std::vector<ownrt::PreparedCompute> suffix_commands;
 std::ofstream timings;
 explicit Runtime(Engine& engine):e(engine),bcs(e.head_choice()=="head-split-bcs"),timings(e.a.output/"p105-transfers.jsonl") {
  require(e.split_head()&&e.p.g.h==2560&&e.p.g.vocab==vocab,"p105 dimensions");
  auto alloc=[&](const char*n,size_t bytes,Memory memory=Memory::device){auto id=e.allocate(0,std::string("p105:")+n,bytes,Category::runtime_overhead,Lifetime::process,memory);e.head_auxiliary.insert(id);return id;};
  best=alloc("best16",16);staging=alloc("staging",hidden_bytes,Memory::pinned);
  if(e.a.rank==0){
   e.load(0,"output.weight");hidden=alloc("verified-final.mix",hidden_bytes);logits=alloc("logits",suffix*2);
   index=alloc("index",4);error=alloc("error",4);active=alloc("active",4);position=alloc("position",4);workspace=alloc("workspace",suffix*32);
   uint32_t zero=0,one=1;for(auto id:{index,error,position})e.upload(0,id,0,&zero,4);e.upload(0,active,0,&one,4);
   integrated::Matrix m{};m.w=e.weights[0].at("output.weight");m.type=iq3::Type::Q6_K;m.x=hidden;m.y=logits;m.rows=m.span=suffix;m.columns=2560;m.workspace=workspace;
   integrated::Spec s;s.op=integrated::Op::argmax;s.ni=1;s.no=1;s.sizes[0]=suffix;s.sizes[1]=1;s.types[0]=flash::Scalar::bf16;s.types[1]=flash::Scalar::i32;
   std::array ids{logits,index,workspace,error,position,active,position};
   e.dev(0).begin_capture(suffix_commands);
   try{p33::submit(e.dev(0),{m},"p33.dense.segment",false,6);round2::submit_simple(e.dev(0),s,ids);pack(e.dev(0),logits,index,error,best,suffix,prefix);e.dev(0).end_capture();}
   catch(...){e.dev(0).end_capture();throw;}
  }else{
   hidden=e.buffers[0].at("final.mix").id;logits=e.buffers[0].at("logits").id;
   index=e.buffers[0].at("next_token").id;error=e.buffers[0].at("error").id;
  }
 }
 void transfer(Allocation dst,Allocation src,size_t n,const char*leg){
  auto start=std::chrono::steady_clock::now();CopyScope scope(bcs);ownrt::CopyEngine copy(e.dev(0));
  auto event=copy.copy(dst,0,src,0,n,{});e.wait(0,event);e.retire_events(0);
  timings<<"{\"leg\":\""<<leg<<"\",\"placement\":\""<<(bcs?"bcs":"compute")<<"\",\"bytes\":"<<n<<",\"host_us\":"<<Engine::ms(start)*1000<<",\"backend\":"<<ownrt::quote(e.dev(0).identity())<<"}\n";
  require(bool(timings),"p105 timing write");
 }
 void export_hidden(Mailbox& box,uint32_t sequence,int pos,int fixture){
  require(e.a.rank==1&&sequence&&fixture>0,"p105 export identity");
  require(!load(box.abort)&&load(box.request)==load(box.reply)&&sequence>load(box.request),"p105 outstanding/stale export");
  require(!export_event,"p105 duplicate hidden export");
  // CopyEngine binds the current final.mix writer event. BCS waits that event
  // on its own queue; the following prefix head only reads the same input.
  export_started=std::chrono::steady_clock::now();CopyScope scope(bcs);ownrt::CopyEngine copy(e.dev(0));
  export_event=copy.copy(staging,0,hidden,0,hidden_bytes,{});
  export_sequence=sequence;export_position=pos;export_fixture=fixture;
 }
 void publish_hidden(Mailbox& box){
  require(e.a.rank==1&&export_event&&!load(box.abort),"p105 hidden publication ownership");
  // Called just after prefix submission. Do not retire events: that head is
  // still running. Both queues are drained by the normal half boundary.
  e.wait(0,export_event);e.guard();require(!load(box.abort),"p105 cancelled hidden export");
  std::memcpy(box.hidden,e.dev(0).arena.row(staging).pointer,hidden_bytes);
  box.position=export_position;box.fixture=export_fixture;publish(box.request,export_sequence);
  timings<<"{\"leg\":\"hidden-export\",\"placement\":\""<<(bcs?"bcs":"compute")<<"\",\"bytes\":5120,\"host_dependency_wait_us\":"<<Engine::ms(export_started)*1000<<",\"prefix_submitted_before_publication\":true,\"backend\":"<<ownrt::quote(e.dev(0).identity())<<"}\n";
  require(bool(timings),"p105 export timing write");export_event=0;
 }
 template<class Cancel> void service(Mailbox& box,uint32_t seq,int pos,int fixture,Cancel cancel){
  require(e.a.rank==0&&seq&&fixture>0,"p105 suffix ownership");
  auto check=[&]{cancel();require(!load(box.abort),"p105 peer failed");};
  require(p56x::wait([&]{return load(box.request)==seq;},check,std::chrono::steady_clock::now()+std::chrono::seconds(e.a.seconds)),"p105 hidden timeout");check();
  require(box.position==pos&&box.fixture==fixture&&load(box.reply)<seq,"p105 stale position/duplicate service");
  e.drain(); // local speculative half has completed; no model-state writes below.
  std::memcpy(e.dev(0).arena.row(staging).pointer,box.hidden,hidden_bytes);
  transfer(hidden,staging,hidden_bytes,"hidden-import");
  uint32_t zero=0,one=1;e.upload(0,error,0,&zero,4);e.upload(0,active,0,&one,4);
  for(const auto& command:suffix_commands)e.tail=e.dev(0).issue(command);
  e.drain();transfer(staging,best,16,"best-export");
  std::memcpy(&box.best,e.dev(0).arena.row(staging).pointer,16);check();publish(box.reply,seq);
 }
 template<class Cancel> void merge_target(Mailbox& box,uint32_t seq,int pos,int fixture,Cancel cancel){
  require(e.a.rank==1&&load(box.request)==seq&&box.position==pos&&box.fixture==fixture,"p105 merge ownership");
  // Pack uses the unchanged prefix argmax and its sticky finite flag.
  e.tail=pack(e.dev(0),logits,index,error,best,prefix,0);e.drain();transfer(staging,best,16,"prefix-export");
  Best local;std::memcpy(&local,e.dev(0).arena.row(staging).pointer,16);
  auto check=[&]{cancel();require(!load(box.abort),"p105 peer failed");};
  require(p56x::wait([&]{return load(box.reply)==seq;},check,std::chrono::steady_clock::now()+std::chrono::seconds(e.a.seconds)),"p105 best timeout");check();
  auto result=merge(local,box.best);
  // Invalid partitions may have diagnostic indices; no nonfinite winner emits.
  if(result.error){e.upload(0,error,0,&result.error,4);throw std::runtime_error("p105 sticky nonfinite target head");}
  e.upload(0,index,0,&result.index,4);
 }
};
}
