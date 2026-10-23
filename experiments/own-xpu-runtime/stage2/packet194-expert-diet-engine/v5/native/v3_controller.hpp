// Packet186 V3 controller (included by v3_boundary.hpp; also compiled alone by the mock gate).
#pragma once
namespace pipeline::v3 {constexpr int32_t boundary_op=15;}
namespace pipeline::native38 {
// native38::run() with one rank-0 boundary command after every rank-0 accept that a rank-1 half
// will consume. Command order on rank 0 per cycle: [rollback, corrected half on a miss] -> accept
// (host-only, measured 0.3 us/cycle) -> boundary (layers 24-25 + export, inside rank 1's draft
// window) -> wait draft -> speculative half. The accept never waits on GPU work and the boundary
// never waits on a capture: the speculative image is captured at the start of the NEXT half.
inline Result run_v3(Backend& b,const Config& c){
 require(c.draft_rank==1,"V3 controller requires the rank-1 draft");
 Result out;out.start=clock_now();std::vector<int> history;bool draft_pending=false;double issued_draft_at=0;uint32_t pending_draft_sequence=0;size_t script_index=0;int length=int(c.prompt.size());
 auto fixture=[&](int p){return std::max(0,p-length+2);};
 auto half_start=[&](int rank,int token,int p,bool spec=false){b.start(rank,half,token,p,fixture(p),spec);};
 auto boundary=[&](int token,int p){b.stream_bytes=0;Reply r=b.call(0,v3::boundary_op,token,p,fixture(p));require(r.bytes>0&&size_t(r.bytes)<=slot_bytes,"V3 boundary export");b.stream_bytes=size_t(r.bytes);};
 half_start(0,c.prompt[0],0);b.wait(0);b.call(0,accept);boundary(c.prompt[0],0);
 for(int p=0;p<length+c.count-1;++p){
  double cycle=clock_now();int token=p<length?c.prompt[p]:out.tokens.back();history.push_back(token);int draft_guess=-1;
  uint32_t expected_draft=0;double draft_started=0;
  if(draft_pending){expected_draft=pending_draft_sequence;draft_started=issued_draft_at;if(b.pending[1])b.wait(1);draft_pending=false;}
  p150::measure("handoff_host",p,false,[&]{b.handover();});half_start(1,token,p);double half_started=clock_now();
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
   if(std::find(c.eos.begin(),c.eos.end(),result.token)!=c.eos.end()){if(pending){b.wait(0);b.call(0,rollback);}break;}
  }
  if(!more)break;
  if(c.mode==3){int confirmed=known?c.prompt[p+1]:out.tokens.back();
   b.start(c.draft_rank,draft,confirmed,p+1,int(p+2>=length),1);pending_draft_sequence=b.seq;issued_draft_at=b.sent[c.draft_rank];draft_pending=true;}
  if(known){if(!pending)half_start(0,c.prompt[p+1],p+1);if(b.pending[0])b.wait(0);b.call(0,accept);boundary(c.prompt[p+1],p+1);}
  else{int actual=out.tokens.back();if(pending){if(b.pending[0])b.wait(0);bool hit=guess==actual;if(hit){++out.hits;b.call(0,accept);}else{++out.misses;double redo=clock_now();if(b.correction_probe){if(b.pending[1])b.wait(1);b.start(1,14,actual,p+1,fixture(p+1));}b.call(0,rollback,actual,p+1,fixture(p+1),1);half_start(0,actual,p+1);b.wait(0);b.call(0,accept);if(b.correction_probe)b.wait(1);out.redo_ms+=(clock_now()-redo)*1000;}boundary(actual,p+1);out.guesses.push_back({p+1,guess,actual,hit,(clock_now()-cycle)*1000});}
   else{half_start(0,actual,p+1);b.wait(0);b.call(0,accept);boundary(actual,p+1);}}
  if(c.dumps)b.call(0,dump,0,p+1);
 }
 require(!draft_pending,"native unresolved draft");out.end=clock_now();b.call(1,0);return out;
}
} // namespace pipeline::native38
