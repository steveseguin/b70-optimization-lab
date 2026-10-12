#pragma once
#include <poll.h>
#include <functional>
#include <sys/mman.h>
#include <sys/socket.h>
#include <fcntl.h>
#include <cerrno>
// Wire ABI is little-endian, fixed-width on the admitted Linux x86_64 host.
namespace pipeline {
constexpr size_t slot_bytes=65536, shared_bytes=2*slot_bytes+4096;
enum Command:int32_t { half=1, accept=2, rollback=3, dump=4, finish=5, canary=6, fail=7, stall=8, draft=9 };
struct Request { int32_t op,token,position,fixture,speculative,sequence, reserved[2]; };
struct Reply { int32_t status,token,error,bytes,sequence,rank,reserved[2]; double busy_ms,gpu_ms,redo_ms,reserved_ms; };
static_assert(sizeof(Request)==32 && sizeof(Reply)==64);
// Reserved MTP wire fields at offset 2*slot_bytes: valid, position, token,
// provider error, then provider elapsed ns. Provider runs on rank1 before HALF.
static void transfer(int fd,void* ptr,size_t n,bool send,int seconds) {
 auto end=std::chrono::steady_clock::now()+std::chrono::seconds(seconds);
 size_t done=0;
 while(done<n) {
  pipeline_cancel_check();
  auto left=std::chrono::duration_cast<std::chrono::milliseconds>(end-std::chrono::steady_clock::now()).count();
  require(left>0,"bounded channel timeout");
  pollfd fds[2]={{fd,short(send?POLLOUT:POLLIN),0},{pipeline_stop_fd,POLLIN,0}};
  int rc=::poll(fds,pipeline_stop_fd>=0?2:1,int(std::min<int64_t>(left,100)));
  if(rc<0&&errno==EINTR)continue;
  require(rc>=0,"channel poll failed");pipeline_cancel_check();if(!rc)continue;
  require(!(fds[0].revents&(POLLERR|POLLNVAL)),"channel failure");
  if(!(fds[0].revents&(send?POLLOUT:POLLIN))) {require(!(fds[0].revents&POLLHUP),"channel EOF");continue;}
  auto count=send?::send(fd,static_cast<char*>(ptr)+done,n-done,MSG_NOSIGNAL|MSG_DONTWAIT):
                  ::recv(fd,static_cast<char*>(ptr)+done,n-done,MSG_DONTWAIT);
  if(count<0&&(errno==EAGAIN||errno==EINTR))continue;
  require(count>0,"short/closed channel");done+=size_t(count);
 }
}
static flash::Plan split(flash::Plan p,int rank,bool mini) {
 const int boundary=mini?2:24;
 std::vector<flash::Launch> launches;
 for(auto l:p.launches) {
  if(l.op=="handoff"||l.op=="handoff_result")throw std::logic_error("split requires flattened local plan");
  bool keep=l.op=="begin"||l.op=="commit";
  if(l.label.starts_with("blk."))keep=(std::stoi(l.label.substr(4))<boundary)==(rank==0);
  else if(l.op!="begin"&&l.op!="commit")keep=(l.label=="embedding"||l.label=="streams")?(rank==0):(rank==1);
  if(keep){l.card=0;l.source_card=-1;launches.push_back(std::move(l));}
 }
 p.launches=std::move(launches);
 std::set<std::string> used{"streams","token","position","active","error","next_token"};
 for(auto& l:p.launches){used.insert(l.inputs.begin(),l.inputs.end());used.insert(l.outputs.begin(),l.outputs.end());}
 std::erase_if(p.buffers,[&](auto& b){return !used.count(b.name);});
 for(auto& b:p.buffers)b.card=0;
 return p;
}
static std::string strings(const std::vector<std::string>& values) {
 std::string out="[";for(auto& v:values){if(out.size()>1)out+=",";out+=ownrt::quote(v);}return out+"]";
}
static void dump_plan(const fs::path& path,const flash::Plan& p) {
 std::ostringstream o;o<<"{\"buffers\":[";bool comma=false;
 for(auto& b:p.buffers){o<<(comma?",":"")<<"{\"name\":"<<ownrt::quote(b.name)<<",\"bytes\":"<<count(b.shape)*flash::scalar_bytes(b.type)<<"}";comma=true;}
 o<<"],\"launches\":[";comma=false;
 for(auto& l:p.launches){o<<(comma?",":"")<<"{\"label\":"<<ownrt::quote(l.label)<<",\"op\":"<<ownrt::quote(l.op)<<",\"inputs\":"<<strings(l.inputs)<<",\"outputs\":"<<strings(l.outputs)<<"}";comma=true;}
 o<<"]}";save(path,o.str());
}
// Discover bankable temporal state from the executed plan, not name suffixes.
static void banks(Engine& e) {
 for(const auto& l:e.p.launches)if(l.op=="gdn"||l.op=="conv") {
  require(l.outputs.size()==2,"temporal output count");auto name=l.outputs[1];
  require(std::find(l.inputs.begin(),l.inputs.end(),name)!=l.inputs.end(),"temporal input absent");
  auto slot=e.buffers[0].at(name);require(!e.state_spares.count(name),"multiple state writers");
  e.state_spares[name]=e.allocate(0,"alternate:"+name,slot.n*flash::scalar_bytes(slot.type),Category::recurrent,Lifetime::request);
  size_t bytes=slot.n*flash::scalar_bytes(slot.type);std::vector<uint8_t> zero(std::min(bytes,size_t(4194304)),0);
  for(size_t off=0;off<bytes;off+=zero.size())e.upload(0,e.state_spares[name],off,zero.data(),std::min(zero.size(),bytes-off));
 }
 e.prepare_plan();e.prepare_commands();
 if(e.a.memory=="resident") {
  e.swap_state_banks();e.prepare_plan();e.prepare_commands();e.swap_state_banks();
 }
}
// Separate from the draft publication and native mailbox. The target rank is
// its only writer. No guessed token can publish this confirmation. The release
// sequence is position+1, so cleared shared memory cannot impersonate position 0.
struct Verification {alignas(4) uint32_t position_plus_one;int32_t token;};
static Verification& verification(uint8_t* shared){return *reinterpret_cast<Verification*>(shared+2*slot_bytes+128);}

struct Candidate {
 bool pending=false,speculative=false,swapped=false,cancelled=false;int position=0,fixture=0;
 int64_t h0=0,h1=0;std::vector<uint8_t> token_history;
 std::map<int,std::vector<uint8_t>> layers;
};
static void publish(Engine& e,const Candidate& c) {
 require(!c.cancelled,"cannot publish cancelled speculative candidate");
 if(!e.a.retain_steps.contains(c.fixture))return;
 fs::path dest=e.a.output/("step"+std::to_string(c.fixture));fs::create_directories(dest);
 for(auto& [layer,bytes]:c.layers){char name[40];std::snprintf(name,sizeof name,"layer-%02d.bf16",layer);
  if(!e.a.oracle.empty()){std::ifstream f(e.a.oracle/("step"+std::to_string(c.fixture))/name,std::ios::binary);
   require(bool(f),"oracle fixture missing");std::vector<uint8_t> expected((std::istreambuf_iterator<char>(f)),{});
   require(bytes==expected,"oracle fixture differs at "+std::string(name));}
  std::ofstream f(dest/name,std::ios::binary);f.write(reinterpret_cast<const char*>(bytes.data()),bytes.size());require(bool(f),"fixture write");
 }
}
static Reply half_step(Engine& e,Candidate& candidate,const Request& request,uint8_t* shared,bool prepared_inputs=false) {
 require(!candidate.pending,"half before resolving prior candidate");
 require(request.position>=0&&request.position<e.p.g.context,"half position bound");
 if(!prepared_inputs)require(e.integer(0,"position")==request.position,"position sequence mismatch");
 require(!prepared_inputs||e.a.rank==1,"prepared half inputs rank ownership");
 require(request.token>=0&&request.token<e.p.g.vocab,"half token bound");
 require(e.a.rank==0||!request.speculative,"rank1 must never speculate");
 e.verify_configuration();e.guard();
 struct rusage before{},after{},thread_before{},thread_after{};getrusage(RUSAGE_SELF,&before);getrusage(RUSAGE_THREAD,&thread_before);
 auto waits=e.host_waits;double waited=e.wait_ms;e.family_ms.fill(0);
 auto start=std::chrono::steady_clock::now();double gpu=e.gemv_ms+e.nongemv_ms;
 candidate={};candidate.pending=true;candidate.position=request.position;candidate.fixture=request.fixture;candidate.speculative=request.speculative;
 if(e.a.rank==0){candidate.h0=e.history0;candidate.h1=e.history1;
  if(e.buffers[0].count("token_history"))candidate.token_history=e.readback(0,e.buffers[0].at("token_history").id,16);}
 auto prepare_start=std::chrono::steady_clock::now();
 if(!prepared_inputs)e.put(0,"token",&request.token,4);
 if(e.a.rank==0)e.prepare_token(request.token);
 else if(!prepared_inputs){size_t n=4*e.p.g.h*2;require(n<=slot_bytes,"shared stream extent");e.put(0,"streams",shared+slot_bytes,n);}
 double prepare_ms=Engine::ms(prepare_start);auto enqueue_start=std::chrono::steady_clock::now();double enqueue_wait=e.wait_ms;
 std::array<int,48> captured{};size_t captured_count=0,issued=0;
 auto cancel_at_boundary=[&](){
  if(!request.speculative)return false;
  if(e.a.cancel_launch>=0)return issued==size_t(e.a.cancel_launch);
  auto& confirmed=verification(shared);
  bool miss=__atomic_load_n(&confirmed.position_plus_one,__ATOMIC_ACQUIRE)==uint32_t(request.position)&&confirmed.token!=request.token;
  return miss;
 };
 struct CancelledLaunch {};
 require(!e.dev(0).before_compute&&!e.dev(0).after_compute,"nested half launch observers");
 e.dev(0).before_compute=[&](){if(cancel_at_boundary())throw CancelledLaunch{};};
 // A multi-pass legacy site may be cancelled before finish() sees its last
 // event. Record each actual submission so drain still covers its whole prefix.
 e.dev(0).after_compute=[&](ownrt::Event event){e.tail=event;++issued;};
 try {for(auto& l:e.p.launches) {
  if(cancel_at_boundary()){candidate.cancelled=true;break;}
  const auto* ready=e.prepared_path?&e.issue_sites[size_t(&l-e.p.launches.data())]:nullptr;
  if(request.fixture==0&&(ready?ready->prefill_skip:(l.label.starts_with("final.")||l.label=="logits"||l.label=="argmax")))continue;
  if(e.progress_callback)e.progress_callback();
  e.enqueue(l,e.logical);
  if(e.progress_callback)e.progress_callback();
  if(ready?ready->layer_end:ends(l.label,".ffn.combine")) {
   int layer=ready?ready->layer:std::stoi(l.label.substr(4));
   if(e.a.retain_steps.contains(request.fixture)){ownrt::CopyEngine copy(e.dev(0));e.tail=copy.copy(e.snapshots[0],size_t(layer)*4*e.p.g.h*2,e.buffers[0].at("streams").id,0,4*e.p.g.h*2,{});captured.at(captured_count++)=layer;}
   if(!e.resident){e.release_layer(0);e.loaded_layer[0]=-1;}
  }
 }}catch(const CancelledLaunch&){candidate.cancelled=true;}
 catch(...){e.dev(0).before_compute={};e.dev(0).after_compute={};throw;}
 e.dev(0).before_compute={};e.dev(0).after_compute={};
 if(cancel_at_boundary())candidate.cancelled=true;
 double enqueue_ms=Engine::ms(enqueue_start)-(e.wait_ms-enqueue_wait);
 e.drain();int error=e.integer(0,"error");require(!error,"sticky rank error (never rolled back)");
 if(e.a.rank==0&&!candidate.cancelled){e.swap_state_banks();candidate.swapped=true;}
 if(captured_count){auto raw=e.readback(0,e.snapshots[0],48*4*e.p.g.h*2);for(size_t ci=0;ci<captured_count;++ci){int layer=captured[ci];size_t n=4*e.p.g.h*2;candidate.layers[layer]={raw.begin()+layer*n,raw.begin()+(layer+1)*n};}}
 if(captured_count){std::vector<uint8_t> zero(48*4*e.p.g.h*2,0);e.upload(0,e.snapshots[0],0,zero.data(),zero.size());}
 int token=-1;size_t bytes=0;
 if(e.a.rank==0){bytes=4*e.p.g.h*2;auto raw=e.readback(0,e.buffers[0].at("streams").id,bytes);std::memcpy(shared,raw.data(),bytes);}
 else if(request.fixture>0){token=e.integer(0,"next_token");auto& confirmed=verification(shared);confirmed.token=token;__atomic_store_n(&confirmed.position_plus_one,uint32_t(request.position+1),__ATOMIC_RELEASE);}
 if(!e.resident){e.release_layer(0);e.loaded_layer[0]=-1;}
 getrusage(RUSAGE_SELF,&after);getrusage(RUSAGE_THREAD,&thread_after);
 double load_average=0;getloadavg(&load_average,1);cpu_set_t affinity;CPU_ZERO(&affinity);require(!sched_getaffinity(0,sizeof affinity,&affinity),"per-half affinity");
 e.timings<<"{\"cpu_affinity\":[";bool comma=false;for(int cpu=0;cpu<CPU_SETSIZE;++cpu)if(CPU_ISSET(cpu,&affinity)){e.timings<<(comma?",":"")<<cpu;comma=true;}e.timings<<"],\"load_average_1m\":"<<load_average<<",\"position\":"<<request.position<<",\"fixture\":"<<request.fixture<<",\"speculative\":"<<(request.speculative?"true":"false")
  <<",\"cancelled\":"<<(candidate.cancelled?"true":"false")<<",\"launches_issued\":"<<issued
  <<",\"prepare_ms\":"<<prepare_ms<<",\"enqueue_loop_ms\":"<<enqueue_ms<<",\"wait_ms\":"<<e.wait_ms-waited<<",\"host_waits\":"<<e.host_waits-waits
  <<",\"process_major_faults\":"<<after.ru_majflt-before.ru_majflt<<",\"process_minor_faults\":"<<after.ru_minflt-before.ru_minflt<<",\"process_voluntary_context_switches\":"<<after.ru_nvcsw-before.ru_nvcsw<<",\"process_involuntary_context_switches\":"<<after.ru_nivcsw-before.ru_nivcsw
  <<",\"thread_voluntary_context_switches\":"<<thread_after.ru_nvcsw-thread_before.ru_nvcsw<<",\"thread_involuntary_context_switches\":"<<thread_after.ru_nivcsw-thread_before.ru_nivcsw
  <<",\"parity_argument_checks\":"<<e.parity_argument_checks<<",\"enqueue_family_ms\":";
 if(!e.class_timing)e.timings<<"null";else {e.timings<<'{';for(size_t j=0;j<e.families.size();++j)e.timings<<(j?",":"")<<ownrt::quote(e.families[j])<<':'<<e.family_ms[j];e.timings<<'}';}e.timings<<"}\n";
 return {0,token,error,int32_t(bytes),request.sequence,e.a.rank,{int32_t(candidate.cancelled),int32_t(issued)},Engine::ms(start),e.gemv_ms+e.nongemv_ms-gpu,0,0};
}
static void undo(Engine& e,Candidate& c) {
 require(e.a.rank==0&&c.pending&&c.speculative,"rollback outside rank0 speculation");
 e.drain();require(!e.integer(0,"error"),"sticky error cannot be rolled back");
 if(c.swapped)e.swap_state_banks();e.history0=c.h0;e.history1=c.h1;
 if(!c.token_history.empty())e.put(0,"token_history",c.token_history.data(),c.token_history.size());
 e.put(0,"position",&c.position,4);e.lookup_ids.clear();e.fp32_sources[0]=0;e.fp32_extents[0]=0;c={};
}
static void state_dump(Engine& e,int sequence) {
 std::ostringstream o;o<<"{\"history0\":"<<e.history0<<",\"history1\":"<<e.history1<<",\"buffers\":{";bool comma=false;
 fs::path dir=e.a.output/("state-"+std::to_string(sequence));fs::create_directories(dir);
 // Full bytes of every plan allocation, including overwrite-only intermediates.
 for(auto& [name,s]:e.buffers[0]){auto b=e.readback(0,s.id,s.n*flash::scalar_bytes(s.type));std::ofstream f(dir/(name+".bin"),std::ios::binary);f.write(reinterpret_cast<char*>(b.data()),b.size());
  o<<(comma?",":"")<<ownrt::quote(name)<<":"<<ownrt::quote(hash(b));comma=true;}
 for(auto& [name,id]:e.state_spares){auto b=e.readback(0,id,e.dev(0).arena.row(id).bytes);std::ofstream f(dir/("alternate-"+name+".bin"),std::ios::binary);f.write(reinterpret_cast<char*>(b.data()),b.size());o<<","<<ownrt::quote("alternate:"+name)<<":"<<ownrt::quote(hash(b));}
 o<<"},\"fp32_cache_valid\":"<<(e.fp32_sources[0]?"true":"false")<<",\"fp32_extent\":"<<e.fp32_extents[0]<<"}";save(dir/"state.json",o.str());
}
} // namespace pipeline
static void pipeline_cancel_check() {
 if(pipeline_stop_fd<0)return;
 pollfd fd{pipeline_stop_fd,POLLIN,0};int rc=::poll(&fd,1,0);
 require(rc>=0||errno==EINTR,"stop channel poll failed");
 require(!stopped && !(fd.revents&(POLLIN|POLLHUP|POLLERR|POLLNVAL)),"cooperative rank stop");
}
#include "rank_canary.hpp"
#include "request_reset.hpp"
#include "native_controller.hpp"
static int run_rank(const Options& a) {
 using namespace pipeline;
 std::unique_ptr<Weights> weights;std::unique_ptr<Engine> engine;std::unique_ptr<mtp36::DraftRuntime> provider;
 int fd=-1;void* mapping=MAP_FAILED;std::string error;std::vector<std::string> teardown;
 pipeline_stop_fd=a.stop_fd;
 try {
  require(a.channel>=0&&a.stop_fd>=0&&!a.shared.empty(),"rank IPC arguments required");
  fd=::open(a.shared.c_str(),O_RDWR|O_NOFOLLOW);require(fd>=0,"shared open");struct stat st{};
  require(!fstat(fd,&st)&&st.st_size==shared_bytes,"shared extent");mapping=mmap(nullptr,shared_bytes,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);require(mapping!=MAP_FAILED,"shared mmap");
  if(a.pipeline_canary){int rc=run_pipe_canary(a,static_cast<uint8_t*>(mapping));munmap(mapping,shared_bytes);::close(fd);return rc;}
  weights=std::make_unique<Weights>(a);auto p=split(plan(*weights,a),a.rank,a.mini);
  dump_plan(a.output/"launch-plan.json",p);write_plan(a.output/"plan.json",p,*weights,1,a);
  engine=std::make_unique<Engine>(*weights,a,p);record_host_memory(a.output,"before_load");engine->initialize();
  if(a.rank==0)banks(*engine);else {engine->prepare_plan();engine->prepare_commands();}
#ifndef OWN_RT_HOST_ONLY
  if(a.rank==0)weights->warm_lookups();
#endif
  save(a.output/"lookup-residency.json",weights->residency);
  {cpu_set_t cpus;CPU_ZERO(&cpus);require(!sched_getaffinity(0,sizeof cpus,&cpus),"affinity receipt");double load=0;getloadavg(&load,1);std::ostringstream o;o<<"{\"cpu_affinity\":[";bool comma=false;for(int i=0;i<CPU_SETSIZE;++i)if(CPU_ISSET(i,&cpus)){o<<(comma?",":"")<<i;comma=true;}o<<"],\"load_average_1m\":"<<load<<"}";save(a.output/"host-environment.json",o.str());}
  record_host_memory(a.output,"after_load");
  if(a.mtp&&a.rank==1)provider=std::make_unique<mtp36::DraftRuntime>(*engine);
  save(a.output/"census.json",engine->dev(0).arena.census());
  Reply ready{};ready.rank=a.rank;transfer(a.channel,&ready,sizeof ready,true,a.seconds);
  Candidate c;int sequence=0,accepted=0;bool async_half_ready=false;int async_half_position=-1,async_half_token=-1;
  auto execute=[&](const Request& r)->Reply {
   auto received=std::chrono::steady_clock::now();
   Reply response{};response.sequence=r.sequence;response.rank=a.rank;
   if(r.op==draft){
    require(a.rank==1&&provider&&!c.pending&&r.position>0,"draft command ownership/confirmation");
    require(engine->integer(0,"position")==r.position,"draft target not confirmed");
    auto before=std::chrono::steady_clock::now();double gpu=engine->gemv_ms+engine->nongemv_ms;
    struct Publication{int32_t valid,position,token,error;uint64_t elapsed_ns;int32_t sequence,reserved;double gpu_ms;};static_assert(sizeof(Publication)==40);
    auto publish_draft=[&,r](int token,double wall_ms,double gpu_ms){
     Publication v{int32_t(token>=0&&token<engine->p.g.vocab),r.position+1,token,int32_t(token<0&&r.fixture!=0),uint64_t(wall_ms*1e6),r.sequence,0,gpu_ms};
     std::memcpy(static_cast<uint8_t*>(mapping)+2*slot_bytes,&v,sizeof v);
     if(r.speculative){auto& mailbox=*reinterpret_cast<native38::Mailbox*>(static_cast<uint8_t*>(mapping)+2*slot_bytes+256);native38::publish(mailbox.draft_sequence,uint32_t(r.sequence));}
    };
    if(r.speculative){
     require(!async_half_ready,"duplicate asynchronous draft");
     async_half_ready=true;async_half_position=r.position;async_half_token=r.token;
     if(provider->begin(r.token,r.position,r.fixture!=0)){
      engine->progress_callback=[&,publish_draft](){if(auto completed=provider->poll_result())publish_draft(completed->token,completed->wall_ms,completed->gpu_ms);};
     }else {engine->progress_callback={};publish_draft(-1,Engine::ms(before),0);}
    }else {int token=provider->run(r.token,r.position,r.fixture!=0);publish_draft(token,Engine::ms(before),engine->gemv_ms+engine->nongemv_ms-gpu);}
    response.busy_ms=Engine::ms(before);response.gpu_ms=engine->gemv_ms+engine->nongemv_ms-gpu;
   }
   else if(r.op==half){
    bool prepared_inputs=async_half_ready;
    if(prepared_inputs){require(r.position==async_half_position&&r.token==async_half_token,"asynchronous draft/half confirmed identity");provider->queue_half_inputs(r.token,static_cast<uint8_t*>(mapping)+slot_bytes);async_half_ready=false;}
    response=half_step(*engine,c,r,static_cast<uint8_t*>(mapping),prepared_inputs);
   }
   else if(r.op==pipeline::accept){require(c.pending,"accept without candidate");publish(*engine,c);if(c.fixture>0)++accepted;c={};}
   else if(r.op==rollback)undo(*engine,c);
   else if(r.op==dump){require(!c.pending,"dump uncommitted state");state_dump(*engine,r.position);if(r.position==2147483647)request_state_inventory(*engine);}
   else if(r.op==11){request_reset(*engine,c,provider.get(),a.output/("reset-"+std::to_string(r.sequence)+".txt"),accepted);accepted=0;}
   else if(r.op==fail)throw std::runtime_error("injected rank failure");
   else if(r.op==stall){auto until=std::chrono::steady_clock::now()+std::chrono::seconds(a.seconds);while(std::chrono::steady_clock::now()<until){pipeline_cancel_check();poll(nullptr,0,10);}throw std::runtime_error("bounded injected stall");}
   else throw std::runtime_error("unknown rank command");
   response.redo_ms=std::chrono::duration<double>(received.time_since_epoch()).count();
   response.reserved_ms=std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
   return response;
  };
  for(;;){Request r{};transfer(a.channel,&r,sizeof r,false,a.seconds);require(r.sequence==++sequence,"command sequence");
   if(r.op==finish){require(!c.pending,"finish with unresolved candidate");if(provider)provider->dump(engine->a.output/"draft-final-state");break;}
   Reply response{};
   if(r.op==10){
    require(!c.pending,"native entry unresolved candidate");
    auto* bytes=static_cast<uint8_t*>(mapping);auto& mailbox=*reinterpret_cast<native38::Mailbox*>(bytes+2*slot_bytes+256);
    auto cancel=[&](){pipeline_cancel_check();if(engine->progress_callback)engine->progress_callback();};
    try {
     if(a.rank==1)native38::worker(mailbox,a.seconds,execute,cancel);
     else {
      auto cfg=native38::config(a.shared.parent_path()/"native-request.txt",engine->p.g.context,engine->p.g.vocab);
      native38::Backend backend(mailbox,bytes,a.seconds,execute,cancel);
      auto result=native38::run(backend,cfg);
      save(a.shared.parent_path()/"native-result.json",native38::json(result,backend,cfg));
     }
    }catch(...){native38::abort(mailbox);throw;}
    response.sequence=r.sequence;response.rank=a.rank;
   }else response=execute(r);
   transfer(a.channel,&response,sizeof response,true,a.seconds);
  }
  engine->dump_classes(engine->a.output/"class-times.json",accepted);
 }catch(const std::exception& ex){
  error=ex.what();
  // A full filesystem cannot bypass the explicit provider/owner drain below.
  try{save(a.output/"failure.txt",error+"\n");}
  catch(const std::exception& record){error+="; failure record: "+std::string(record.what());std::cerr<<error<<"\n";}
  try{save(a.output/"receipt.json","{\"passed\":false,\"teardown_pending\":true,\"error\":"+ownrt::quote(error)+"}");}
  catch(const std::exception& record){error+="; failure receipt: "+std::string(record.what());std::cerr<<error<<"\n";}
 }
 // Failure receipt is durable before any teardown. Device owns all SYCL borrowers.
 if(engine)engine->progress_callback={};
 provider.reset();
 if(engine){try{teardown=engine->shutdown();}catch(const std::exception& ex){error+=(error.empty()?"":"; ")+std::string(ex.what());}engine.reset();}
 weights.reset();if(mapping!=MAP_FAILED)munmap(mapping,shared_bytes);if(fd>=0)::close(fd);
 std::ostringstream o;o<<"{\"schema\":\"packet32.rank.v1\",\"passed\":"<<(error.empty()?"true":"false")<<",\"rank\":"<<a.rank<<",\"error\":"<<ownrt::quote(error)<<",\"arithmetic\":"<<ownrt::quote(arithmetic::version)<<",\"device_executed\":"
#ifdef OWN_RT_HOST_ONLY
 <<"false"
#else
 <<"true"
#endif
 <<",\"teardown\":[";for(size_t i=0;i<teardown.size();++i)o<<(i?",":"")<<teardown[i];o<<"]}";save(a.output/"receipt.json",o.str());return error.empty()?0:1;
}
