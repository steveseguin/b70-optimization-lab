#include "failure.hpp"
#pragma once
// Weight-free gate using the real owner, shared context, adapter and copy paths.
struct CanaryIncrement final
#ifdef OWN_RT_HOST_ONLY
 : integrated::HostOperation {
 void run(std::span<void*const> p)const override {auto x=static_cast<uint32_t*>(p[0]);for(int i=0;i<64;++i)++x[i];}
#else
 : ownrt::SyclOperation {
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  auto x=static_cast<uint32_t*>(p[0]);return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::range<1>(64),[=](sycl::id<1> i){++x[i];});});
 }
#endif
};
static int run_canary(const Options& a) {
 require(a.cards==2 && a.seconds>=300 && a.seconds<=1800,"canary: two cards and watchdog 300..1800 seconds");
 auto start=std::chrono::steady_clock::now();
#ifdef OWN_RT_HOST_ONLY
 auto backend=std::make_unique<Host>();auto raw=backend.get();auto select=[](int){};
#else
 auto backend=std::make_unique<tp2::Context>(a.card,a.card+1);auto raw=backend.get();
 auto select=[&](int c){raw->allocation_card=c;};
#endif
 ownrt::Device d(std::move(backend));try {
 double startup_jit_ms=0,work_wall_ms=0,max_ns=0,device_ns=0;
 bool submission_budget_passed=true;unsigned waits=0;size_t bytes=0;
 { // All context borrowers unwind before the owner, including on exceptions.
 packet23::Borrower bundle_borrower(d,"canary executable kernel bundle");
 auto compiled=raw->canary_bundle();
 startup_jit_ms=Engine::ms(start);auto work_start=std::chrono::steady_clock::now();
 ownrt::CopyEngine copy(d,4096,1);
 std::array<std::map<std::string,Allocation>,2> b;
 std::vector<ownrt::Event> segment;ownrt::Event tail=0;
 auto guard=[&]{require(!stopped,"canary cooperative stop");};
 auto drain=[&]{if(!tail)return;guard();++waits;require(d.wait(tail,std::chrono::seconds(5)),"canary five-second drain timeout");
#ifndef OWN_RT_HOST_ONLY
  for(auto e:segment){auto t=d.timing(e);require(t.end_ns>=t.start_ns&&t.start_ns,"canary profiling required");max_ns=std::max(max_ns,double(t.end_ns-t.start_ns));device_ns+=double(t.end_ns-t.start_ns);submission_budget_passed &= max_ns<100000000.;}
#endif
  segment.clear();tail=0;d.retire_completed_events();};
 auto save_event=[&](ownrt::Event e){tail=e;segment.push_back(e);};
 for(int c=0;c<2;++c){select(c);for(auto name:{"data","streams","token","position","active","error","next_token","scratch","rope","control","scores","probabilities"}){
  size_t bytes=std::string(name)=="data"||std::string(name)=="streams"?256:16;
  b[c][name]=d.arena.allocate("card"+std::to_string(c)+":"+name,bytes,Memory::device,Category::scratch,Lifetime::transaction);
 }}
 auto host=d.arena.allocate("canary-host",256,Memory::pinned,Category::pinned_slab,Lifetime::transfer);
 auto hp=static_cast<uint32_t*>(d.arena.row(host).pointer);
 for(int c=0;c<2;++c)for(auto [name,id]:b[c]){select(c);std::fill(hp,hp+64,0);if(name=="active")hp[0]=1;if(name=="token")hp[0]=7;save_event(copy.copy(id,0,host,0,d.arena.row(id).bytes,{}));drain();}
 auto increment=[&](int c){guard();select(c);std::array<Allocation,1> args{b[c].at("data")};save_event(d.compute(CanaryIncrement{},args,{}));};
 auto peer=[&](int src,int dst,const std::string& name){drain();select(dst);auto id=b[dst].at(name);save_event(copy.copy(id,0,b[src].at(name),0,d.arena.row(id).bytes,{}));};
 auto verify=[&](int c,const std::string& name,uint32_t value,int n){drain();select(c);save_event(copy.copy(host,0,b[c].at(name),0,n*4,{}));drain();for(int i=0;i<n;++i)require(hp[i]==value,"canary byte mismatch");};
 for(int i=0;i<100;++i){increment(0);drain();peer(0,1,"data");drain();increment(1);drain();peer(1,0,"data");verify(0,"data",2*(i+1),64);}
 auto special=[&](int c,Special op,const std::string& dest="streams"){
  guard();select(c);Spec s{};s.g.context=8;s.g.h=64;s.special=op;
  std::vector<Allocation> args;
  if(op==Special::broadcast){s.ni=1;s.no=1;s.sizes[0]=1;s.sizes[1]=dest=="streams"?64:1;s.types[0]=s.types[1]=flash::Scalar::u32;args={b[c].at("token"),b[c].at(dest)};}
  for(auto name:{"scratch","error","position","active","rope"})args.push_back(b[c].at(name));
  auto launch=packet18::submit_parallel(d,s,args,b[c].at("control"),b[c].at("scores"),b[c].at("probabilities"),{});
  save_event(launch.last);
 };
 // Real token's begin/broadcast/boundary/return/commit order. A broadcast
 // substitutes for half-model arithmetic; no weights or table are loaded.
 special(0,Special::begin);drain();special(1,Special::begin);drain();special(0,Special::broadcast);
 for(auto name:{"streams","token","position","active","error"})peer(0,1,name);
 special(1,Special::broadcast,"next_token");
 for(auto name:{"next_token","error"})peer(1,0,name);
 special(0,Special::commit);drain();special(1,Special::commit);drain();
 verify(0,"position",1,1);verify(1,"position",1,1);
 verify(0,"next_token",7,1);verify(0,"error",0,1);verify(1,"error",0,1);verify(1,"streams",7,64);
 for(int c=0;c<2;++c){for(int i=0;i<1000;++i)increment(c);drain();verify(c,"data",1200,64);}
 bytes=d.arena.total(Memory::device);require(bytes<16*1024*1024,"canary allocation bound");
 work_wall_ms=Engine::ms(work_start);
 } // compiled bundle, copy wrapper and submission captures are now destroyed.
 packet23::row(a.output,"canary completed checks",&waits,sizeof waits,submission_budget_passed);
 auto teardown_start=std::chrono::steady_clock::now();
 auto receipt=d.shutdown(std::chrono::seconds(5));require(receipt.safe_to_exit && receipt.exit_code==0,"canary unsafe teardown");
 double elapsed=Engine::ms(start),teardown_ms=Engine::ms(teardown_start);
 std::ostringstream out;out<<"{\"schema\":\"own-runtime.iq3.packet18.canary.v2\",\"passed\":"<<(submission_budget_passed?"true":"false")<<",\"owner_cards\":2,\"device_executed\":"
#ifdef OWN_RT_HOST_ONLY
 <<"false"
#else
 <<"true"
#endif
 <<",\"startup_jit_ms\":"<<startup_jit_ms<<",\"device_work_ms\":"<<device_ns/1e6<<",\"work_wall_ms\":"<<work_wall_ms<<",\"teardown_ms\":"<<teardown_ms
 <<",\"submission_budget_passed\":"<<(submission_budget_passed?"true":"false")<<",\"total_expectation_ms\":30000,\"total_expectation_exceeded\":"<<(elapsed>=30000?"true":"false")
 <<",\"round_trips\":100,\"kernels_per_card\":1000,\"token_sequence\":true,\"owned_device_bytes\":"<<bytes<<",\"wall_ms\":"<<elapsed<<",\"max_submission_ns\":"<<max_ns<<",\"host_waits\":"<<waits<<",\"teardown\":["<<receipt.json()<<"]}";
 save(a.output/"receipt.json",out.str());return 0;
 }catch(const std::exception& e){packet23::failure(d,a.output,e.what());throw;}
}
