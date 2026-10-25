#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
// Linux process-shared single-producer/single-consumer mailbox. The futex word
// is the release/acquire publication fence; wakeups are hints, never state.
#include <linux/futex.h>
#include <sys/syscall.h>
#include <atomic>
#include <functional>
#include "stage2/packet194-expert-diet-engine/host_spin.hpp"
namespace pipeline::native38 {
struct alignas(64) Mailbox {
 alignas(4) uint32_t request_sequence=0,reply_sequence=0,abort=0,draft_sequence=0;
 Request request{}; Reply reply{};
};
static_assert(sizeof(Mailbox)<4096-256);
static_assert(std::atomic<uint32_t>::is_always_lock_free);
inline uint32_t load(uint32_t& n){return __atomic_load_n(&n,__ATOMIC_ACQUIRE);}
inline void publish(uint32_t& n,uint32_t value){__atomic_store_n(&n,value,__ATOMIC_RELEASE);::syscall(SYS_futex,&n,FUTEX_WAKE,1,nullptr,nullptr,0);}
inline double clock_now(){return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();}
inline void wait_change(uint32_t& n,uint32_t old,Mailbox& m,int seconds,const std::function<void()>& cancel){
 require(p56x::wait([&]{return load(n)!=old;},[&]{cancel();require(!load(m.abort),"native peer failed");},
            std::chrono::steady_clock::now()+std::chrono::seconds(seconds)),"bounded native mailbox timeout");
 cancel();require(!load(m.abort),"native peer failed");
}
inline void abort(Mailbox& m){publish(m.abort,1);::syscall(SYS_futex,&m.request_sequence,FUTEX_WAKE,1,nullptr,nullptr,0);::syscall(SYS_futex,&m.reply_sequence,FUTEX_WAKE,1,nullptr,nullptr,0);}
struct Trace {int rank;Request command;Reply reply;double sent;};
struct Backend {
 Mailbox& m; uint8_t* shared;int seconds;std::function<Reply(const Request&)> execute;std::function<void()> cancel;
 std::function<void(const Request&)> before_remote_wait;
 bool correction_probe=false,split_replay=false;
 uint32_t seq;bool pending[2]={false,false};Reply local{};Request commands[2]{};double sent[2]={};std::vector<Trace> trace;size_t stream_bytes=0;
 // Batched prefill transport (pipeline::prefill layout); null when the rank runs without --prefill-rows.
 uint8_t* prefill=nullptr;int prefill_rows=0;size_t prefill_stream=0;
 Backend(Mailbox& box,uint8_t* mem,int timeout,std::function<Reply(const Request&)> fn,std::function<void()> stop):m(box),shared(mem),seconds(timeout),execute(fn),cancel(stop),seq(load(m.request_sequence)){}
 void start(int rank,int op,int token=0,int position=0,int fixture=0,int speculative=0){
  require(!pending[rank],"native double pending");cancel();require(!load(m.abort),"native peer failed");Request r{op,token,position,fixture,speculative,0,{0,0}};commands[rank]=r;sent[rank]=clock_now();pending[rank]=true;
  if(rank==0){if(op==draft)r.sequence=position;commands[rank]=r;local=execute(r);if(op==half)stream_bytes=local.bytes;}
  else {require(load(m.reply_sequence)==seq,"native outstanding mailbox");require(seq<UINT32_MAX,"native sequence overflow");r.sequence=int32_t(seq+1);commands[rank]=r;m.request=r;publish(m.request_sequence,++seq);}
 }
 Reply wait(int rank){require(pending[rank],"native wait idle");Reply r;
  if(rank==0)r=local;else{if(before_remote_wait)before_remote_wait(commands[rank]);uint32_t seen=load(m.reply_sequence);p150::measure("remote_reply_wait",commands[rank].position,false,[&]{if(seen!=seq)wait_change(m.reply_sequence,seen,m,seconds,cancel);});require(load(m.reply_sequence)==seq,"native reply sequence");r=m.reply;}
  require(!load(m.abort),"native peer failed");require(!r.status&&!r.error,"native failed operation");pending[rank]=false;trace.push_back({rank,commands[rank],r,sent[rank]});return r;
 }
 Reply call(int rank,int op,int token=0,int position=0,int fixture=0,int speculative=0){start(rank,op,token,position,fixture,speculative);return wait(rank);}
 void handover(){require(!pending[1]&&stream_bytes&&stream_bytes<=slot_bytes,"native handover ownership");std::memcpy(shared+slot_bytes,shared,stream_bytes);}
};
inline void worker(Mailbox& m,int seconds,const std::function<Reply(const Request&)>& execute,const std::function<void()>& cancel,const std::function<void(const Request&)>& published={},const std::function<void()>& finish_reports={}){
 uint32_t seen=load(m.reply_sequence);
 for(;;){if(load(m.request_sequence)==seen)wait_change(m.request_sequence,seen,m,seconds,cancel);cancel();require(!load(m.abort),"native peer failed");uint32_t next=load(m.request_sequence);require(next==seen+1,"native worker sequence");Request r=m.request;
  if(r.op==0){if(finish_reports)finish_reports();m.reply={};publish(m.reply_sequence,next);return;}
  m.reply=execute(r);publish(m.reply_sequence,next);if(published)published(r);seen=next;
 }
}
// prefill: rows per batched-prefill chunk requested for this request (0 = token-by-token prompt).
inline bool early_rank1(){static const bool on=[]{const char* e=std::getenv("OWNRT_EARLY_RANK1");return !e||e[0]!='0';}();return on;}
struct Config {int draft_rank=1,mode=0,count=0,overlap=1,dumps=0,vocab=31,prefill=0;std::vector<int> prompt,script,eos;};
inline Config config(const fs::path& path,int context,int vocab){
 std::ifstream f(path);Config c;c.vocab=vocab;size_t np=0,ns=0,ne=0;require(bool(f>>c.mode>>c.count>>c.overlap>>c.dumps>>np>>ns>>ne),"native config header");
 require(c.mode>=0&&c.mode<=3&&c.count>0&&np>0&&np<=size_t(context)&&size_t(c.count)<=size_t(context)-np&&ns<=size_t(context)&&ne<=16&&(c.overlap==0||c.overlap==1)&&(c.dumps==0||c.dumps==1),"native config bounds");
 for(auto pair:{std::pair{&c.prompt,np},std::pair{&c.script,ns},std::pair{&c.eos,ne}}){pair.first->resize(pair.second);for(int& x:*pair.first){require(bool(f>>x),"native config tokens");require(x>=((pair.first==&c.script)?-1:0)&&x<vocab,"native config token bounds");}}
 // Optional trailer "prefill <rows>"; any other trailing data is refused.
 std::string extra;if(f>>extra){require(extra=="prefill"&&bool(f>>c.prefill)&&c.prefill>=0&&c.prefill<=64,"native config prefill trailer");require(!(f>>extra),"native config trailing data");}
 return c;
}
struct Row {int token;double stamp;};
struct Guess {int position,guess,actual;bool hit;double cycle_ms;};
struct DraftRow {int position,sequence,guess,error,actual=-1,hit=-1;double wall_ms,gpu_ms,wait_ms,started,half_started=0,completed=0,cycle_ms=-1;};
struct Result {std::vector<DraftRow> draft_rows;std::vector<int> guess_sequence;std::vector<int> tokens;std::vector<Row> rows;std::vector<Guess> guesses;int guesses_count=0,hits=0,misses=0,no_guess=0;double redo_ms=0,prompt_ms=0,start=0,end=0;};
inline int ngram(const std::vector<int>& h){for(int n:{2,1}){if(int(h.size())<n)continue;for(int s=int(h.size())-n-1;s>=0;--s)if(std::equal(h.begin()+s,h.begin()+s+n,h.end()-n))return h[s+n];}return -1;}
// Rank-0-only append stream. No shared-map ABI change, device copy or fsync.
// One fresh file per native request. A stale path is an error, never truncated.
class ConfirmedStream {
  int fd_=-1;
  void line(const std::string& text) {
    size_t done=0;
    while(done<text.size()) {
      auto n=::write(fd_,text.data()+done,text.size()-done);
      if(n<0&&errno==EINTR)continue;
      require(n>0,"confirmed token stream write");done+=size_t(n);
    }
  }
public:
  ConfirmedStream()=default;
  ConfirmedStream(const ConfirmedStream&)=delete;
  ConfirmedStream& operator=(const ConfirmedStream&)=delete;
  ~ConfirmedStream(){if(fd_>=0)::close(fd_);}
  void begin(const fs::path& path,int request_sequence,int count,int vocab) {
    require(fd_<0,"confirmed token stream already open");
    fd_=::open(path.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600);
    require(fd_>=0,"confirmed token stream create");
    line("{\"type\":\"begin\",\"schema\":\"sc117.confirmed-tokens.v1\",\"request_sequence\":"+
         std::to_string(request_sequence)+",\"limit\":"+std::to_string(count)+
         ",\"vocab\":"+std::to_string(vocab)+"}\n");
  }
  void token(size_t index,int token,double target_completed) {
    std::ostringstream out;out.precision(17);
    out<<"{\"type\":\"token\",\"index\":"<<index<<",\"token_id\":"<<token
       <<",\"target_completed_monotonic\":"<<target_completed<<"}\n";
    line(out.str()); // write(2) makes a full line visible; no userspace buffering.
  }
  void end(size_t count) {
    line("{\"type\":\"end\",\"count\":"+std::to_string(count)+"}\n");
    int fd=fd_;fd_=-1;require(::close(fd)==0,"confirmed token stream close");
  }
};
using EmitConfirmed=std::function<void(size_t,int,double)>;
inline Result run(Backend& b,const Config& c,const EmitConfirmed& emit={}){
 Result out;out.start=clock_now();std::vector<int> history;bool draft_pending=false;double issued_draft_at=0;uint32_t pending_draft_sequence=0;size_t script_index=0;int length=int(c.prompt.size());
 auto fixture=[&](int p){return std::max(0,p-length+2);};
 auto half_start=[&](int rank,int token,int p,bool spec=false){b.start(rank,half,token,p,fixture(p),spec);};
 double rank1_started_at=0; // >0: rank 1's half for the coming position was already issued
 bool defer_draft=false;     // a decode miss: the draft is issued after rank 0's redo
 // Batched prefill bulk: target positions 0..N-1 (N = length-2) in chunks on both ranks, then the original scalar
 // loop resumes at p=N in exactly the state its iteration N-1 leaves: rank 0 has run and accepted HALF(N), rank 1
 // is committed through N-1, and the draft has consumed confirmed positions 1..N with its publication for N+1 pending.
 const int rows=b.prefill&&c.prefill>0?std::min(c.prefill,b.prefill_rows):0;
 const int bulk=rows&&c.draft_rank==0&&c.overlap==1&&(c.mode==0||c.mode==3)&&length-2>=rows?length-2:0;
 int first=0;
 if(bulk) {
  auto* header=reinterpret_cast<pipeline::prefill::Header*>(b.prefill);
  require(header->magic==pipeline::prefill::magic&&header->rows==uint32_t(b.prefill_rows)&&header->stream_bytes==b.prefill_stream,"native prefill header");
  const int chunks=(bulk+rows-1)/rows;
  auto count=[&](int k){return std::min(rows,bulk-k*rows);};
  auto rank0_chunk=[&](int k){std::memcpy(header->tokens,c.prompt.data()+k*rows,size_t(count(k))*4);b.call(0,pipeline::prefill::op,count(k),k*rows,k%2);};
  // Draft replay for chunk k: confirmed position q+1 takes rank 1's final row of position q, in order.
  auto drafts=[&](int k){if(c.mode!=3)return;
   const auto* rev=pipeline::prefill::reverse(b.prefill,k%2,size_t(b.prefill_rows),b.prefill_stream);
   for(int r=0;r<count(k);++r){const int q=k*rows+r;if(q+1>=bulk)break;
    std::memcpy(b.shared+reverse_offset,rev+size_t(r)*b.prefill_stream,b.prefill_stream);
    __atomic_store_n(&reverse_ready(b.shared).position_plus_one,uint32_t(q+1),__ATOMIC_RELEASE);
    b.call(0,draft,c.prompt[q+1],q+1,0,0);}};
  rank0_chunk(0);
  for(int k=0;k<chunks;++k){
   b.start(1,pipeline::prefill::op,count(k),k*rows,k%2);
   if(k>0)drafts(k-1);
   if(k+1<chunks)rank0_chunk(k+1);
   b.wait(1);
  }
  drafts(chunks-1);
  for(int q=0;q<bulk;++q)history.push_back(c.prompt[q]);
  // Seam: iteration N-1's rank-0 HALF(N), its draft for confirmed position N, then rank 0's accept.
  half_start(0,c.prompt[bulk],bulk);b.wait(0);
  if(c.mode==3){
   const auto* rev=pipeline::prefill::reverse(b.prefill,(chunks-1)%2,size_t(b.prefill_rows),b.prefill_stream);
   std::memcpy(b.shared+reverse_offset,rev+size_t(count(chunks-1)-1)*b.prefill_stream,b.prefill_stream);
   __atomic_store_n(&reverse_ready(b.shared).position_plus_one,uint32_t(bulk),__ATOMIC_RELEASE);
   b.start(c.draft_rank,draft,c.prompt[bulk],bulk,int(bulk+1>=length),1);pending_draft_sequence=b.seq;issued_draft_at=b.sent[c.draft_rank];b.wait(0);draft_pending=true;
  }
  b.call(0,accept);
  first=bulk;
 } else {half_start(0,c.prompt[0],0);b.wait(0);b.call(0,accept);}
 for(int p=first;p<length+c.count-1;++p){
  double cycle=clock_now();int token=p<length?c.prompt[p]:out.tokens.back();history.push_back(token);int draft_guess=-1;
  uint32_t expected_draft=0;double draft_started=0;
  if(draft_pending){expected_draft=c.draft_rank==0?uint32_t(p):pending_draft_sequence;draft_started=issued_draft_at;if(c.draft_rank==1&&b.pending[1])b.wait(1);draft_pending=false;}
  double half_started;
  if(rank1_started_at>0){half_started=rank1_started_at;rank1_started_at=0;} // started at the end of the last iteration
  else{p150::measure("handoff_host",p,false,[&]{b.handover();});half_start(1,token,p);half_started=clock_now();}
  if(expected_draft){double waiting=clock_now();uint32_t seen=load(b.m.draft_sequence);p150::measure("draft_wait",p,false,[&]{if(seen!=expected_draft)wait_change(b.m.draft_sequence,seen,b.m,b.seconds,b.cancel);});p150::measure("draft_zero_wait",p,true,[&]{if(b.split_replay)require(load(b.m.draft_sequence)==expected_draft,"p150 satisfied draft wait");});
   require(load(b.m.draft_sequence)==expected_draft,"native draft publication sequence");
   struct Publication{int32_t valid,position,token,error;uint64_t elapsed_ns;int32_t sequence,reserved;double gpu_ms;};Publication v{};std::memcpy(&v,b.shared+2*slot_bytes,sizeof v);
   if(v.valid==1&&v.position==p+1&&!v.error&&v.sequence==int32_t(expected_draft)&&v.token>=0&&v.token<c.vocab)draft_guess=v.token;
   out.draft_rows.push_back({v.position,v.sequence,draft_guess,v.error,-1,-1,v.elapsed_ns/1e6,v.gpu_ms,(clock_now()-waiting)*1000,draft_started,half_started});
  }
  bool more=p+1<length+c.count-1,known=more&&p+1<length,pending=false;int guess=-1;
  if(known&&c.overlap){half_start(0,c.prompt[p+1],p+1);pending=true;}
  else if(more&&!known){
   if(c.mode==1)guess=ngram(history);else if(c.mode==2){if(script_index<c.script.size())guess=c.script[script_index];++script_index;}else if(c.mode==3)guess=draft_guess;
   out.guess_sequence.push_back(guess);if(guess<0)++out.no_guess;else{++out.guesses_count;half_start(0,guess,p+1,true);pending=true;}
  }
  Reply result=b.wait(1);double stamp=clock_now();b.call(1,accept);
  if(c.mode==3&&!out.draft_rows.empty()){auto& dr=out.draft_rows.back();dr.actual=fixture(p)>0?result.token:c.prompt[p+1];dr.hit=guess>=0&&fixture(p)>0?int(guess==result.token):-1;dr.completed=stamp;if(out.draft_rows.size()>1&&!out.rows.empty()){auto& prev=out.draft_rows[out.draft_rows.size()-2];prev.cycle_ms=(stamp-prev.completed)*1000;}}
  if(fixture(p)>0){out.tokens.push_back(result.token);out.rows.push_back({result.token,stamp});if(out.rows.size()==1)out.prompt_ms=(stamp-out.start)*1000;
   if(std::find(c.eos.begin(),c.eos.end(),result.token)!=c.eos.end()){if(pending){b.wait(0);b.call(0,rollback);}if(emit)emit(out.tokens.size(),out.tokens.back(),out.rows.back().stamp);break;}
  }
  if(!more){if(emit)emit(out.tokens.size(),out.tokens.back(),out.rows.back().stamp);break;}
  bool early_accept=false;
  if(c.mode==3){int confirmed=known?c.prompt[p+1]:out.tokens.back();
   if(c.draft_rank==0&&pending){b.wait(0);if(known||guess==confirmed){b.call(0,accept);early_accept=true;}}
   // Rank 1's next half needs only rank 0's accepted half, the draft only rank 1's last result: start rank 1 first,
   // since rank 0's draft submission runs synchronously here (about 0.4 ms). Same commands, earlier rank-1 issue.
   if(early_accept&&c.draft_rank==0&&!c.dumps&&early_rank1()){p150::measure("handoff_host",p+1,false,[&]{b.handover();});half_start(1,confirmed,p+1);rank1_started_at=clock_now();}
   // A decode miss: rank 1 waits for rank 0's redo, while the draft is needed only by the next speculative half. Run
   // rollback and redo first, start rank 1, then issue the draft (same commands; the draft takes rank 1's rows from
   // host memory at submission).
   defer_draft=c.draft_rank==0&&pending&&!early_accept&&!known&&!b.correction_probe&&!c.dumps&&early_rank1();
   if(!defer_draft){b.start(c.draft_rank,draft,confirmed,p+1,int(p+2>=length),1);pending_draft_sequence=b.seq;issued_draft_at=b.sent[c.draft_rank];if(c.draft_rank==0)b.wait(0);draft_pending=true;}}
  if(known){if(!pending)half_start(0,c.prompt[p+1],p+1);if(b.pending[0])b.wait(0);if(!early_accept)b.call(0,accept);}
  else{int actual=out.tokens.back();if(pending){if(b.pending[0])b.wait(0);bool hit=guess==actual;if(hit){++out.hits;if(!early_accept)b.call(0,accept);}else{++out.misses;double redo=clock_now();if(b.correction_probe){if(b.pending[1])b.wait(1);b.start(1,14,actual,p+1,fixture(p+1));}b.call(0,rollback,actual,p+1,fixture(p+1),1);half_start(0,actual,p+1);b.wait(0);b.call(0,accept);if(b.correction_probe)b.wait(1);out.redo_ms+=(clock_now()-redo)*1000;
    if(defer_draft){p150::measure("handoff_host",p+1,false,[&]{b.handover();});half_start(1,actual,p+1);rank1_started_at=clock_now();
     b.start(0,draft,actual,p+1,int(p+2>=length),1);pending_draft_sequence=b.seq;issued_draft_at=b.sent[0];b.wait(0);draft_pending=true;defer_draft=false;}}out.guesses.push_back({p+1,guess,actual,hit,(clock_now()-cycle)*1000});}
   else{half_start(0,actual,p+1);b.wait(0);b.call(0,accept);}}
   // Both ranks have accepted, or the miss has rolled back and been corrected.
   // Publish only the target output, never the next-token draft or speculative half.
   if(fixture(p)>0&&emit)emit(out.tokens.size(),out.tokens.back(),out.rows.back().stamp);
   if(c.dumps)b.call(0,dump,0,p+1);
 }
 require(!draft_pending,"native unresolved draft");out.end=clock_now();b.call(1,0);return out;
}
inline std::string json(const Result& r,const Backend& b,const Config& c){
 std::ostringstream o;o.precision(17);o<<"{\"tokens\":[";for(size_t i=0;i<r.tokens.size();++i)o<<(i?",":"")<<r.tokens[i];
 double duration=r.rows.size()>1?(r.rows.back().stamp-r.rows.front().stamp)*1000:0;
 o<<"],\"stats\":{\"guesses\":"<<r.guesses_count<<",\"hits\":"<<r.hits<<",\"misses\":"<<r.misses<<",\"no_guess\":"<<r.no_guess<<",\"redo_ms\":"<<r.redo_ms<<"},\"prompt_wall_ms\":"<<r.prompt_ms<<",\"decode_wall_ms\":"<<duration<<",\"decode_intervals\":"<<(r.tokens.empty()?0:r.tokens.size()-1)<<",\"decode_numerator\":"<<(r.tokens.empty()?0:r.tokens.size()-1)<<",\"prompt_overlap\":"<<(c.overlap?"true":"false")<<",\"controller\":\"native\",\"bounded_spin_iterations\":null,\"wait_policy\":\""<<(p56x::sleep20?"sleep20":"spin")<<"\",\"spin_before_sleep_us\":"<<(p56x::sleep20?250:0)<<",\"yield_iterations\":256,\"work_start\":"<<r.start<<",\"work_end\":"<<r.end<<",\"timing_rows\":[";
 for(size_t i=0;i<r.rows.size();++i)o<<(i?",":"")<<"{\"generated_index\":"<<i+1<<",\"token_id\":"<<r.rows[i].token<<",\"completed_monotonic\":"<<r.rows[i].stamp<<"}";
 o<<"],\"guess_sequence\":[";for(size_t i=0;i<r.guess_sequence.size();++i){o<<(i?",":"");if(r.guess_sequence[i]<0)o<<"null";else o<<r.guess_sequence[i];}
 o<<"],\"draft_rows\":[";for(size_t i=0;i<r.draft_rows.size();++i){auto& d=r.draft_rows[i];o<<(i?",":"")<<"{\"position\":"<<d.position<<",\"sequence\":"<<d.sequence<<",\"guess\":"<<(d.guess<0?"null":std::to_string(d.guess))<<",\"provider_error\":"<<d.error<<",\"draft_wall_ms\":"<<d.wall_ms<<",\"draft_gpu_ms\":"<<d.gpu_ms<<",\"rank0_idle_waiting_for_guess_ms\":"<<d.wait_ms<<",\"draft_started_monotonic\":"<<d.started<<",\"rank1_half_started_monotonic\":"<<d.half_started<<",\"rank1_before_half_ms\":"<<(d.half_started-d.started)*1000<<",\"actual\":"<<d.actual<<",\"hit\":"<<(d.hit<0?"null":d.hit?"true":"false")<<",\"target_completed_monotonic\":"<<d.completed;if(d.cycle_ms>=0)o<<",\"cycle_ms\":"<<d.cycle_ms;o<<"}";}
 o<<"],\"guess_rows\":[";for(size_t i=0;i<r.guesses.size();++i){auto& g=r.guesses[i];o<<(i?",":"")<<"{\"position\":"<<g.position<<",\"guess\":"<<g.guess<<",\"actual\":"<<g.actual<<",\"hit\":"<<(g.hit?"true":"false")<<",\"cycle_ms\":"<<g.cycle_ms<<"}";}
 o<<"],\"rank_trace\":[";for(size_t i=0;i<b.trace.size();++i){auto& t=b.trace[i];o<<(i?",":"")<<"{\"rank\":"<<t.rank<<",\"op\":"<<t.command.op<<",\"token\":"<<t.command.token<<",\"position\":"<<t.command.position<<",\"fixture\":"<<t.command.fixture<<",\"speculative\":"<<(t.command.speculative?"true":"false")<<",\"busy_ms\":"<<t.reply.busy_ms<<",\"gpu_ms\":"<<t.reply.gpu_ms<<",\"sent\":"<<t.sent<<",\"rank_received\":"<<t.reply.redo_ms<<",\"rank_completed\":"<<t.reply.reserved_ms<<"}";}return o.str()+"]}";
}
} // namespace pipeline::native38
