#pragma once
#include "wire.hpp"
#include "checkpoint_ring.hpp"
#include "engine_backend.hpp"
// Unpromoted concrete command24..26 handler. Include after existing native
// Request/Reply,half_step,publish,reverse_ready. Existing handlers20..23 untouched.
namespace pipeline::ring_next {
class Dispatcher {
 Engine& e;uint8_t* shared;size_t mapped_bytes;bool verify;
 ownrt::ring_next::wire::Context context;
 CheckpointRingFor<Engine> checkpoints;
 EngineBackend backend;
 ownrt::ring_next::StageRing<EngineBackend> ring;
 std::span<uint8_t> area(size_t offset,size_t bytes){require(offset<=mapped_bytes&&bytes<=mapped_bytes-offset,"ring shared metadata bound");return {shared+offset,bytes};}
 void final_hidden(const ownrt::ring_next::Row& row,int commit_sequence,int next_token,Reply& reply){
  if(!e.a.pipeline_live_draft)return;
  require(e.a.pipeline_final()&&reverse_ready(shared).position_plus_one==uint32_t(row.position+1),"ring final raw hidden ownership");
  ownrt::live_draft::Handoff h;h.bytes=int32_t(e.stream_bytes());h.position=row.position;h.final_stage=e.a.pipeline_stage;h.stages=int32_t(e.a.pipeline_boundaries.size()-1);
  h.row_ticket=row.ticket;h.commit_sequence=commit_sequence;h.input_token=row.token;h.head=row.fixture>0;h.next_token=h.head?next_token:-1;
  const auto raw=area(ownrt::live_draft::hidden_offset,h.bytes);const auto bytes=std::vector<uint8_t>(raw.begin(),raw.end());const auto sha=hash(bytes);require(sha.size()==h.hidden_sha256.size(),"ring hidden SHA length");std::memcpy(h.hidden_sha256.data(),sha.data(),sha.size());
  ownrt::live_draft::validate(h,context.stream_bytes,context.stages,context.vocab);std::memcpy(area(ownrt::live_draft::header_offset,sizeof h).data(),&h,sizeof h);reply.bytes=h.bytes;reply.token=h.next_token;
 }
public:
 Dispatcher(Engine& owner,SpeculativeImage& legacy,const OperatorStatePartition& partition,uint8_t* mapping,size_t mapping_bytes,bool full_byte_verify,uint64_t epoch,ownrt::ring_next::Digest request,std::function<void()> reset_owner={})
  :e(owner),shared(mapping),mapped_bytes(mapping_bytes),verify(full_byte_verify),
   context{epoch,request,owner.a.pipeline_stage,int(owner.a.pipeline_boundaries.size()-1),int(owner.stream_bytes()),owner.p.g.vocab},
   checkpoints(owner,full_byte_verify,partition),backend(owner,legacy,checkpoints,mapping,std::move(reset_owner)),
   ring(backend,owner.a.pipeline_final(),partition.enabled,owner.p.g.context,owner.p.g.vocab,epoch,request,ownrt::ring_next::request_prefix(request,epoch)){
  require(shared&&mapped_bytes==shared_bytes&&owner.a.pipeline_enabled(),"ring dispatcher mapping/mode");ownrt::ring_next::wire::context(context);legacy.boundary();
 }
 static bool handles(int op){return op==24||op==25||op==26;}
 Reply execute(const Request& r){
  namespace wire=ownrt::ring_next::wire;require(handles(r.op),"ring dispatcher only owns24..26");
  const auto started=std::chrono::steady_clock::now();const double gpu_before=e.gemv_ms+e.nongemv_ms;
  wire::Command command{r.op,r.token,r.position,r.fixture,r.speculative,r.sequence,r.reserved[0],r.reserved[1]};
  const auto meta=wire::read<wire::RowMeta>(area(wire::row_offset,sizeof(wire::RowMeta)));
  Reply reply{};reply.sequence=r.sequence;reply.rank=e.a.rank;reply.reserved[0]=context.stage;reply.reserved[1]=context.stage==context.stages-1;
  if(r.op==wire::row_op){
   const auto bytes=e.a.pipeline_first()?std::span<uint8_t>{}:area(slot_bytes,context.stream_bytes);std::vector<uint8_t> owned(bytes.begin(),bytes.end());
   const auto row=wire::row(meta,command,context,owned);backend.stage_input(std::move(owned));const auto& completed=ring.execute(row);
   reply.token=completed.token;reply.bytes=int32_t(completed.stream.size());
   require(completed.stream.empty()||completed.stream.size()==size_t(context.stream_bytes),"ring complete native stream result");
   if(!completed.stream.empty())std::memcpy(area(0,completed.stream.size()).data(),completed.stream.data(),completed.stream.size());
   const auto publication=wire::publication(meta,r.sequence,completed.stream);wire::write(area(wire::row_offset,sizeof publication),publication);
  }else{
   const auto row=wire::resolution(meta,command,context);const auto prior_checks=checkpoints.byte_checks();
   const int next_token=ring.oldest_result(row).token;
   const auto resolved=r.op==wire::accept_op?ring.accept(r.sequence,row,r.token):ring.abort_suffix(r.sequence,row);
   const auto acknowledgment=wire::acknowledgment(context,r.sequence,row,resolved,checkpoints.byte_checks()>prior_checks);
   wire::write(area(wire::ack_offset,sizeof acknowledgment),acknowledgment);
   if(r.op==wire::accept_op&&e.a.pipeline_final())final_hidden(row,r.sequence,next_token,reply);
  }
  reply.busy_ms=Engine::ms(started);reply.gpu_ms=e.gemv_ms+e.nongemv_ms-gpu_before;
  return reply;
 }
 // Wire RESET parsing/epoch authority and ring attestation are not implemented
 // by this proposal. The checked outer request boundary supplies the new scope.
 void reset_boundary(int sequence,uint64_t epoch,ownrt::ring_next::Digest request){
  ring.reset(sequence,epoch,request,ownrt::ring_next::request_prefix(request,epoch));context.epoch=epoch;context.request=request;
  std::memset(area(ownrt::ring_next::wire::row_offset,sizeof(ownrt::ring_next::wire::RowMeta)).data(),0,sizeof(ownrt::ring_next::wire::RowMeta));
  std::memset(area(ownrt::ring_next::wire::ack_offset,sizeof(ownrt::ring_next::wire::Ack)).data(),0,sizeof(ownrt::ring_next::wire::Ack));
 }
 void reply_published(int op){if(op==ownrt::ring_next::wire::row_op&&e.a.rank==1)e.reply_report.published();}
 void boundary(){ring.boundary();}
};
}
