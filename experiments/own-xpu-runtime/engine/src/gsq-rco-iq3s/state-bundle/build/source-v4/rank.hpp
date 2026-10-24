#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#include "gsq-rco-iq3s/integration/build/private/source/diet-native/native-src/strict_snapshot.hpp"
#include <poll.h>
#include <functional>
#include <sys/mman.h>
#include <sys/socket.h>
#include <fcntl.h>
#include <cerrno>
// Wire ABI is little-endian, fixed-width on the admitted Linux x86_64 host.
namespace pipeline {
constexpr size_t slot_bytes=65536, reverse_offset=2*slot_bytes+4096, probe_offset=reverse_offset+slot_bytes, shared_bytes=probe_offset+slot_bytes+64;
static_assert(slot_bytes==65536,"strict snapshot shared slot extent");
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
static flash::Plan split(flash::Plan p,int rank,bool mini,int draft_rank=1,int target_split=0,int rank0_extra=0) {
 require(target_split==0||target_split==23||target_split==24,"unsupported target split");
 require(rank0_extra==0||rank0_extra==2||rank0_extra==3,"packet188 rank-0 extra layer count (0, 2: V3 24-25, 3: k3 24-26)");
 require(!rank0_extra||(target_split==0&&draft_rank==1),"packet186 V3 layout requires the 24/24 base split and the rank-1 draft");
 const int boundary=mini?2:(target_split?target_split:(draft_rank==0?22:24));
 // packet186: rank 0 also holds the GDN layers 24-25 (mini: 2); packet188 k3 storage: 24-26 (mini: 2-3,
 // five-layer pipeline miniature). Rank 1 keeps 24-47 (dual layout).
 const int rank0_end=rank0_extra?boundary+(mini?rank0_extra-1:rank0_extra):boundary;
 std::vector<flash::Launch> launches;
 for(auto l:p.launches) {
  if(l.op=="handoff"||l.op=="handoff_result")throw std::logic_error("split requires flattened local plan");
  bool keep=l.op=="begin"||l.op=="commit";
  if(l.label.starts_with("blk.")){const int layer=std::stoi(l.label.substr(4));keep=rank==0?layer<rank0_end:layer>=boundary;}
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
  if(e.v3_skip_half.at(size_t(&l-e.p.launches.data())))continue; // packet186: layers 24-25 state lives outside the banks and the image
  require(l.outputs.size()==2,"temporal output count");auto name=l.outputs[1];
  require(std::find(l.inputs.begin(),l.inputs.end(),name)!=l.inputs.end(),"temporal input absent");
  auto slot=e.buffers[0].at(name);require(!e.state_spares.count(name),"multiple state writers");
  e.state_spares[name]=e.allocate(0,"alternate:"+name,slot.n*flash::scalar_bytes(slot.type),Category::recurrent,Lifetime::request);
  if(e.miss_banks())e.state_reserves[name]=e.allocate(0,"speculative-reserve:"+name,slot.n*flash::scalar_bytes(slot.type),Category::runtime_overhead,Lifetime::process);
  size_t bytes=slot.n*flash::scalar_bytes(slot.type);std::vector<uint8_t> zero(std::min(bytes,size_t(4194304)),0);
  for(size_t off=0;off<bytes;off+=zero.size()){e.upload(0,e.state_spares[name],off,zero.data(),std::min(zero.size(),bytes-off));if(e.miss_banks())e.upload(0,e.state_reserves[name],off,zero.data(),std::min(zero.size(),bytes-off));}
 }
 e.prepare_plan();e.prepare_commands();
 if(e.miss_banks()) {
  require(e.a.memory=="resident","third banks require resident engine");
  // 01 -> 02 -> 20 -> 21 -> 12 -> 10 -> 01. All six captures happen
  // during load. No per-token whole-plan rebuild or device allocation.
  for(int i=0;i<6;++i){if(i%2==0)e.rotate_spare_bank();else e.swap_state_banks();if(i<5){e.prepare_plan();e.prepare_commands();}}
  require(e.active_bank==0&&e.spare_bank==1,"third bank preparation cycle");
  e.bank_parity=0;e.bank_cache_ready=true;
 }else if(e.a.memory=="resident") {
  e.swap_state_banks();e.prepare_plan();e.prepare_commands();e.swap_state_banks();
 }
}
// Separate from the draft publication and native mailbox. The target rank is
// its only writer. No guessed token can publish this confirmation. The release
// sequence is position+1, so cleared shared memory cannot impersonate position 0.
struct Verification {alignas(4) uint32_t position_plus_one;int32_t token;};
struct ReverseReady {alignas(4) uint32_t position_plus_one;};
static ReverseReady& reverse_ready(uint8_t* shared){return *reinterpret_cast<ReverseReady*>(shared+2*slot_bytes+192);}
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
static Reply half_step(Engine& e,Candidate& candidate,const Request& request,uint8_t* shared,SpeculativeImage& image,bool prepared_inputs=false,bool corrected=false) {
 const auto p150_half_begin=std::chrono::steady_clock::now();
 require(!candidate.pending,"half before resolving prior candidate");
 require(request.position>=0&&request.position<e.p.g.context,"half position bound");
 // packet188 rank0_prepare=async: rank 0's inputs are staged without host waits; the device position is
 // captured by an ordered copy and checked after the half's final drain (finish_staged), before any reply.
 const bool staged=e.a.rank==0&&e.prepare_async;
 if(!prepared_inputs&&!staged)require(e.integer(0,"position")==request.position,"position sequence mismatch");
 require(!prepared_inputs||e.a.rank==1,"prepared half inputs rank ownership");
 require(request.token>=0&&request.token<e.p.g.vocab,"half token bound");
 require(e.a.rank==0||!request.speculative,"rank1 must never speculate");
 e.verify_configuration();e.guard();
 if(e.attribution.enabled)e.attribution.begin(request.fixture,request.position,request.speculative);
 // Snapshot the prior launch extents before admitting a speculative bucket.
 if(request.speculative)p150::measure("snapshot",request.position,false,[&]{image.begin(shared,staged?request.position:-1);});
 e.admit_position(request.position);
 struct rusage before{},after{},thread_before{},thread_after{};getrusage(RUSAGE_SELF,&before);getrusage(RUSAGE_THREAD,&thread_before);
 auto waits=e.host_waits;double waited=e.wait_ms;e.family_ms.fill(0);
 const auto retire_calls=e.retirement_calls;const double retire_ms=e.retirement_ms,profile_ms=e.profiling_ms;
 auto start=std::chrono::steady_clock::now();double gpu=e.gemv_ms+e.nongemv_ms;
 candidate={};candidate.pending=true;candidate.position=request.position;candidate.fixture=request.fixture;candidate.speculative=request.speculative;
 if(e.a.rank==0){candidate.h0=e.history0;candidate.h1=e.history1;
  if(!staged&&e.buffers[0].count("token_history"))p150::measure("token_history",request.position,false,[&]{candidate.token_history=e.readback(0,e.buffers[0].at("token_history").id,16);});}
 auto prepare_start=std::chrono::steady_clock::now();
 if(staged)p150::measure("token_prep",request.position,false,[&]{e.stage_half_inputs(request.token);});
 else {
 if(!prepared_inputs)e.put(0,"token",&request.token,4);
 if(e.a.rank==0){
 const auto h0=e.history0,h1=e.history1;
 p150::measure("token_prep",request.position,false,[&]{e.prepare_token(request.token);});
 p150::measure("token_prep_duplicate",request.position,true,[&]{if(e.sealed_selection.choices.at("probe")=="split"){
 e.history0=h0;e.history1=h1;e.prepare_token(request.token);}});
 }
 else if(!prepared_inputs){size_t n=e.stream_bytes();require(n<=slot_bytes,"shared stream extent");e.put(0,"streams",shared+slot_bytes,n);}
 }
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
  if(e.v3_skip_half[size_t(&l-e.p.launches.data())])continue; // packet186: moved layers run in the boundary (rank 0) or not at all (rank 1, V3)
  if(cancel_at_boundary()){candidate.cancelled=true;break;}
  const auto* ready=e.prepared_path?&e.issue_sites[size_t(&l-e.p.launches.data())]:nullptr;
  if(request.fixture==0&&(ready?ready->prefill_skip:(l.label.starts_with("final.")||l.label=="logits"||l.label=="argmax")))continue;
  if(e.progress_pending&&e.progress_callback)e.progress_callback();
  if(l.label=="logits"&&e.head_export)e.head_export(request.sequence,request.position,request.fixture);
  e.enqueue(l,e.logical);
  if(e.correction_exchange&&(l.op=="gemv"||l.op=="routed_gemv"||l.op=="expert_gate_up")&&(ends(l.label,".gdn.z")||ends(l.label,".qsa.ik")||ends(l.label,".attention")||l.op=="expert_gate_up"||ends(l.label,".expsdown")))e.correction_exchange(l);
  if(l.label=="logits"&&e.head_publish)e.head_publish();
  if(e.progress_pending&&e.progress_callback)e.progress_callback();
  if(ready?ready->layer_end:ends(l.label,".ffn.combine")) {
   int layer=ready?ready->layer:std::stoi(l.label.substr(4));
   if(e.a.rank==1&&e.a.draft_rank==0&&layer==(e.a.mini?3:47)){
    auto bytes=e.readback(0,e.buffers[0].at("streams").id,e.stream_bytes());
    std::memcpy(shared+reverse_offset,bytes.data(),bytes.size());
    __atomic_store_n(&reverse_ready(shared).position_plus_one,uint32_t(request.position+1),__ATOMIC_RELEASE);
   }
   if(e.a.retain_steps.contains(request.fixture)){ownrt::CopyEngine copy(e.dev(0));e.tail=copy.copy(e.snapshots[0],size_t(layer)*e.stream_bytes(),e.buffers[0].at("streams").id,0,e.stream_bytes(),{});captured.at(captured_count++)=layer;}
   if(!e.resident){e.release_layer(0);e.loaded_layer[0]=-1;}
  }
 }}catch(const CancelledLaunch&){candidate.cancelled=true;}
 catch(...){e.dev(0).before_compute={};e.dev(0).after_compute={};throw;}
 e.dev(0).before_compute={};e.dev(0).after_compute={};
 if(cancel_at_boundary())candidate.cancelled=true;
 double enqueue_ms=Engine::ms(enqueue_start)-(e.wait_ms-enqueue_wait);
 e.drain();if(e.a.rank==0)p150::record("layer_body",request.position,false,enqueue_start);
 if(staged)candidate.token_history=e.finish_staged(request.position,e.buffers[0].count("token_history")>0);
 if(request.fixture>0&&e.head_merge)e.head_merge(request.sequence,request.position,request.fixture);
 int error=0,folded_token=-1;bool folded=false;
 if(e.a.rank==1&&request.fixture>0&&e.kio_active){auto both=e.read_error_and_token();error=both.first;folded_token=both.second;folded=true;} // packet188: one kernel readback
 else error=e.integer(0,"error");
 require(!error,"sticky rank error (never rolled back)");
 if(e.a.rank==0&&!candidate.cancelled){e.swap_state_banks();candidate.swapped=true;}
 if(captured_count){auto raw=e.readback(0,e.snapshots[0],48*e.stream_bytes());for(size_t ci=0;ci<captured_count;++ci){int layer=captured[ci];size_t n=e.stream_bytes();candidate.layers[layer]={raw.begin()+layer*n,raw.begin()+(layer+1)*n};}}
 if(captured_count){std::vector<uint8_t> zero(48*e.stream_bytes(),0);e.upload(0,e.snapshots[0],0,zero.data(),zero.size());}
 int token=-1;size_t bytes=0;
 if(e.a.rank==0){if(!e.v3_active)p150::measure("handoff_export",request.position,false,[&]{bytes=e.stream_bytes();auto raw=e.readback(0,e.buffers[0].at("streams").id,bytes);std::memcpy(shared,raw.data(),bytes);});}
 else if(request.fixture>0){token=folded?folded_token:e.integer(0,"next_token");auto& confirmed=verification(shared);confirmed.token=token;__atomic_store_n(&confirmed.position_plus_one,uint32_t(request.position+1),__ATOMIC_RELEASE);}
 if(!e.resident){e.release_layer(0);e.loaded_layer[0]=-1;}
 if(e.a.rank==1)e.reply_report.begin(request.sequence,request.fixture,request.position);
 getrusage(RUSAGE_SELF,&after);getrusage(RUSAGE_THREAD,&thread_after);
 const bool report_site=e.attribution.enabled&&p65timing::sample(request.fixture),report_cancelled=candidate.cancelled;
 const auto report_half=e.attribution.current.half;const auto report_retirement_calls=e.retirement_calls-retire_calls;
 const auto report_reprepares=e.capacity_reprepares,report_waits=e.host_waits-waits,report_checks=e.parity_argument_checks;
 const double report_retirement_ms=e.retirement_ms-retire_ms,report_profiling_ms=e.profiling_ms-profile_ms,report_wait_ms=e.wait_ms-waited;
 const auto report_families=e.family_ms;
 const double half_completion_ms=Engine::ms(start);
 const auto probe_calls=e.correction_exchange_calls,probe_send=e.correction_send_bytes,probe_receive=e.correction_receive_bytes;
 // All changing fields are values. Only stable configuration and output streams
 // remain references. Resource snapshots retain the original half boundary.
 auto report=[=,&e](){
 double load_average=0;getloadavg(&load_average,1);cpu_set_t affinity;CPU_ZERO(&affinity);require(!sched_getaffinity(0,sizeof affinity,&affinity),"per-half affinity");
 if(report_site)e.site_timings
  <<"{\"schema\":\"packet65.half.v1\",\"half\":"<<report_half
  <<",\"rank\":"<<e.a.rank<<",\"fixture\":"<<request.fixture<<",\"position\":"<<request.position
  <<",\"speculative\":"<<(request.speculative?"true":"false")
  <<",\"cancelled\":"<<(report_cancelled?"true":"false")<<"}\n";
 e.timings<<"{\"cpu_affinity\":[";bool comma=false;for(int cpu=0;cpu<CPU_SETSIZE;++cpu)if(CPU_ISSET(cpu,&affinity)){e.timings<<(comma?",":"")<<cpu;comma=true;}e.timings<<"],\"load_average_1m\":"<<load_average<<",\"position\":"<<request.position<<",\"fixture\":"<<request.fixture<<",\"speculative\":"<<(request.speculative?"true":"false")
  <<",\"corrected\":"<<(corrected?"true":"false")<<",\"half_completion_ms\":"<<half_completion_ms<<",\"probe_exchanges\":"<<probe_calls<<",\"probe_send_bytes\":"<<probe_send<<",\"probe_receive_bytes\":"<<probe_receive
  <<",\"p76_retirement_ms\":"<<report_retirement_ms<<",\"p76_retirement_calls\":"<<report_retirement_calls<<",\"p76_profiling_ms\":"<<report_profiling_ms<<",\"p76_ordered_retirement\":"<<(e.ordered_retirement?"true":"false")
  <<",\"launch_extent\":"<<std::min(e.p.g.context,((request.position+32)/32)*32)<<",\"capacity_reprepares\":"<<report_reprepares
  <<",\"cancelled\":"<<(report_cancelled?"true":"false")<<",\"launches_issued\":"<<issued
  <<",\"prepare_ms\":"<<prepare_ms<<",\"enqueue_loop_ms\":"<<enqueue_ms<<",\"wait_ms\":"<<report_wait_ms<<",\"host_waits\":"<<report_waits
  <<",\"process_major_faults\":"<<after.ru_majflt-before.ru_majflt<<",\"process_minor_faults\":"<<after.ru_minflt-before.ru_minflt<<",\"process_voluntary_context_switches\":"<<after.ru_nvcsw-before.ru_nvcsw<<",\"process_involuntary_context_switches\":"<<after.ru_nivcsw-before.ru_nivcsw
  <<",\"thread_voluntary_context_switches\":"<<thread_after.ru_nvcsw-thread_before.ru_nvcsw<<",\"thread_involuntary_context_switches\":"<<thread_after.ru_nivcsw-thread_before.ru_nivcsw
  <<",\"parity_argument_checks\":"<<report_checks<<",\"enqueue_family_ms\":";
 if(!e.class_timing)e.timings<<"null";else {e.timings<<'{';for(size_t j=0;j<e.families.size();++j)e.timings<<(j?",":"")<<ownrt::quote(e.families[j])<<':'<<report_families[j];e.timings<<'}';}e.timings<<"}\n";
 require(bool(e.timings)&&bool(e.site_timings),"p92 half receipt write failed");
 };
 if(e.a.rank==1)e.reply_report.schedule(std::move(report));else report();
 if(e.a.rank==0)p150::record("half_total",request.position,false,p150_half_begin);
 return {0,token,error,int32_t(bytes),request.sequence,e.a.rank,{int32_t(candidate.cancelled),int32_t(issued)},Engine::ms(start),e.gemv_ms+e.nongemv_ms-gpu,0,0};
}
static void undo(Engine& e,Candidate& c,SpeculativeImage& image,bool redo=false,int position=-1,int token=-1) {
 require(e.a.rank==0&&c.pending&&c.speculative,"rollback outside rank0 speculation");
 e.drain();require(!e.integer(0,"error"),"sticky error cannot be rolled back");
 if(c.swapped)e.swap_state_banks();image.restore(redo,position,token);c={};
}
static void state_dump(Engine& e,int sequence) {
 std::ostringstream o;o<<"{\"history0\":"<<e.history0<<",\"history1\":"<<e.history1<<",\"buffers\":{";bool comma=false;
 fs::path dir=e.a.output/("state-"+std::to_string(sequence));fs::create_directories(dir);gsq_bundle::Writer bundle(dir);
 // Full bytes of every plan allocation, including overwrite-only intermediates.
 for(auto& [name,s]:e.buffers[0]){auto b=e.readback(0,s.id,s.n*flash::scalar_bytes(s.type));bundle.append(name+".bin",b.data(),b.size());
  o<<(comma?",":"")<<ownrt::quote(name)<<":"<<ownrt::quote(hash(b));comma=true;}
 for(auto& [name,id]:e.state_spares){auto b=e.readback(0,id,e.dev(0).arena.row(id).bytes);bundle.append("alternate-"+name+".bin",b.data(),b.size());o<<","<<ownrt::quote("alternate:"+name)<<":"<<ownrt::quote(hash(b));}
 o<<"},\"fp32_cache_valid\":"<<(e.fp32_sources[0]?"true":"false")<<",\"fp32_extent\":"<<e.fp32_extents[0]<<"}";bundle.finish(o.str());
}
} // namespace pipeline
static void pipeline_cancel_check() {
 if(pipeline_stop_fd<0)return;
 pollfd fd{pipeline_stop_fd,POLLIN,0};int rc=::poll(&fd,1,0);
 require(rc>=0||errno==EINTR,"stop channel poll failed");
 require(!stopped && !(fd.revents&(POLLIN|POLLHUP|POLLERR|POLLNVAL)),"cooperative rank stop");
}
#include "stage2/packet194-expert-diet-engine/rank_canary.hpp"
#include "stage2/packet194-expert-diet-engine/request_reset.hpp"
#include "stage2/packet194-expert-diet-engine/native_controller.hpp"
#include "gsq-rco-iq3s/integration/build/private/source/diet-native/native/v3_boundary.hpp"
#include "gsq-rco-iq3s/integration/build/private/source/diet-native/native/bracket_boundary.hpp"
#include "gsq-rco-iq3s/integration/build/private/source/diet-native/native/probe_exchange.hpp"
static int run_rank(const Options& a) {
 using namespace pipeline;
 std::unique_ptr<Weights> weights;std::unique_ptr<Engine> engine;std::unique_ptr<mtp36::DraftRuntime> provider;
 std::unique_ptr<p105::Runtime> head_runtime;bool native_active=false;
 int fd=-1;void* mapping=MAP_FAILED;std::string error,selection_observed_sha256;std::vector<std::string> teardown;
 pipeline_stop_fd=a.stop_fd;
 try {
  require(a.channel>=0&&a.stop_fd>=0&&!a.shared.empty(),"rank IPC arguments required");
  fd=::open(a.shared.c_str(),O_RDWR|O_NOFOLLOW);require(fd>=0,"shared open");struct stat st{};
  require(!fstat(fd,&st)&&st.st_size==shared_bytes,"shared extent");mapping=mmap(nullptr,shared_bytes,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);require(mapping!=MAP_FAILED,"shared mmap");
  if(a.pipeline_canary){int rc=run_pipe_canary(a,static_cast<uint8_t*>(mapping));munmap(mapping,shared_bytes);::close(fd);return rc;}
  weights=std::make_unique<Weights>(a);auto p=split(plan(*weights,a),a.rank,a.mini,a.draft_rank,a.target_split,v3::rank0_extended(a));
  dump_plan(a.output/"launch-plan.json",p);write_plan(a.output/"plan.json",p,*weights,1,a);
  engine=std::make_unique<Engine>(*weights,a,p);selection_observed_sha256=engine->sealed_selection.observed_sha256;record_host_memory(a.output,"before_load");engine->initialize();
  // Exact F32 activation mode is admitted only on the paths that have F32 variants.
  if(a.f32_activations)require(!engine->v3_active&&!engine->kio_active&&!engine->prepare_async&&!engine->split_head()&&engine->sealed_selection.choices.at("probe")=="off"&&a.gsq_packed&&a.draft_rank==0,"exact F32 activations: unsupported optional path/selection");
  if(engine->split_head())head_runtime=std::make_unique<p105::Runtime>(*engine);
  if(a.rank==0)banks(*engine);else {engine->prepare_plan();engine->prepare_commands();}
  auto& head_box=*reinterpret_cast<p105::Mailbox*>(static_cast<uint8_t*>(mapping)+reverse_offset);
  static_assert(sizeof(p105::Mailbox)<=slot_bytes);
  if(head_runtime&&a.rank==1){
   engine->head_export=[&](int seq,int pos,int fixture){require(native_active,"p105 requires native controller");head_runtime->export_hidden(head_box,uint32_t(seq),pos,fixture);};
   engine->head_publish=[&](){head_runtime->publish_hidden(head_box);};
   engine->head_merge=[&](int seq,int pos,int fixture){head_runtime->merge_target(head_box,uint32_t(seq),pos,fixture,pipeline_cancel_check);};
  }
  // packet186: the p149 probe (selection probe=xchg, never bundle 8) needs full geometry; the miniature
  // two-rank V3 state gate runs without it. Full-shape construction order is unchanged.
  std::optional<p149::Exchange> probe;if(!a.mini)probe.emplace(*engine,static_cast<uint8_t*>(mapping));
  SpeculativeImage image(*engine);
#ifndef OWN_RT_HOST_ONLY
  if(a.rank==0&&!a.gsq_packed)weights->warm_lookups();
#endif
  save(a.output/"lookup-residency.json",weights->residency);
  {cpu_set_t cpus;CPU_ZERO(&cpus);require(!sched_getaffinity(0,sizeof cpus,&cpus),"affinity receipt");double load=0;getloadavg(&load,1);std::ostringstream o;o<<"{\"cpu_affinity\":[";bool comma=false;for(int i=0;i<CPU_SETSIZE;++i)if(CPU_ISSET(i,&cpus)){o<<(comma?",":"")<<i;comma=true;}o<<"],\"load_average_1m\":"<<load<<"}";save(a.output/"host-environment.json",o.str());}
  record_host_memory(a.output,"after_load");
  if(a.mtp&&a.rank==a.draft_rank)provider=std::make_unique<mtp36::DraftRuntime>(*engine);
  save(a.output/"census.json",engine->dev(0).arena.census());
  engine->bracket_weights_locked=true;
  save(a.output/"loaded-arena-descriptors.txt",engine->bracket_arena_descriptors());
  Reply ready{};ready.rank=a.rank;transfer(a.channel,&ready,sizeof ready,true,a.seconds);
  Candidate c;int sequence=0,accepted=0;bool async_half_ready=false;int async_half_position=-1,async_half_token=-1;V3Boundary v3state;
  auto execute=[&](const Request& r)->Reply {
   if(a.rank==1)engine->reply_report.before(r.op);
   auto received=std::chrono::steady_clock::now();
   Reply response{};response.sequence=r.sequence;response.rank=a.rank;
   bool completing_redo=image.before_command(r.op==half&&!r.speculative,r.position,r.token);
   if(r.op==draft){
    require(a.rank==a.draft_rank&&provider&&r.position>0,"draft command ownership/confirmation");
    if(a.rank==1){require(!c.pending&&engine->integer(0,"position")==r.position,"draft target not confirmed");}
    else {auto* bytes=static_cast<uint8_t*>(mapping);require(__atomic_load_n(&reverse_ready(bytes).position_plus_one,__ATOMIC_ACQUIRE)==uint32_t(r.position),"reverse stream position mismatch");
     if(__atomic_load_n(&verification(bytes).position_plus_one,__ATOMIC_ACQUIRE)){auto& v=verification(bytes);require(__atomic_load_n(&v.position_plus_one,__ATOMIC_ACQUIRE)==uint32_t(r.position)&&v.token==r.token,"rank0 draft requires target confirmation");}
     provider->set_reverse_hidden(bytes+reverse_offset);}
    auto before=std::chrono::steady_clock::now();double gpu=engine->gemv_ms+engine->nongemv_ms;
    struct Publication{int32_t valid,position,token,error;uint64_t elapsed_ns;int32_t sequence,reserved;double gpu_ms;};static_assert(sizeof(Publication)==40);
    auto publish_draft=[&,r](int token,double wall_ms,double gpu_ms){
     Publication v{int32_t(token>=0&&token<engine->p.g.vocab),r.position+1,token,int32_t(token<0&&r.fixture!=0),uint64_t(wall_ms*1e6),r.sequence,0,gpu_ms};
     std::memcpy(static_cast<uint8_t*>(mapping)+2*slot_bytes,&v,sizeof v);
     if(r.speculative){auto& mailbox=*reinterpret_cast<native38::Mailbox*>(static_cast<uint8_t*>(mapping)+2*slot_bytes+256);native38::publish(mailbox.draft_sequence,uint32_t(r.sequence));}
    };
    if(r.speculative){
     require(!async_half_ready,"duplicate asynchronous draft");
     async_half_ready=a.rank==1;async_half_position=r.position;async_half_token=r.token;
     if(provider->begin(r.token,r.position,r.fixture!=0)){
      engine->progress_callback=[&,publish_draft](){if(provider->submitting())if(auto completed=provider->poll_result())publish_draft(completed->token,completed->wall_ms,completed->gpu_ms);};
     }else {engine->progress_callback={};publish_draft(-1,Engine::ms(before),0);}
    }else {int token=provider->run(r.token,r.position,r.fixture!=0);publish_draft(token,Engine::ms(before),engine->gemv_ms+engine->nongemv_ms-gpu);}
    response.busy_ms=Engine::ms(before);response.gpu_ms=engine->gemv_ms+engine->nongemv_ms-gpu;
   }
   else if(r.op==half){
    require(!head_runtime||native_active,"p105 head split requires native controller");
    v3_before_half(*engine,v3state,r);
    bool prepared_inputs=async_half_ready;
    if(prepared_inputs){require(r.position==async_half_position&&r.token==async_half_token,"asynchronous draft/half confirmed identity");provider->queue_half_inputs(r.token,static_cast<uint8_t*>(mapping)+slot_bytes);async_half_ready=false;}
    engine->correction_exchange_calls=engine->correction_send_bytes=engine->correction_receive_bytes=0;
    if(completing_redo&&engine->sealed_selection.choices.at("probe")=="xchg")
      engine->correction_exchange=[&](const flash::Launch& l){require(bool(probe),"p149 probe absent");probe->exchange(l);};
    try {response=half_step(*engine,c,r,static_cast<uint8_t*>(mapping),image,prepared_inputs,completing_redo);}
    catch(...){engine->correction_exchange={};throw;}
    engine->correction_exchange={};
    require(engine->correction_exchange_calls==((completing_redo&&engine->sealed_selection.choices.at("probe")=="xchg")?96:0),"p149 corrected-half exchange census");
    if(completing_redo){require(!c.cancelled&&c.swapped,"incomplete confirmed redo");image.finish_redo();}
   }
   else if(r.op==pipeline::accept){require(c.pending,"accept without candidate");publish(*engine,c);if(c.speculative)image.accept();if(c.fixture>0)++accepted;v3_accepted(*engine,v3state,c);c={};}
   else if(r.op==v3::boundary_op){response=v3_boundary_step(*engine,v3state,r,static_cast<uint8_t*>(mapping),c);}
   else if(r.op==rollback){
    bool redo=r.speculative==1;require(r.speculative==0||redo,"rollback mode");
    if(redo){auto& v=verification(static_cast<uint8_t*>(mapping));
     require(c.pending&&c.speculative&&r.position==c.position&&r.fixture==c.fixture&&r.token>=0&&r.token<engine->p.g.vocab,"redo identity");
     require(__atomic_load_n(&v.position_plus_one,__ATOMIC_ACQUIRE)==uint32_t(r.position)&&v.token==r.token,"redo requires verified target token (verified "+std::to_string(v.position_plus_one)+"/"+std::to_string(v.token)+", redo "+std::to_string(r.position)+"/"+std::to_string(r.token)+")");}
    undo(*engine,c,image,redo,r.position,r.token);
   }
   else if(r.op==14){
    require(a.rank==1&&native_active&&!c.pending&&engine->sealed_selection.choices.at("probe")=="xchg","p149 miss responder ownership");
    require(bool(probe),"p149 probe absent");probe->serve_correction([&]{if(engine->progress_pending&&engine->progress_callback)engine->progress_callback();});
   }
   else if(r.op==dump){require(!c.pending,"dump uncommitted state");image.boundary();state_dump(*engine,r.position);if(r.position==2147483647)request_state_inventory(*engine);}
   else if(r.op==11){image.boundary();v3state.reset();request_reset(*engine,c,provider.get(),a.output/("reset-"+std::to_string(r.sequence)+".txt"),accepted);accepted=0;}
   else if(r.op==13){require(!async_half_ready,"pending half");v3state.reset();bracket_boundary(*engine,c,provider.get(),image,a.output/("bracket-"+std::to_string(r.sequence)+".txt"),accepted);async_half_position=async_half_token=-1;}
   #ifdef OWN_RT_HOST_ONLY
   else if(r.op==12){require(a.rank==0&&c.pending&&c.speculative,"negative control ownership");image.corrupt_protected_for_gate(r.token);}
#endif
   else if(r.op==fail)throw std::runtime_error("injected rank failure");
   else if(r.op==stall){auto until=std::chrono::steady_clock::now()+std::chrono::seconds(a.seconds);while(std::chrono::steady_clock::now()<until){pipeline_cancel_check();poll(nullptr,0,10);}throw std::runtime_error("bounded injected stall");}
   else throw std::runtime_error("unknown rank command");
   if(a.rank==1)engine->reply_report.after(r.op);
   response.redo_ms=std::chrono::duration<double>(received.time_since_epoch()).count();
   response.reserved_ms=std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
   if(a.rank==0&&(r.op==pipeline::accept||r.op==rollback))p150::record(r.op==pipeline::accept?"accept":"rollback",r.position,false,received);
   return response;
  };
  for(;;){Request r{};transfer(a.channel,&r,sizeof r,false,a.seconds);require(r.sequence==++sequence,"command sequence");
   if(r.op==finish){if(a.rank==1)engine->reply_report.flush();require(!c.pending,"finish with unresolved candidate");require(!v3state.ready,"finish with a pending V3 boundary");image.boundary();if(provider&&a.finish_dump)provider->dump_all_state(engine->a.output/"draft-final-state");break;}
   Reply response{};
   if(r.op==10){
    require(!c.pending,"native entry unresolved candidate");
    auto* bytes=static_cast<uint8_t*>(mapping);auto& mailbox=*reinterpret_cast<native38::Mailbox*>(bytes+2*slot_bytes+256);
    auto cancel=[&](){pipeline_cancel_check();if(engine->progress_pending&&engine->progress_callback)engine->progress_callback();};
    try {native_active=true;p150::samples.clear();
     if(a.rank==1)native38::worker(mailbox,a.seconds,execute,cancel,
       [&](const Request& cmd){if(cmd.op==half)engine->reply_report.published();},
       [&](){engine->reply_report.flush();});
     else {
      auto cfg=native38::config(a.shared.parent_path()/"native-request.txt",engine->p.g.context,engine->p.g.vocab);cfg.draft_rank=a.draft_rank;
      native38::Backend backend(mailbox,bytes,a.seconds,execute,cancel);
      backend.split_replay=engine->sealed_selection.choices.at("probe")=="split";
      backend.correction_probe=engine->sealed_selection.choices.at("probe")=="xchg";
      if(head_runtime)backend.before_remote_wait=[&](const Request& req){if(req.op==half&&req.fixture>0)head_runtime->service(head_box,uint32_t(req.sequence),req.position,req.fixture,[&]{cancel();require(!native38::load(mailbox.abort),"p105 native peer failed");});};
       native38::ConfirmedStream stream;native38::EmitConfirmed emit;
       if(a.token_stream){
        stream.begin(engine->a.output/"confirmed-tokens.jsonl",r.sequence,cfg.count,cfg.vocab);
        emit=[&](size_t index,int token,double stamp){stream.token(index,token,stamp);};
       }
       auto result=engine->v3_active?native38::run_v3(backend,cfg,emit):native38::run(backend,cfg,emit); // packet186
      save(a.shared.parent_path()/"native-result.json",native38::json(result,backend,cfg));
       // End seals the list, not overall request success: normal rank replies remain required.
       if(a.token_stream)stream.end(result.tokens.size());
     }
     p150::flush(engine->timings,a.rank);engine->timings.flush();native_active=false;
    }catch(...){p105::publish(head_box.abort,1);native38::abort(mailbox);throw;}
    response.sequence=r.sequence;response.rank=a.rank;
   }else response=execute(r);
   transfer(a.channel,&response,sizeof response,true,a.seconds);
   if(a.rank==1&&r.op==half)engine->reply_report.published();
  }
  engine->dump_classes(engine->a.output/"class-times.json",accepted);
 }catch(const std::exception& ex){
  error=ex.what();
  if(engine&&a.rank==1&&!engine->reply_report.poisoned())try{engine->reply_report.flush();}catch(const std::exception& report){error+="; report: "+std::string(report.what());}
  // A full filesystem cannot bypass the explicit provider/owner drain below.
  try{save(a.output/"failure.txt",error+"\n");}
  catch(const std::exception& record){error+="; failure record: "+std::string(record.what());std::cerr<<error<<"\n";}
  try{save(a.output/"receipt.json","{\"passed\":false,\"teardown_pending\":true,\"error\":"+ownrt::quote(error)+"}");}
  catch(const std::exception& record){error+="; failure receipt: "+std::string(record.what());std::cerr<<error<<"\n";}
 }
 // Failure receipt is durable before any teardown. Device owns all SYCL borrowers.
 if(engine)engine->progress_callback={};
 head_runtime.reset();
 provider.reset();
 if(engine){try{teardown=engine->shutdown();}catch(const std::exception& ex){error+=(error.empty()?"":"; ")+std::string(ex.what());}engine.reset();}
 weights.reset();if(mapping!=MAP_FAILED)munmap(mapping,shared_bytes);if(fd>=0)::close(fd);
 std::ostringstream o;o<<"{\"schema\":\"packet32.rank.v1\",\"passed\":"<<(error.empty()?"true":"false")<<",\"rank\":"<<a.rank<<",\"error\":"<<ownrt::quote(error)<<",\"arithmetic\":"<<ownrt::quote(arithmetic::version)<<",\"device_executed\":"
#ifdef OWN_RT_HOST_ONLY
 <<"false"
#else
 <<"true"
#endif
 <<",\"selection_sha256\":"<<ownrt::quote(selection_observed_sha256)<<",\"teardown\":[";for(size_t i=0;i<teardown.size();++i)o<<(i?",":"")<<teardown[i];o<<"]}";save(a.output/"receipt.json",o.str());return error.empty()?0:1;
}
