#pragma once
#include <poll.h>
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
 e.prepare_plan();
 if(e.a.memory=="resident") {
  e.swap_state_banks();e.prepare_plan();e.swap_state_banks();
 }
}
struct Candidate {
 bool pending=false,speculative=false;int position=0,fixture=0;
 int64_t h0=0,h1=0;std::vector<uint8_t> token_history;
 std::map<int,std::vector<uint8_t>> layers;
};
static void publish(Engine& e,const Candidate& c) {
 if(c.fixture<1||c.fixture>8)return;
 fs::path dest=e.a.output/("step"+std::to_string(c.fixture));fs::create_directories(dest);
 for(auto& [layer,bytes]:c.layers){char name[40];std::snprintf(name,sizeof name,"layer-%02d.bf16",layer);
  if(!e.a.oracle.empty()){std::ifstream f(e.a.oracle/("step"+std::to_string(c.fixture))/name,std::ios::binary);
   require(bool(f),"oracle fixture missing");std::vector<uint8_t> expected((std::istreambuf_iterator<char>(f)),{});
   require(bytes==expected,"oracle fixture differs at "+std::string(name));}
  std::ofstream f(dest/name,std::ios::binary);f.write(reinterpret_cast<const char*>(bytes.data()),bytes.size());require(bool(f),"fixture write");
 }
}
static Reply half_step(Engine& e,Candidate& candidate,const Request& request,uint8_t* shared) {
 require(!candidate.pending,"half before resolving prior candidate");
 require(request.position>=0&&request.position<e.p.g.context,"half position bound");
 require(e.integer(0,"position")==request.position,"position sequence mismatch");
 require(request.token>=0&&request.token<e.p.g.vocab,"half token bound");
 require(e.a.rank==0||!request.speculative,"rank1 must never speculate");
 auto start=std::chrono::steady_clock::now();double gpu=e.gemv_ms+e.nongemv_ms;
 candidate={};candidate.pending=true;candidate.position=request.position;candidate.fixture=request.fixture;candidate.speculative=request.speculative;
 if(e.a.rank==0){candidate.h0=e.history0;candidate.h1=e.history1;
  if(e.buffers[0].count("token_history"))candidate.token_history=e.readback(0,e.buffers[0].at("token_history").id,16);}
 e.put(0,"token",&request.token,4);
 if(e.a.rank==0)e.prepare_token(request.token);
 else {size_t n=4*e.p.g.h*2;require(n<=slot_bytes,"shared stream extent");e.put(0,"streams",shared+slot_bytes,n);}
 std::vector<int> captured;
 for(auto& l:e.p.launches) {
  if(request.fixture==0&&(l.label.starts_with("final.")||l.label=="logits"||l.label=="argmax"))continue;
  e.enqueue(l,e.logical);
  if(ends(l.label,".ffn.combine")) {
   int layer=std::stoi(l.label.substr(4));
   if(request.fixture>0&&request.fixture<=8){ownrt::CopyEngine copy(e.dev(0));e.tail=copy.copy(e.snapshots[0],size_t(layer)*4*e.p.g.h*2,e.buffers[0].at("streams").id,0,4*e.p.g.h*2,{});captured.push_back(layer);}
   if(e.a.memory=="layer-streaming"){e.release_layer(0);e.loaded_layer[0]=-1;}
  }
 }
 e.drain();int error=e.integer(0,"error");require(!error,"sticky rank error (never rolled back)");
 if(e.a.rank==0)e.swap_state_banks();
 if(!captured.empty()){auto raw=e.readback(0,e.snapshots[0],48*4*e.p.g.h*2);for(int layer:captured){size_t n=4*e.p.g.h*2;candidate.layers[layer]={raw.begin()+layer*n,raw.begin()+(layer+1)*n};}}
 int token=-1;size_t bytes=0;
 if(e.a.rank==0){bytes=4*e.p.g.h*2;auto raw=e.readback(0,e.buffers[0].at("streams").id,bytes);std::memcpy(shared,raw.data(),bytes);}
 else if(request.fixture>0)token=e.integer(0,"next_token");
 if(e.a.memory=="layer-streaming"){e.release_layer(0);e.loaded_layer[0]=-1;}
 return {0,token,error,int32_t(bytes),request.sequence,e.a.rank,{0,0},Engine::ms(start),e.gemv_ms+e.nongemv_ms-gpu,0,0};
}
static void undo(Engine& e,Candidate& c) {
 require(e.a.rank==0&&c.pending&&c.speculative,"rollback outside rank0 speculation");
 e.drain();require(!e.integer(0,"error"),"sticky error cannot be rolled back");
 e.swap_state_banks();e.history0=c.h0;e.history1=c.h1;
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
  if(a.rank==0)banks(*engine);else engine->prepare_plan();record_host_memory(a.output,"after_load");
  if(a.mtp&&a.rank==1)provider=std::make_unique<mtp36::DraftRuntime>(*engine);
  save(a.output/"census.json",engine->dev(0).arena.census());
  Reply ready{};ready.rank=a.rank;transfer(a.channel,&ready,sizeof ready,true,a.seconds);
  Candidate c;int sequence=0,accepted=0;
  for(;;){Request r{};transfer(a.channel,&r,sizeof r,false,a.seconds);require(r.sequence==++sequence,"command sequence");
   auto received=std::chrono::steady_clock::now();
   Reply response{};response.sequence=r.sequence;response.rank=a.rank;
   if(r.op==draft){
    require(a.rank==1&&provider&&!c.pending&&r.position>0,"draft command ownership/confirmation");
    require(engine->integer(0,"position")==r.position,"draft target not confirmed");
    auto before=std::chrono::steady_clock::now();double gpu=engine->gemv_ms+engine->nongemv_ms;
    int token=provider->run(r.token,r.position,r.fixture!=0);
    struct Publication{int32_t valid,position,token,error;uint64_t elapsed_ns;int32_t sequence,reserved;double gpu_ms;};static_assert(sizeof(Publication)==40);
    Publication v{int32_t(token>=0&&token<engine->p.g.vocab),r.position+1,token,int32_t(token<0&&r.fixture!=0),uint64_t(Engine::ms(before)*1e6),r.sequence,0,engine->gemv_ms+engine->nongemv_ms-gpu};
    std::memcpy(static_cast<uint8_t*>(mapping)+2*slot_bytes,&v,sizeof v);
    response.busy_ms=Engine::ms(before);response.gpu_ms=v.gpu_ms;
    // Socket reply publishes the completed shared bytes. Draft never fills Reply.token.
   }
   else if(r.op==half)response=half_step(*engine,c,r,static_cast<uint8_t*>(mapping));
   else if(r.op==pipeline::accept){require(c.pending,"accept without candidate");publish(*engine,c);if(c.fixture>0)++accepted;c={};}
   else if(r.op==rollback)undo(*engine,c);
   else if(r.op==dump){require(!c.pending,"dump uncommitted state");state_dump(*engine,r.position);}
   else if(r.op==finish){require(!c.pending,"finish with unresolved candidate");if(provider)provider->dump(a.output/"draft-final-state");break;}
   else if(r.op==fail)throw std::runtime_error("injected rank failure");
   else if(r.op==stall){auto until=std::chrono::steady_clock::now()+std::chrono::seconds(a.seconds);while(std::chrono::steady_clock::now()<until){pipeline_cancel_check();poll(nullptr,0,10);}throw std::runtime_error("bounded injected stall");}
   else throw std::runtime_error("unknown rank command");
   response.redo_ms=std::chrono::duration<double>(received.time_since_epoch()).count();
   response.reserved_ms=std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
   transfer(a.channel,&response,sizeof response,true,a.seconds);
  }
  engine->dump_classes(a.output/"class-times.json",accepted);
 }catch(const std::exception& ex){error=ex.what();save(a.output/"failure.txt",error+"\n");save(a.output/"receipt.json","{\"passed\":false,\"teardown_pending\":true,\"error\":"+ownrt::quote(error)+"}");}
 // Failure receipt is durable before any teardown. Device owns all SYCL borrowers.
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
