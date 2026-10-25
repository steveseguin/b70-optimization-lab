#pragma once
// Unpromoted adapter: include after existing pipeline::half_step/publish and
// the proposal's StageRing/CheckpointRing headers. No copied model executor.
namespace pipeline::ring_next {
class EngineBackend {
 Engine& e;SpeculativeImage& inactive_legacy;CheckpointRingFor<Engine>& snapshots;uint8_t* shared;std::function<void()> reset_owner;std::vector<uint8_t> input;bool input_ready=false;
public:
 struct Result {int token=-1;Candidate candidate;std::vector<uint8_t> stream;};
 EngineBackend(Engine& owner,SpeculativeImage& legacy,CheckpointRingFor<Engine>& ring,uint8_t* map,std::function<void()> cold_reset={}):e(owner),inactive_legacy(legacy),snapshots(ring),shared(map),reset_owner(std::move(cold_reset)){
  require(shared&&e.a.retain_steps.ranges.empty(),"ring native backend retain_steps none");
 }
 int position(){return e.integer(0,"position");}int error(){return e.integer(0,"error");}
 bool retention_disabled()const{return e.a.retain_steps.ranges.empty();}
 void quiescent(){e.drain();if(e.a.rank==1)e.reply_report.flush();require(!e.progress_pending&&!e.progress_callback&&!e.poisoned,"ring native unresolved owner");}
 void stage_input(std::vector<uint8_t> bytes){require(!input_ready&&bytes.size()==(e.a.pipeline_first()?0:e.stream_bytes()),"ring owned input extent/lifetime");input=std::move(bytes);input_ready=true;}
 int capture(const ownrt::ring_next::Row&){return snapshots.capture(shared);}
 Result execute(const ownrt::ring_next::Row& row){
  Request request{half,row.token,row.position,row.fixture,0,row.ticket,{e.a.pipeline_stage,int(e.a.pipeline_final())}};
  require(input_ready,"ring missing owned input");e.verify_configuration();e.guard();
  // Existing rank-one prepared-input path consumes private uploaded bytes.
  // This avoids re-reading a shared slot after its hash was checked.
  if(!e.a.pipeline_first()){e.put(0,"token",&row.token,4);e.put(0,"streams",input.data(),input.size());}
  Result result;auto reply=half_step(e,result.candidate,request,shared,inactive_legacy,!e.a.pipeline_first());input_ready=false;input.clear();
  require(result.candidate.pending&&!result.candidate.cancelled&&!result.candidate.speculative,"ring native row completion");
  result.token=reply.token;if(!e.a.pipeline_final()){require(reply.bytes==int(e.stream_bytes()),"ring full native output extent");result.stream.assign(shared,shared+reply.bytes);}
  else require(!reply.bytes,"ring final stage stream ownership");return result;
 }
 void publish(const Result& result){require(retention_disabled(),"ring retained evidence not admitted");pipeline::publish(e,result.candidate);}
 void restore(int slot){snapshots.restore(slot);}void release(int slot){snapshots.release(slot);}
 // The checked request/provider reset is invoked only after StageRing has
 // admitted an empty canonical boundary, then descriptors are rebuilt in place.
 void reset(){require(bool(reset_owner),"ring cold reset callback not bound");reset_owner();snapshots.reset_after_owner_zero();}
};
}
