#pragma once
// Increment body is identical to packet29 canary; one local queue per process.
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
static int run_pipe_canary(const Options& a,uint8_t* shared) {
 using namespace pipeline;
#ifdef OWN_RT_HOST_ONLY
 ownrt::Device d(std::make_unique<Host>());
#else
 ownrt::Device d(ownrt::make_sycl_device(a.card,true));
#endif
 std::string error;int iterations=0;double maximum_ns=0,total_ns=0;
 try { // Copy/operation borrowers leave this scope before shutdown.
  auto local=d.arena.allocate("card0:canary",256,Memory::device,Category::scratch,Lifetime::transaction);
  auto host=d.arena.allocate("canary-host",256,Memory::pinned,Category::pinned_slab,Lifetime::transfer);
  ownrt::CopyEngine copy(d,4096,1);auto hp=d.arena.row(host).pointer;
  auto drain=[&](ownrt::Event event){require(d.wait(event,std::chrono::seconds(5)),"canary drain bound");};
  Reply ready{};ready.rank=a.rank;transfer(a.channel,&ready,sizeof ready,true,a.seconds);int sequence=0;
  for(;;){Request r{};transfer(a.channel,&r,sizeof r,false,a.seconds);require(r.sequence==++sequence,"canary sequence");
   if(r.op==finish){require(iterations==1000,"canary requires 1000 handovers");break;}
   require(r.op==canary&&r.position==iterations,"canary command/order");auto start=std::chrono::steady_clock::now();
   std::memcpy(hp,shared+a.rank*slot_bytes,256);for(int i=0;i<64;++i)require(static_cast<uint32_t*>(hp)[i]==unsigned(iterations),"canary input bytes");
   drain(copy.copy(local,0,host,0,256,{}));std::array<Allocation,1> args{local};auto event=d.compute(CanaryIncrement{},args,{});drain(event);
#ifndef OWN_RT_HOST_ONLY
   auto timing=d.timing(event);require(timing.start_ns&&timing.end_ns>=timing.start_ns,"canary profiling");
   double ns=timing.end_ns-timing.start_ns;maximum_ns=std::max(maximum_ns,ns);total_ns+=ns;require(ns<100000000,"canary submission budget");
#endif
   drain(copy.copy(host,0,local,0,256,{}));d.retire_completed_events();++iterations;
   for(int i=0;i<64;++i)require(static_cast<uint32_t*>(hp)[i]==unsigned(iterations),"canary output bytes");
   std::memcpy(shared+a.rank*slot_bytes,hp,256);
   Reply reply{0,iterations,0,256,r.sequence,a.rank,{0,0},Engine::ms(start),0,
    std::chrono::duration<double>(start.time_since_epoch()).count(),std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count()};
   transfer(a.channel,&reply,sizeof reply,true,a.seconds);
  }
 }catch(const std::exception& ex){error=ex.what();save(a.output/"receipt.json","{\"passed\":false,\"teardown_pending\":true,\"error\":"+ownrt::quote(error)+"}");}
 auto receipt=d.shutdown(std::chrono::seconds(60));save(a.output/"teardown.json",receipt.json());
 if(!receipt.safe_to_exit){save(a.output/"retained-owner.json",receipt.json());ownrt::hold_for_supervisor();}
 std::ostringstream o;o<<"{\"schema\":\"packet32.canary-rank.v1\",\"passed\":"<<(error.empty()&&receipt.exit_code==0?"true":"false")
 <<",\"rank\":"<<a.rank<<",\"kernels\":"<<iterations<<",\"handovers\":"<<iterations<<",\"device_bytes\":256,\"host_pinned_bytes\":256,\"max_submission_ns\":"<<maximum_ns<<",\"gpu_ms\":"<<total_ns/1e6
 <<",\"error\":"<<ownrt::quote(error)<<",\"teardown\":["<<receipt.json()<<"]}";save(a.output/"receipt.json",o.str());return error.empty()&&receipt.exit_code==0?0:1;
}
