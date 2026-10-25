#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#include "gsq-rco-iq3s/integration/build/private/source/diet-native/native-src/strict_snapshot.hpp"
#include "pipeline/checkpoint.hpp"
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
 require(target_split==0||(target_split>=20&&target_split<=24),"unsupported target split");
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
 for(auto& b:p.buffers){o<<(comma?",":"")<<"{\"name\":"<<ownrt::quote(b.name)<<",\"bytes\":"<<count(b.shape)*flash::scalar_bytes(b.type)<<",\"dtype\":"<<ownrt::quote(b.type==flash::Scalar::bf16?"BF16":b.type==flash::Scalar::f32?"F32":b.type==flash::Scalar::i32?"I32":b.type==flash::Scalar::u32?"U32":"I64")<<",\"shape\":[";for(size_t i=0;i<b.shape.size();++i)o<<(i?",":"")<<b.shape[i];o<<"]}";comma=true;}
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
 require(!e.a.pipeline_enabled()||!request.speculative,"general pipeline is target-only");
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
 if(!prepared_inputs){e.put(0,"token",&request.token,4);if(e.a.tp_replicate)e.put(1,"token",&request.token,4);}
 if(e.a.rank==0){
 const auto h0=e.history0,h1=e.history1;
 p150::measure("token_prep",request.position,false,[&]{e.prepare_token(request.token);});
 p150::measure("token_prep_duplicate",request.position,true,[&]{if(e.sealed_selection.choices.at("probe")=="split"){
 e.history0=h0;e.history1=h1;e.prepare_token(request.token);}});
 }
 else if(!prepared_inputs){size_t n=e.stream_bytes();require(n<=slot_bytes,"shared stream extent");e.put(0,"streams",shared+slot_bytes,n);if(e.a.tp_replicate)e.put(1,"streams",shared+slot_bytes,n);}
 }
 double prepare_ms=Engine::ms(prepare_start);auto enqueue_start=std::chrono::steady_clock::now();double enqueue_wait=e.wait_ms;
 std::array<int,48> captured{};size_t captured_count=0,issued=0;
 // Diagnostic only (OWNRT_DECODE_PROFILE=1): drain after every site and add its wall time to its op (linear sites by
 // weight format), one line per HALF. Serializes the step, so it shows where time goes, never speed. No arithmetic change.
 // OWNRT_DECODE_PROFILE=2: device timestamps instead. Per site, the summed kernel durations and the idle gap between
 // the previous kernel's end and this site's first start, with no drain between sites (events stay in the ledger
 // until the half's final drain).
 static const int decode_profile_mode=[]{const char* v=std::getenv("OWNRT_DECODE_PROFILE");return v?std::atoi(v):0;}();
 static const bool decode_profile=decode_profile_mode==1;
 std::map<std::string,std::pair<int,double>> decode_spent;
 struct SiteEvents{std::string key;std::vector<ownrt::Event> events;};std::vector<SiteEvents> device_sites;
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
 e.dev(0).after_compute=[&](ownrt::Event event){e.tail=event;++issued;if(decode_profile_mode>=2&&!device_sites.empty())device_sites.back().events.push_back(event);};
 try {for(auto& l:e.p.launches) {
  if(e.v3_skip_half[size_t(&l-e.p.launches.data())])continue; // packet186: moved layers run in the boundary (rank 0) or not at all (rank 1, V3)
  if(cancel_at_boundary()){candidate.cancelled=true;break;}
  const auto* ready=e.prepared_path?&e.issue_sites[size_t(&l-e.p.launches.data())]:nullptr;
  if(request.fixture==0&&(ready?ready->prefill_skip:(l.label.starts_with("final.")||l.label=="logits"||l.label=="argmax")))continue;
  if(e.progress_pending&&e.progress_callback)e.progress_callback();
  if(l.label=="logits"&&e.head_export)e.head_export(request.sequence,request.position,request.fixture);
  if(decode_profile)e.drain();
  if(decode_profile_mode>=2){std::string key=l.op;if(l.op=="gemv"||l.op=="routed_gemv"){auto role=l.label;if(role.starts_with("blk.")){auto dot=role.find('.',4);if(dot!=std::string::npos)role=role.substr(dot+1);}key+=":"+e.w.directory.at(l.weights.at(0)).grid+":"+role;}device_sites.push_back({key,{}});}
  const auto site_start=std::chrono::steady_clock::now();
  e.enqueue(l,e.logical);
  if(decode_profile){e.drain();
   // Linear sites by weight format and role (label without its layer number), other sites by op.
   std::string key=l.op;if(l.op=="gemv"||l.op=="routed_gemv"){auto role=l.label;if(role.starts_with("blk.")){auto dot=role.find('.',4);if(dot!=std::string::npos)role=role.substr(dot+1);}key+=":"+e.w.directory.at(l.weights.at(0)).grid+":"+role;}
   auto& entry=decode_spent[key];++entry.first;entry.second+=Engine::ms(site_start);}
  if(e.correction_exchange&&(l.op=="gemv"||l.op=="routed_gemv"||l.op=="expert_gate_up")&&(ends(l.label,".gdn.z")||ends(l.label,".qsa.ik")||ends(l.label,".attention")||l.op=="expert_gate_up"||ends(l.label,".expsdown")))e.correction_exchange(l);
  if(l.label=="logits"&&e.head_publish)e.head_publish();
  if(e.progress_pending&&e.progress_callback)e.progress_callback();
  if(ready?ready->layer_end:ends(l.label,".ffn.combine")) {
   int layer=ready?ready->layer:std::stoi(l.label.substr(4));
   if((!e.a.pipeline_enabled()&&e.a.rank==1&&e.a.draft_rank==0&&layer==(e.a.mini?3:47))||(e.a.pipeline_live_draft&&e.a.pipeline_final()&&layer==e.a.pipeline_boundaries.back()-1)){
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
 if(decode_profile_mode>=2&&e.tail){
  // Read every site's device timestamps before the final drain retires the events.
  // Mid-half drains (rank 1 exports its final rows) retire earlier events; those sites are skipped, never waited on.
  ownrt::Event last=0;for(const auto& site:device_sites)if(!site.events.empty())last=site.events.back();
  try{if(last)e.dev(0).wait(last,std::chrono::milliseconds(10000));}catch(const std::exception&){}
  std::map<std::string,std::array<double,3>> spent;uint64_t previous_end=0,first_start=0,last_end=0;
  // OWNRT_DECODE_PROFILE=3: as 2, with each launch of a multi-pass site under its own key (site#pass).
  for(const auto& site:device_sites){if(site.events.empty())continue;auto& v=spent[site.key];v[2]+=1;
   for(size_t i=0;i<site.events.size();++i){if(decode_profile_mode==3&&site.events.size()>1){ownrt::EventTiming t{};try{t=e.dev(0).timing(site.events[i]);}catch(const std::exception&){continue;}auto& w=spent[site.key+"#"+std::to_string(i)];w[0]+=double(t.end_ns-t.start_ns)/1000.0;w[2]+=1;}ownrt::EventTiming t{};try{t=e.dev(0).timing(site.events[i]);}catch(const std::exception&){previous_end=0;continue;}if(!first_start)first_start=t.start_ns;
    if(i==0&&previous_end&&t.start_ns>previous_end)v[1]+=double(t.start_ns-previous_end)/1000.0;
    v[0]+=double(t.end_ns-t.start_ns)/1000.0;previous_end=t.end_ns;last_end=std::max(last_end,t.end_ns);}}
  std::ofstream o(e.a.output/"decode-device-profile.jsonl",std::ios::app);o<<"{\"position\":"<<request.position<<",\"fixture\":"<<request.fixture<<",\"speculative\":"<<(request.speculative?"true":"false")<<",\"cancelled\":"<<(candidate.cancelled?"true":"false")<<",\"span_us\":"<<double(last_end-first_start)/1000.0<<",\"sites\":{";bool comma=false;
  for(const auto& [k,v]:spent){o<<(comma?",":"")<<ownrt::quote(k)<<":{\"count\":"<<v[2]<<",\"busy_us\":"<<v[0]<<",\"gap_us\":"<<v[1]<<"}";comma=true;}o<<"}}\n";
 }
 e.drain();if(e.a.rank==0)p150::record("layer_body",request.position,false,enqueue_start);
 if(decode_profile){std::ofstream o(e.a.output/"decode-profile.jsonl",std::ios::app);o<<"{\"position\":"<<request.position<<",\"fixture\":"<<request.fixture<<",\"speculative\":"<<(request.speculative?"true":"false")<<",\"cancelled\":"<<(candidate.cancelled?"true":"false")<<",\"sites\":{";bool comma=false;
  for(const auto& [k,v]:decode_spent){o<<(comma?",":"")<<ownrt::quote(k)<<":{\"count\":"<<v.first<<",\"ms\":"<<v.second<<"}";comma=true;}o<<"}}\n";}
 if(staged)candidate.token_history=e.finish_staged(request.position,e.buffers[0].count("token_history")>0);
 if(request.fixture>0&&e.head_merge)e.head_merge(request.sequence,request.position,request.fixture);
 int error=0,folded_token=-1;bool folded=false;
 if(e.a.rank==1&&request.fixture>0&&e.kio_active){auto both=e.read_error_and_token();error=both.first;folded_token=both.second;folded=true;} // packet188: one kernel readback
 else {error=e.integer(0,"error");if(e.a.tp_replicate)error=error||e.integer(1,"error");}
 require(!error,"sticky rank error (never rolled back)");
 if(e.a.rank==0&&!candidate.cancelled){e.swap_state_banks();candidate.swapped=true;}
 if(captured_count){auto raw=e.readback(0,e.snapshots[0],48*e.stream_bytes());for(size_t ci=0;ci<captured_count;++ci){int layer=captured[ci];size_t n=e.stream_bytes();candidate.layers[layer]={raw.begin()+layer*n,raw.begin()+(layer+1)*n};}}
 if(captured_count){std::vector<uint8_t> zero(48*e.stream_bytes(),0);e.upload(0,e.snapshots[0],0,zero.data(),zero.size());}
 int token=-1;size_t bytes=0;
 if(e.a.pipeline_enabled()){
  if(!e.a.pipeline_final()){bytes=e.stream_bytes();require(bytes>0&&bytes<=slot_bytes,"pipeline stream export extent");auto raw=e.readback(0,e.buffers[0].at("streams").id,bytes);std::memcpy(shared,raw.data(),bytes);}
  else if(request.fixture>0)token=e.integer(0,"next_token");
 }
 else if(e.a.rank==0){if(!e.v3_active)p150::measure("handoff_export",request.position,false,[&]{bytes=e.stream_bytes();auto raw=e.readback(0,e.buffers[0].at("streams").id,bytes);std::memcpy(shared,raw.data(),bytes);});}
 else if(request.fixture>0){token=folded?folded_token:e.integer(0,"next_token");if(e.a.tp_replicate)require(e.integer(1,"next_token")==token,"tp-replicate: card 1 next token differs from card 0");auto& confirmed=verification(shared);confirmed.token=token;__atomic_store_n(&confirmed.position_plus_one,uint32_t(request.position+1),__ATOMIC_RELEASE);}
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
 for(auto& [name,s]:e.buffers[0]){if(name.find("#tp")!=std::string::npos)continue; // TP-internal half buffers: not model state
  auto b=e.readback(0,s.id,s.n*flash::scalar_bytes(s.type));bundle.append(name+".bin",b.data(),b.size());
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
#include "pipeline/request_reset.hpp"
#include "pipeline/ring/dispatcher.hpp"
#include "gsq-rco-iq3s/state-bundle/build/source-v4/prefill_wire.hpp"
#include "stage2/packet194-expert-diet-engine/native_controller.hpp"
#include "gsq-rco-iq3s/integration/build/private/source/diet-native/native/v3_boundary.hpp"
#include "gsq-rco-iq3s/integration/build/private/source/diet-native/native/bracket_boundary.hpp"
#include "gsq-rco-iq3s/integration/build/private/source/diet-native/native/probe_exchange.hpp"
// --tp-replicate gate: every non-weight buffer of card 1 must equal card 0 bitwise after the same steps.
static void tp_compare(Engine& e,const fs::path& path) {
 e.drain();std::ostringstream o;o<<"{\"buffers\":";size_t n=0;std::vector<std::string> differ;
 for(const auto& [name,slot]:e.buffers[0]){if(name.find("#tp")!=std::string::npos)continue; // per-card halves differ by design
  auto other=e.buffers[1].find(name);if(other==e.buffers[1].end()){differ.push_back(name+" (missing on card 1)");continue;}
  const size_t bytes=slot.n*flash::scalar_bytes(slot.type);if(!bytes)continue;++n;
  if(e.readback(0,slot.id,bytes)!=e.readback(1,other->second.id,bytes))differ.push_back(name);}
 o<<n<<",\"differ\":[";for(size_t i=0;i<differ.size();++i)o<<(i?",":"")<<ownrt::quote(differ[i]);o<<"],\"passed\":"<<(differ.empty()?"true":"false")<<"}";
 save(path,o.str());
}
static int run_rank(const Options& a) {
 using namespace pipeline;
 std::unique_ptr<Weights> weights;std::unique_ptr<Engine> engine;std::unique_ptr<mtp36::DraftRuntime> provider;
 std::unique_ptr<p105::Runtime> head_runtime;bool native_active=false;
 int fd=-1;void* mapping=MAP_FAILED;std::string error,selection_observed_sha256;std::vector<std::string> teardown;
 int prefill_fd=-1;void* prefill_map=MAP_FAILED;size_t prefill_map_bytes=0;uint8_t* prefill_base=nullptr;
 pipeline_stop_fd=a.stop_fd;
 try {
  require(a.channel>=0&&a.stop_fd>=0&&!a.shared.empty(),"rank IPC arguments required");
  fd=::open(a.shared.c_str(),O_RDWR|O_NOFOLLOW);require(fd>=0,"shared open");struct stat st{};
  require(!fstat(fd,&st)&&st.st_size==shared_bytes,"shared extent");mapping=mmap(nullptr,shared_bytes,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);require(mapping!=MAP_FAILED,"shared mmap");
  if(a.pipeline_canary){int rc=run_pipe_canary(a,static_cast<uint8_t*>(mapping));munmap(mapping,shared_bytes);::close(fd);return rc;}
  // --tp-replicate: the plan is the one-card rank plan; the card-1 twins are added after write_plan.
  Options one_card=a;one_card.cards=1;
  weights=std::make_unique<Weights>(a);auto full_plan=plan(*weights,one_card);
  auto p=a.pipeline_enabled()?ownrt::pipeline_layout::slice(std::move(full_plan),a.pipeline_boundaries,a.pipeline_stage):split(std::move(full_plan),a.rank,a.mini,a.draft_rank,a.target_split,v3::rank0_extended(a));
  dump_plan(a.output/"launch-plan.json",p);write_plan(a.output/"plan.json",p,*weights,1,one_card);
  if(a.tp_replicate){ // every launch also on card 1 (same arithmetic), every buffer on both cards
   // OWNRT_TP_SPLIT=".attention,.gdn.qkv": those dense GEMVs are row-split instead. Card c computes rows
   // [c*R/2, (c+1)*R/2) into its half buffer y#tp (whole rows, unchanged arithmetic), then a tp_gather site on each
   // card assembles y from its own half (local copy) and the peer's half (peer copy). Order L0, L1, G0, G1.
   std::vector<std::string> roles;if(const char* v=std::getenv("OWNRT_TP_SPLIT")){std::string s=v;size_t at=0;
    while(at<=s.size()){auto end=s.find(',',at);if(end==std::string::npos)end=s.size();if(end>at)roles.push_back(s.substr(at,end-at));at=end+1;}}
   // Only the p33 dense paths with row-major expanded rows (Q6_K qkv, Q8_0 attention) are split today.
   auto split_site=[&](const flash::Launch& l){if(l.op!="gemv"||!l.label.starts_with("blk.")||!(qkv_q6_site(*weights,a,l)||attention_q8_site(*weights,a,l)))return false;for(const auto& r:roles)if(ends(l.label,r))return true;return false;};
   std::vector<flash::Launch> both;both.reserve(p.launches.size()*2);std::set<std::string> halves;
   // OWNRT_TP_EXPERTS=1: placement (mask + gather). Timing-only diagnostics, outputs NOT exact: =mask (mask, no gather),
   // =gather (gather on unmasked routes; exact, measures the gather's cost).
   const std::string tp_experts=[]{const char* v=std::getenv("OWNRT_TP_EXPERTS");return std::string(v?v:"");}();
   // =slot: every card holds every expert (replicated weights); the 10 slots split by position (5/5), exact.
   const bool experts=tp_experts=="1"||tp_experts=="mask"||tp_experts=="gather"||tp_experts=="slot";
   const bool mask_routes=tp_experts=="1"||tp_experts=="mask"||tp_experts=="slot",gather_rows=tp_experts=="1"||tp_experts=="gather"||tp_experts=="slot";
   const int by_slot=tp_experts=="slot"?2:0; // carried in Launch::parameter bit 1
   for(const auto& l:p.launches){
    if(split_site(l)){
     const int R=l.shape.at(1);require(R>0&&R%2==0,"TP split needs an even row count");
     const std::string y=l.outputs.at(0),part=y+"#tp";
     if(halves.insert(part).second){auto it=std::find_if(p.buffers.begin(),p.buffers.end(),[&](const flash::Buffer& b){return b.name==y;});
      require(it!=p.buffers.end(),"TP split output buffer");flash::Buffer b=*it;b.name=part;b.shape={R/2};p.buffers.push_back(b);}
     for(int c=0;c<2;++c){auto t=l;t.card=c;t.row_begin=c*(R/2);t.row_count=R/2;t.outputs.at(0)=part;both.push_back(std::move(t));}
     for(int c=0;c<2;++c){flash::Launch g;g.op="tp_gather";g.label=l.label+".tp_gather";g.card=c;g.inputs={part};g.outputs={y};g.shape={R};g.parameter=R/2;both.push_back(std::move(g));}
    } else {both.push_back(l);auto twin=l;twin.card=1;both.push_back(std::move(twin));}
    // OWNRT_TP_EXPERTS=1: card c computes only the slots whose expert id has parity c (routes masked after the
    // gather), and takes the other slots' expsdown rows from the peer before the unchanged in-order moe_combine.
    if(mask_routes&&l.op=="expert_gather"&&l.outputs.size()>=2)for(int c=0;c<2;++c){flash::Launch m;m.op="tp_route_mask";m.label=l.label+".tp_mask";m.card=c;
     m.inputs={l.outputs[0],l.outputs[1]};m.outputs={l.outputs[0],l.outputs[1]};m.parameter=c|by_slot;both.push_back(std::move(m));}
    if(gather_rows&&l.op=="routed_gemv"&&ends(l.label,".expsdown")){
     const std::string y=l.outputs.at(0),part=y+"#tp",ids=l.label.substr(0,l.label.size()-9)+".ids";
     if(halves.insert(part).second){auto it=std::find_if(p.buffers.begin(),p.buffers.end(),[&](const flash::Buffer& b){return b.name==y;});
      require(it!=p.buffers.end(),"TP expert output buffer");flash::Buffer b=*it;b.name=part;p.buffers.push_back(b);}
     // Push, then wait, then select: each card pushes its routed output into the peer's y#tp (own queue, no cross
     // wait); card 1 then waits for card 0's latest work (its push), card 0 for card 1's (push and wait); each selects
     // its non-owned slots from y#tp. Only true data dependencies cross cards.
     for(int c=0;c<2;++c){flash::Launch g;g.op="tp_push";g.label=l.label+".tp_push";g.card=c;g.inputs={y};g.outputs={part};both.push_back(std::move(g));}
     for(int c:{1,0}){flash::Launch g;g.op="tp_wait";g.label=l.label+".tp_wait";g.card=c;both.push_back(std::move(g));}
     for(int c=0;c<2;++c){flash::Launch g;g.op="tp_select";g.label=l.label+".tp_select";g.card=c;g.inputs={part,ids};g.outputs={y};g.parameter=c|by_slot;both.push_back(std::move(g));}
    }
   }
   p.launches=std::move(both);for(auto& b:p.buffers)b.card=-1;
  }
  engine=std::make_unique<Engine>(*weights,a,p);selection_observed_sha256=engine->sealed_selection.observed_sha256;record_host_memory(a.output,"before_load");engine->initialize();
  // Exact F32 activation mode is admitted only on the paths that have F32 variants.
  if(a.f32_activations)require(!engine->v3_active&&!engine->kio_active&&!engine->prepare_async&&!engine->split_head()&&engine->sealed_selection.choices.at("probe")=="off"&&a.gsq_packed&&a.draft_rank==0,"exact F32 activations: unsupported optional path/selection");
  if(engine->split_head())head_runtime=std::make_unique<p105::Runtime>(*engine);
  if(a.rank==0)banks(*engine);else {engine->prepare_plan();engine->prepare_commands();}
  if(a.prefill_rows) {
   engine->prefill_allocate();
   require(!a.prefill_shared.empty(),"batched prefill requires --prefill-shared");
   prefill_map_bytes=prefill::bytes(size_t(a.prefill_rows),engine->stream_bytes());
   prefill_fd=::open(a.prefill_shared.c_str(),O_RDWR|O_NOFOLLOW);require(prefill_fd>=0,"prefill shared open");struct stat pst{};
   require(!fstat(prefill_fd,&pst)&&size_t(pst.st_size)==prefill_map_bytes,"prefill shared extent");
   prefill_map=mmap(nullptr,prefill_map_bytes,PROT_READ|PROT_WRITE,MAP_SHARED,prefill_fd,0);require(prefill_map!=MAP_FAILED,"prefill shared mmap");
   prefill_base=static_cast<uint8_t*>(prefill_map);const auto& h=*reinterpret_cast<const prefill::Header*>(prefill_base);
   require(h.magic==prefill::magic&&h.version==prefill::version&&h.rows==uint32_t(a.prefill_rows)&&h.stream_bytes==engine->stream_bytes(),"prefill shared header");
  }
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
  std::optional<ownrt::wavefront::Ledger> wave_ledger;
  std::unique_ptr<StageCheckpoint> wave_checkpoint;std::ofstream wave_trace;size_t wave_trace_rows=0,wave_trace_omitted=0;int wave_output=-1;
  std::unique_ptr<ring_next::Dispatcher> ring_dispatcher;
  OperatorStatePartition operator_partition;std::set<Allocation> before_provider;
  if(a.pipeline_draft_partition&&a.pipeline_first())for(const auto& [id,owner]:engine->allocations)before_provider.insert(id);
  if(a.pipeline_live_draft&&a.pipeline_first())provider=std::make_unique<mtp36::DraftRuntime>(*engine);
  if(a.pipeline_draft_partition&&provider)operator_partition=admit_operator_partition(*engine,before_provider,provider->live_mutable_inventory(),provider->live_pinned_inventory(),provider->live_private_recursive_inventory());
  if(a.pipeline_wavefront){
   wave_ledger.emplace(a.pipeline_final(),engine->p.g.context,engine->p.g.vocab);
   wave_checkpoint=std::make_unique<StageCheckpoint>(*engine,a.pipeline_wavefront_verify,provider?provider->live_pinned_inventory():std::vector<Allocation>{},operator_partition);
   wave_trace.open(a.output/"wavefront.jsonl");require(bool(wave_trace),"wavefront trace open");
  }
  if(a.pipeline_ring){
   ownrt::ring_next::Digest request{};for(size_t i=0;i<request.size();++i)request[i]=uint8_t(std::stoul(a.pipeline_ring_request_sha256.substr(2*i,2),nullptr,16));
   ring_dispatcher=std::make_unique<ring_next::Dispatcher>(*engine,image,operator_partition,static_cast<uint8_t*>(mapping),shared_bytes,a.pipeline_ring_verify,0,request,provider.get());
  }
#ifndef OWN_RT_HOST_ONLY
  if(a.rank==0&&!a.gsq_packed)weights->warm_lookups();
  else if(a.rank==0&&!a.mini){const char* v=std::getenv("OWNRT_LOOKUP_COPY");if(!v||std::string(v)!="0")weights->copy_lookups();}
#endif
  save(a.output/"lookup-residency.json",weights->residency);
  {cpu_set_t cpus;CPU_ZERO(&cpus);require(!sched_getaffinity(0,sizeof cpus,&cpus),"affinity receipt");double load=0;getloadavg(&load,1);std::ostringstream o;o<<"{\"cpu_affinity\":[";bool comma=false;for(int i=0;i<CPU_SETSIZE;++i)if(CPU_ISSET(i,&cpus)){o<<(comma?",":"")<<i;comma=true;}o<<"],\"load_average_1m\":"<<load<<"}";save(a.output/"host-environment.json",o.str());}
  record_host_memory(a.output,"after_load");
  if(a.mtp&&a.rank==a.draft_rank&&!a.pipeline_live_draft)provider=std::make_unique<mtp36::DraftRuntime>(*engine);
  save(a.output/"census.json",engine->dev(0).arena.census());
  engine->bracket_weights_locked=true;
  save(a.output/"loaded-arena-descriptors.txt",engine->bracket_arena_descriptors());
  if(a.pipeline_enabled()){
   require(engine->stream_bytes()>0&&engine->stream_bytes()<=slot_bytes,"pipeline stream slot extent");
   std::ostringstream o;o<<"{\"schema\":\"ownrt.pipeline-stage.v1\",\"stage_id\":"<<a.pipeline_stage<<",\"stage_count\":"<<a.pipeline_boundaries.size()-1
    <<",\"begin\":"<<a.pipeline_boundaries[a.pipeline_stage]<<",\"end\":"<<a.pipeline_boundaries[a.pipeline_stage+1]
    <<",\"first\":"<<(a.pipeline_first()?"true":"false")<<",\"final\":"<<(a.pipeline_final()?"true":"false")
    <<",\"activation_dtype\":\"F32\",\"stream_bytes\":"<<engine->stream_bytes()<<",\"boundaries\":[";
   for(size_t i=0;i<a.pipeline_boundaries.size();++i)o<<(i?",":"")<<a.pipeline_boundaries[i];o<<"],\"mode\":"<<ownrt::quote(a.pipeline_ring?(a.pipeline_ring_live_draft?"verified-ring-live":"verified-ring"):(a.pipeline_wavefront?"wavefront":"target-only"))<<",\"speculation_enabled\":"<<((a.pipeline_wavefront||a.pipeline_ring)?"true":"false")<<",\"inactive_alternate_banks\":[";bool comma=false;for(const auto& [name,id]:engine->state_spares){o<<(comma?",":"")<<ownrt::quote(name);comma=true;}o<<"]";if(a.pipeline_ring)o<<",\"ring_capacity\":2,\"depth\":2,\"ring_epoch\":0,\"ring_request_sha256\":"<<ownrt::quote(a.pipeline_ring_request_sha256);if(a.pipeline_ring_live_draft)o<<",\"provider_borrow_mode\":\"quiescent-target\"";o<<"}";save(a.output/"pipeline-stage.json",o.str());
  }
  Reply ready{};ready.rank=a.rank;if(a.pipeline_enabled()){ready.reserved[0]=a.pipeline_stage;ready.reserved[1]=a.pipeline_final();ready.bytes=int32_t(engine->stream_bytes());}transfer(a.channel,&ready,sizeof ready,true,a.seconds);
  ownrt::live_draft::Sequence live_draft_sequence;
  Candidate c;int sequence=0,accepted=0;bool async_half_ready=false;int async_half_position=-1,async_half_token=-1;V3Boundary v3state;
  auto execute=[&](const Request& r)->Reply {
   if(a.rank==1)engine->reply_report.before(r.op);
   auto received=std::chrono::steady_clock::now();
   Reply response{};response.sequence=r.sequence;response.rank=a.rank;
   if(a.pipeline_ring&&ring_dispatcher->handles_command(r.op)){auto reply=ring_dispatcher->execute(r);if(r.op==ownrt::ring_next::wire::accept_op&&r.fixture>0)++accepted;return reply;}
   if(a.pipeline_ring)ring_dispatcher->boundary();
   if(a.pipeline_wavefront&&(r.op==ownrt::wavefront::row_op||r.op==ownrt::wavefront::commit_op||r.op==ownrt::wavefront::abort_op)){
    auto& ledger=*wave_ledger;auto& checkpoint=*wave_checkpoint;auto started=std::chrono::steady_clock::now();double checkpoint_ms=0;int ticket=r.sequence;bool tentative=false;
    if(r.op==ownrt::wavefront::row_op){
     require(r.speculative==0||r.speculative==1,"wavefront tentative flag");
     ledger.begin({r.sequence,r.token,r.position,r.fixture,r.speculative==1});tentative=r.speculative==1;
     require(!c.pending,"wavefront row overwrites candidate");
     if(tentative){auto before=std::chrono::steady_clock::now();checkpoint.begin(static_cast<uint8_t*>(mapping));checkpoint_ms=Engine::ms(before);}
     Request actual=r;actual.op=half;actual.speculative=0; // independent checkpoint owns speculation; legacy image stays inert
     response=half_step(*engine,c,actual,static_cast<uint8_t*>(mapping),image);
     require(!c.cancelled&&!c.speculative,"wavefront legacy speculation unexpectedly active");wave_output=response.token;
    }else{
     ticket=r.speculative;ledger.match(ticket,r.token,r.position,r.fixture);tentative=ledger.candidate().tentative;
     require(c.pending&&!c.cancelled&&!c.speculative&&c.position==r.position&&c.fixture==r.fixture,"wavefront candidate identity");
     if(r.op==ownrt::wavefront::commit_op){
      require(checkpoint.active()==tentative,"wavefront checkpoint commit identity");
      if(tentative){auto before=std::chrono::steady_clock::now();checkpoint.commit();checkpoint_ms=Engine::ms(before);}
      publish(*engine,c);ledger.commit(ticket,r.token,r.position,r.fixture,wave_output);if(c.fixture>0)++accepted;
      if(a.pipeline_live_draft&&a.pipeline_final()){
       auto* bytes=static_cast<uint8_t*>(mapping);require(reverse_ready(bytes).position_plus_one==uint32_t(r.position+1),"live draft final hidden position");
       ownrt::live_draft::Handoff h;h.bytes=int32_t(engine->stream_bytes());h.position=r.position;h.final_stage=a.pipeline_stage;h.stages=int32_t(a.pipeline_boundaries.size()-1);
       h.row_ticket=ticket;h.commit_sequence=r.sequence;h.input_token=r.token;h.head=r.fixture>0;h.next_token=h.head?wave_output:-1;
       std::vector<uint8_t> raw(bytes+reverse_offset,bytes+reverse_offset+h.bytes);const auto sha=hash(raw);require(sha.size()==h.hidden_sha256.size(),"live hidden SHA size");std::memcpy(h.hidden_sha256.data(),sha.data(),sha.size());
       ownrt::live_draft::validate(h,int(engine->stream_bytes()),int(a.pipeline_boundaries.size()-1),engine->p.g.vocab);
       std::memcpy(bytes+ownrt::live_draft::header_offset,&h,sizeof h);response.bytes=h.bytes;response.token=h.next_token;
      }
     }else{
      require(tentative&&checkpoint.active(),"wavefront abort requires tentative checkpoint");
      auto before=std::chrono::steady_clock::now();checkpoint.abort();checkpoint_ms=Engine::ms(before);
      require(engine->integer(0,"position")==r.position,"wavefront aborted device position");ledger.abort(ticket,r.token,r.position,r.fixture);
     }
     c={};wave_output=-1;
    }
    response.sequence=r.sequence;response.rank=a.rank;response.reserved[0]=a.pipeline_stage;response.reserved[1]=a.pipeline_final();response.busy_ms=Engine::ms(started);
    response.redo_ms=std::chrono::duration<double>(received.time_since_epoch()).count();response.reserved_ms=std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
    if(wave_trace_rows<size_t(a.pipeline_wavefront_trace_limit)){
     wave_trace<<"{\"schema\":\"ownrt.wavefront-row.v1\",\"stage\":"<<a.pipeline_stage<<",\"sequence\":"<<r.sequence<<",\"ticket\":"<<ticket<<",\"op\":"<<r.op<<",\"position\":"<<r.position<<",\"token\":"<<r.token<<",\"fixture\":"<<r.fixture<<",\"tentative\":"<<(tentative?"true":"false")<<",\"output\":"<<response.token<<",\"bytes\":"<<response.bytes<<",\"checkpoint_ms\":"<<checkpoint_ms<<",\"wall_ms\":"<<response.busy_ms<<",\"committed_position\":"<<ledger.position()<<",\"pending\":"<<(ledger.pending()?"true":"false")<<"}\n";wave_trace.flush();require(bool(wave_trace),"wavefront trace write");++wave_trace_rows;
    }else ++wave_trace_omitted;
    return response;
   }
   if(a.pipeline_live_draft&&r.op==ownrt::live_draft::step_op){
    require(a.pipeline_first()&&provider&&r.speculative==0&&(r.fixture==0||r.fixture==1),"live draft command owner/flags");
    wave_ledger->boundary();require(!c.pending&&!wave_checkpoint->active()&&!provider->submitting(),"live draft requires resolved target checkpoint");
    auto* bytes=static_cast<uint8_t*>(mapping);ownrt::live_draft::Handoff h;std::memcpy(&h,bytes+ownrt::live_draft::header_offset,sizeof h);
    ownrt::live_draft::validate(h,int(engine->stream_bytes()),int(a.pipeline_boundaries.size()-1),engine->p.g.vocab);
    live_draft_sequence.admit(h,r.position,r.token,r.fixture,engine->p.g.vocab);
    require(engine->integer(0,"position")>=r.position&&provider->live_position()+1==r.position,"live draft target/canonical prefix");
    std::vector<uint8_t> hidden(bytes+slot_bytes,bytes+slot_bytes+engine->stream_bytes());
    require(hash(hidden)==std::string(h.hidden_sha256.data(),h.hidden_sha256.size()),"live draft hidden hash mismatch");
    auto start=std::chrono::steady_clock::now();const double gpu=engine->gemv_ms+engine->nongemv_ms;
    response.token=provider->live_step(r.token,r.position,r.fixture!=0,hidden.data(),hidden.size());
    live_draft_sequence.complete(h,provider->live_position());response.busy_ms=Engine::ms(start);response.gpu_ms=engine->gemv_ms+engine->nongemv_ms-gpu;
    response.reserved[0]=a.pipeline_stage;response.reserved[1]=a.pipeline_final();return response;
   }
   if(a.pipeline_wavefront){wave_ledger->boundary();require(!c.pending&&!wave_checkpoint->active(),"wavefront boundary unresolved candidate");wave_checkpoint->attest(*wave_ledger);}
   bool completing_redo=(a.pipeline_wavefront||a.pipeline_ring)?false:image.before_command(r.op==half&&!r.speculative,r.position,r.token);
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
   else if(r.op==prefill::op){
    require(prefill_base&&!c.pending&&!async_half_ready&&r.token>=1&&r.token<=a.prefill_rows&&(r.fixture==0||r.fixture==1)&&!r.speculative,"prefill command");
    const size_t S=engine->stream_bytes(),R=size_t(a.prefill_rows);auto before=std::chrono::steady_clock::now();
    const auto& h=*reinterpret_cast<const prefill::Header*>(prefill_base);
    if(a.rank==0)engine->prefill_chunk(r.position,h.tokens,r.token,nullptr,prefill::forward(prefill_base,r.fixture,R,S));
    else engine->prefill_chunk(r.position,nullptr,r.token,prefill::forward(prefill_base,r.fixture,R,S),prefill::reverse(prefill_base,r.fixture,R,S));
    response.busy_ms=Engine::ms(before);response.bytes=int32_t(size_t(r.token)*S);
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
   else if(r.op==dump){require(!c.pending,"dump uncommitted state");image.boundary();if(provider)provider->flush_depth_probe();state_dump(*engine,r.position);if(a.pipeline_live_draft&&provider)provider->live_dump(engine->a.output/("state-"+std::to_string(r.position)+".draft"));if(a.pipeline_ring)ring_dispatcher->attest(engine->a.output/("state-"+std::to_string(r.position)+".ring-state.json"),r.position);if(a.pipeline_wavefront)wave_checkpoint->attest(*wave_ledger,engine->a.output/("state-"+std::to_string(r.position)+".wavefront-state.json"),r.position);if(engine->a.tp_replicate)tp_compare(*engine,a.output/"tp-replicate-compare.json");if(r.position==2147483647)request_state_inventory(*engine);}
   else if(r.op==11){image.boundary();v3state.reset();
    const auto metadata=a.output/("reset-"+std::to_string(r.sequence)+".txt");
    if(a.pipeline_persistent_requests){require(!r.token&&!r.position&&!r.fixture&&!r.speculative,"persistent reset zero payload");persistent_reset(*engine,c,provider.get(),*wave_checkpoint,*wave_ledger,live_draft_sequence,a.output,metadata,accepted,r.sequence,static_cast<uint8_t*>(mapping),shared_bytes,wave_trace,wave_trace_rows,wave_trace_omitted);wave_output=-1;}
    else request_reset(*engine,c,provider.get(),metadata,accepted);
    accepted=0;
   }
   else if(r.op==13){require(!async_half_ready,"pending half");v3state.reset();bracket_boundary(*engine,c,provider.get(),image,a.output/("bracket-"+std::to_string(r.sequence)+".txt"),accepted);async_half_position=async_half_token=-1;}
   #ifdef OWN_RT_HOST_ONLY
   else if(r.op==12){require(a.rank==0&&c.pending&&c.speculative,"negative control ownership");image.corrupt_protected_for_gate(r.token);}
#endif
   else if(r.op==16){require(!c.pending&&!async_half_ready,"redirect with unresolved candidate");require(!provider||!provider->submitting(),"redirect draft publication pending");image.boundary();request_redirect(*engine,provider.get(),a.output/("redirect-"+std::to_string(r.sequence)+".txt"));}
   else if(r.op==fail)throw std::runtime_error("injected rank failure");
   else if(r.op==stall){auto until=std::chrono::steady_clock::now()+std::chrono::seconds(a.seconds);while(std::chrono::steady_clock::now()<until){pipeline_cancel_check();poll(nullptr,0,10);}throw std::runtime_error("bounded injected stall");}
   else throw std::runtime_error("unknown rank command");
   if(a.rank==1)engine->reply_report.after(r.op);
   response.redo_ms=std::chrono::duration<double>(received.time_since_epoch()).count();
   response.reserved_ms=std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
   if(a.rank==0&&(r.op==pipeline::accept||r.op==rollback))p150::record(r.op==pipeline::accept?"accept":"rollback",r.position,false,received);
   if(a.pipeline_enabled()){response.reserved[0]=a.pipeline_stage;response.reserved[1]=a.pipeline_final();}
   return response;
  };
  for(;;){Request r{};transfer(a.channel,&r,sizeof r,false,a.seconds);require(r.sequence==++sequence,"command sequence");
   if(a.pipeline_enabled()){
    require(r.reserved[0]==a.pipeline_stage&&r.reserved[1]==int(a.pipeline_final()),"pipeline command stage identity");
    if(a.pipeline_ring)require(ring_dispatcher->handles_command(r.op)||((r.op==dump||r.op==finish)&&!r.speculative),"ring command admission");
    else if(a.pipeline_wavefront)require(r.op==ownrt::wavefront::row_op||r.op==ownrt::wavefront::commit_op||r.op==ownrt::wavefront::abort_op||(a.pipeline_live_draft&&a.pipeline_first()&&r.op==ownrt::live_draft::step_op&&!r.speculative)||(a.pipeline_persistent_requests&&r.op==11&&!r.speculative)||((r.op==dump||r.op==finish)&&!r.speculative),"wavefront command admission");
    else require((r.op==half||r.op==pipeline::accept||r.op==dump||r.op==finish)&&!r.speculative,"general pipeline target-only command");
   }
   if(r.op==finish){if(a.pipeline_ring)ring_dispatcher->attest();if(a.pipeline_wavefront){wave_checkpoint->attest(*wave_ledger);save(a.output/"wavefront-trace-summary.json","{\"records\":"+std::to_string(wave_trace_rows)+",\"omitted\":"+std::to_string(wave_trace_omitted)+"}");}if(a.rank==1)engine->reply_report.flush();require(!c.pending,"finish with unresolved candidate");require(!v3state.ready,"finish with a pending V3 boundary");image.boundary();if(provider)provider->flush_depth_probe();if(provider&&a.finish_dump)provider->dump_all_state(engine->a.output/"draft-final-state");if(a.pipeline_live_draft&&provider)provider->live_dump(engine->a.output/"draft-final-state-sealed");break;}
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
      backend.prefill=prefill_base;backend.prefill_rows=a.prefill_rows;backend.prefill_stream=a.prefill_rows?engine->stream_bytes():0;
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
   if(a.pipeline_ring)ring_dispatcher->reply_published(r.op);
   if(a.rank==1&&(r.op==half||(a.pipeline_wavefront&&r.op==ownrt::wavefront::row_op)))engine->reply_report.published();
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
 if(prefill_map!=MAP_FAILED)munmap(prefill_map,prefill_map_bytes);if(prefill_fd>=0)::close(prefill_fd);
 std::ostringstream o;o<<"{\"schema\":\"packet32.rank.v1\",\"passed\":"<<(error.empty()?"true":"false")<<",\"rank\":"<<a.rank<<",\"error\":"<<ownrt::quote(error)<<",\"arithmetic\":"<<ownrt::quote(arithmetic::version)<<",\"device_executed\":"
#ifdef OWN_RT_HOST_ONLY
 <<"false"
#else
 <<"true"
#endif
 <<",\"selection_sha256\":"<<ownrt::quote(selection_observed_sha256)<<",\"teardown\":[";for(size_t i=0;i<teardown.size();++i)o<<(i?",":"")<<teardown[i];o<<"]}";save(a.output/"receipt.json",o.str());return error.empty()?0:1;
}
