#pragma once
#include "wire.hpp"
#include "checkpoint_ring.hpp"
#include "engine_backend.hpp"
// Opt-in concrete command24..26 handler. Include after existing native
// Request/Reply,half_step,publish,reverse_ready. Existing handlers20..23 untouched.
namespace pipeline::ring_next {
class Dispatcher {
 Engine& e;uint8_t* shared;size_t mapped_bytes;bool verify;
 ownrt::ring_next::wire::Context context;
 CheckpointRingFor<Engine> checkpoints;
 EngineBackend backend;
 ownrt::ring_next::StageRing<EngineBackend> ring;std::ofstream trace;uint64_t trace_rows=0,trace_omitted=0;
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
  require(owner.a.pipeline_ring&&!owner.a.pipeline_wavefront&&!owner.a.mtp&&!partition.enabled&&!owner.a.pipeline_live_draft,"ring exclusive target-only owner");
  checkpoints.write_layout(e.a.output/"ring-checkpoint-layout.json");
  trace.open(e.a.output/"ring.jsonl");require(bool(trace),"ring trace open");
 }
 static bool handles(int op){return op==24||op==25||op==26;}
 Reply execute(const Request& r){
  namespace wire=ownrt::ring_next::wire;require(handles(r.op),"ring dispatcher only owns24..26");
  const auto started=std::chrono::steady_clock::now();const double gpu_before=e.gemv_ms+e.nongemv_ms;
  wire::Command command{r.op,r.token,r.position,r.fixture,r.speculative,r.sequence,r.reserved[0],r.reserved[1]};
  const auto meta=wire::read<wire::RowMeta>(area(wire::row_offset,sizeof(wire::RowMeta)));
  std::vector<uint64_t> discarded;
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
   discarded=resolved.discarded;
   const auto acknowledgment=wire::acknowledgment(context,r.sequence,row,resolved,checkpoints.byte_checks()>prior_checks);
   wire::write(area(wire::ack_offset,sizeof acknowledgment),acknowledgment);
   if(r.op==wire::accept_op&&e.a.pipeline_final())final_hidden(row,r.sequence,next_token,reply);
  }
  if(trace_rows<size_t(e.a.pipeline_ring_trace_limit)){
   trace<<"{\"op\":"<<r.op<<",\"sequence\":"<<r.sequence<<",\"row_id\":"<<meta.id<<",\"parent_id\":"<<meta.parent<<",\"position\":"<<meta.position<<",\"token\":"<<meta.token<<",\"fixture\":"<<meta.fixture<<",\"tentative\":"<<((meta.flags&wire::tentative)?"true":"false")<<",\"physical\":"<<ring.physical()<<",\"committed\":"<<ring.committed()<<",\"pending\":"<<ring.pending()<<",\"discarded\":[";
   for(size_t i=0;i<discarded.size();++i)trace<<(i?",":"")<<discarded[i];trace<<"]}\n";trace.flush();require(bool(trace),"ring trace write");++trace_rows;
  }else ++trace_omitted;
  reply.busy_ms=Engine::ms(started);reply.gpu_ms=e.gemv_ms+e.nongemv_ms-gpu_before;
  return reply;
 }
 // Initial ring integration refuses RESET and all provider commands.
 void attest(const fs::path& destination={},int dump_marker=-1){
  ring.boundary();checkpoints.boundary();const int position=e.integer(0,"position");
  require(position==ring.committed()&&uint64_t(position)==ring.commits,"ring canonical position/commit conservation");
  require(e.bank_parity==(e.a.pipeline_first()?unsigned(position%2):0u),"ring canonical bank parity");
  require(ring.rows==ring.commits+ring.discarded_rows&&ring.tentative_rows==ring.accepted_tentative_rows+ring.discarded_rows,"ring row conservation");
  require(checkpoints.captures()==ring.tentative_rows&&checkpoints.releases()==checkpoints.captures()&&checkpoints.restores()==ring.abort_count,"ring snapshot conservation");
  require((!ring.abort_count&&!ring.discarded_rows)||(ring.abort_count<=ring.discarded_rows&&ring.discarded_rows<=2*ring.abort_count),"ring suffix count conservation");
  auto file_hash=[&](const fs::path& path,size_t limit){
   const int fd=::open(path.c_str(),O_RDONLY|O_NOFOLLOW|O_NONBLOCK);require(fd>=0,"ring evidence open");
   struct Close {int fd;~Close(){::close(fd);}} close{fd};struct stat before{},after{},named{};
   require(!::fstat(fd,&before)&&S_ISREG(before.st_mode)&&before.st_size>0&&uint64_t(before.st_size)<=limit,"ring bounded regular evidence");
   std::vector<uint8_t> bytes(size_t(before.st_size));size_t done=0;
   while(done<bytes.size()){auto n=::pread(fd,bytes.data()+done,bytes.size()-done,off_t(done));if(n<0&&errno==EINTR)continue;require(n>0,"ring bounded evidence read");done+=size_t(n);}
   require(!::fstat(fd,&after)&&!::lstat(path.c_str(),&named)&&S_ISREG(named.st_mode)&&before.st_dev==after.st_dev&&before.st_ino==after.st_ino&&before.st_size==after.st_size&&before.st_mtim.tv_sec==after.st_mtim.tv_sec&&before.st_mtim.tv_nsec==after.st_mtim.tv_nsec&&before.st_ctim.tv_sec==after.st_ctim.tv_sec&&before.st_ctim.tv_nsec==after.st_ctim.tv_nsec&&before.st_dev==named.st_dev&&before.st_ino==named.st_ino,"ring evidence identity changed");return hash(bytes);
  };
  const auto layout=file_hash(e.a.output/"ring-checkpoint-layout.json",1024*1024);
  std::string seal;if(dump_marker>=0)seal=file_hash(e.a.output/("state-"+std::to_string(dump_marker))/"state-seal.txt",4096);
  std::ostringstream o;o<<"{\"schema\":\"ownrt.ring-state.v1\",\"mode\":\"verified-ring\",\"stage_id\":"<<context.stage<<",\"ring_request_sha256\":"<<ownrt::quote(e.a.pipeline_ring_request_sha256)<<",\"ring_epoch\":"<<context.epoch<<",\"ring_capacity\":2,\"depth\":2,\"dump_marker\":"<<dump_marker<<",\"state_seal_sha256\":"<<ownrt::quote(seal)<<",\"checkpoint_layout_sha256\":"<<ownrt::quote(layout)
   <<",\"actual_position\":"<<position<<",\"committed_position\":"<<ring.committed()<<",\"pending_tickets\":0,\"active_slots\":0,\"sticky_error\":0,\"rows\":"<<ring.rows<<",\"tentative_rows\":"<<ring.tentative_rows<<",\"commits\":"<<ring.commits<<",\"accepted_tentative_rows\":"<<ring.accepted_tentative_rows<<",\"abort_count\":"<<ring.abort_count<<",\"discarded_rows\":"<<ring.discarded_rows<<",\"snapshot_captures\":"<<checkpoints.captures()<<",\"snapshot_releases\":"<<checkpoints.releases()<<",\"byteverified_restore_count\":"<<checkpoints.byte_checks()<<",\"saved_bytes\":"<<checkpoints.captures()*checkpoints.slot_bytes()<<",\"target_mutable_checkpoint_bytes\":"<<checkpoints.slot_bytes()
   <<",\"restore_verification_enabled\":"<<(verify?"true":"false")<<",\"all_aborts_byte_verified\":"<<(checkpoints.byte_checks()==ring.abort_count?"true":"false")<<",\"max_pending\":"<<ring.max_pending<<",\"trace_records\":"<<trace_rows<<",\"trace_omitted\":"<<trace_omitted<<",\"bank_parity\":"<<e.bank_parity<<",\"inactive_alternate_banks\":[";
  bool comma=false;for(const auto& [name,id]:e.state_spares){o<<(comma?",":"")<<ownrt::quote(name);comma=true;}o<<"],\"canonical_bank_mapping\":{";comma=false;
  for(const auto& [name,id]:e.state_spares){o<<(comma?",":"")<<ownrt::quote(name)<<":{\"active_allocation\":"<<e.buffers[0].at(name).id<<",\"inactive_allocation\":"<<id<<"}";comma=true;}o<<"}}";
  const auto path=destination.empty()?e.a.output/"ring-quiescence.json":destination;
  const auto text=o.str();struct stat prior{};const int found=::lstat(path.c_str(),&prior);
  if(!found){require(dump_marker>=0&&S_ISREG(prior.st_mode),"ring attestation destination already exists or is not regular");const std::vector<uint8_t> expected(text.begin(),text.end());require(file_hash(path,1024*1024)==hash(expected),"ring sealed attestation changed");}
  else {require(errno==ENOENT,"ring attestation destination lookup");const int fd=::open(path.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);require(fd>=0,"ring fresh attestation create");struct Close{int fd;~Close(){::close(fd);}} close{fd};size_t done=0;while(done<text.size()){auto n=::write(fd,text.data()+done,text.size()-done);if(n<0&&errno==EINTR)continue;require(n>0,"ring attestation write");done+=size_t(n);}}
 }
 void reply_published(int op){if(op==ownrt::ring_next::wire::row_op&&e.a.rank==1)e.reply_report.published();}
 void boundary(){ring.boundary();}
};
}
